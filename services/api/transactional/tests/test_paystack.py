import hashlib
import hmac
import json
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from transactional.models import (
    InventoryItem,
    InventoryMovement,
    Payment,
    PaymentWebhookEvent,
    POSLocation,
    POSOperator,
    POSOperatorLocation,
    POSOperatorTerminal,
    POSTerminal,
    Product,
    Sale,
    SaleLine,
)
from transactional.payment_providers import PaymentIntent, PaymentProviderError, VerifiedPayment
from transactional.payment_services import create_pending_sale, initialize_external_payment
from transactional.providers.paystack import PaystackProvider
from transactional.services import CheckoutLine


class FakeUrlopenResponse:
    def __init__(self, payload: dict):
        self.payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self.payload


@pytest.fixture
def paystack_provider():
    return PaystackProvider(
        secret_key="sk_test_example",
        base_url="https://api.paystack.co",
    )


@pytest.fixture
def pos_operator():
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="paystack-pos-operator",
        password="test-password",
        is_staff=True,
    )
    location = POSLocation.objects.create(
        code="MAIN",
        name="Main Store",
    )
    terminal = POSTerminal.objects.create(
        location=location,
        code="MAIN-01",
        name="Main Terminal",
    )
    operator = POSOperator.objects.create(user=user)
    POSOperatorLocation.objects.create(operator=operator, location=location)
    POSOperatorTerminal.objects.create(operator=operator, terminal=terminal)

    return user, location, terminal


@pytest.fixture
def pending_external_payment():
    product = Product.objects.create(
        sku="SKU-PAYSTACK-001",
        name="Paystack Product",
        currency="NGN",
        unit_price_minor=2500,
    )
    InventoryItem.objects.create(
        product=product,
        location_code="MAIN",
        quantity=5,
    )

    sale = create_pending_sale(
        lines=[CheckoutLine(product_id=product.id, quantity=2)],
        location_code="MAIN",
        currency="NGN",
        idempotency_key="paystack-sale-001",
    )

    return product, sale


def test_paystack_initiate_payment_parses_response(paystack_provider):
    payload = {
        "status": True,
        "message": "Authorization URL created",
        "data": {
            "authorization_url": "https://checkout.paystack.com/example",
            "access_code": "example",
            "reference": "TK-1-ref",
        },
    }

    with patch(
        "transactional.providers.paystack.urlopen",
        return_value=FakeUrlopenResponse(payload),
    ):
        intent = paystack_provider.initiate_payment(
            amount_minor=2500,
            currency="NGN",
            reference="TK-1-ref",
            customer_email="customer@example.com",
        )

    assert intent == PaymentIntent(
        provider="PAYSTACK",
        provider_reference="TK-1-ref",
        amount_minor=2500,
        currency="NGN",
        checkout_url="https://checkout.paystack.com/example",
        access_code="example",
    )


def test_paystack_verify_payment_parses_success(paystack_provider):
    payload = {
        "status": True,
        "message": "Verification successful",
        "data": {
            "status": "success",
            "reference": "TK-1-ref",
            "amount": 2500,
            "currency": "NGN",
        },
    }

    with patch(
        "transactional.providers.paystack.urlopen",
        return_value=FakeUrlopenResponse(payload),
    ):
        verified = paystack_provider.verify_payment(
            provider_reference="TK-1-ref",
        )

    assert verified == VerifiedPayment(
        provider="PAYSTACK",
        provider_reference="TK-1-ref",
        amount_minor=2500,
        currency="NGN",
        succeeded=True,
    )


def test_paystack_webhook_signature_validation(paystack_provider):
    body = b'{"event":"charge.success"}'
    signature = hmac.new(
        b"sk_test_example",
        body,
        hashlib.sha512,
    ).hexdigest()

    assert paystack_provider.verify_webhook_signature(
        payload=body,
        signature=signature,
    )

    assert not paystack_provider.verify_webhook_signature(
        payload=body,
        signature="invalid",
    )


@pytest.mark.django_db
def test_initialize_external_payment_persists_pending_payment(pending_external_payment):
    _, sale = pending_external_payment

    class FakeProvider:
        name = "PAYSTACK"

        def initiate_payment(self, **kwargs):
            assert kwargs["amount_minor"] == 5000
            assert kwargs["currency"] == "NGN"
            assert kwargs["customer_email"] == "customer@example.com"
            return PaymentIntent(
                provider="PAYSTACK",
                provider_reference=kwargs["reference"],
                amount_minor=5000,
                currency="NGN",
                checkout_url="https://checkout.example/payment",
                access_code="access-001",
            )

    result = initialize_external_payment(
        sale_id=sale.sale_id,
        customer_email="customer@example.com",
        provider=FakeProvider(),
        idempotency_key="paystack-init-001",
    )

    payment = Payment.objects.get(id=result.payment_id)

    assert result.provider == "PAYSTACK"
    assert result.amount_minor == 5000
    assert result.status == Payment.Status.PENDING
    assert result.checkout_url == "https://checkout.example/payment"
    assert result.access_code == "access-001"
    assert payment.provider_metadata["checkout_url"] == "https://checkout.example/payment"
    assert payment.provider_metadata["access_code"] == "access-001"
    assert Sale.objects.get(id=sale.sale_id).status == Sale.Status.PENDING_PAYMENT
    assert InventoryMovement.objects.count() == 0
    assert SaleLine.objects.count() == 1


@pytest.mark.django_db
def test_initialize_external_payment_retry_is_idempotent(pending_external_payment):
    _, sale = pending_external_payment

    provider = type(
        "FakeProvider",
        (),
        {
            "name": "PAYSTACK",
            "initiate_payment": lambda self, **kwargs: PaymentIntent(
                provider="PAYSTACK",
                provider_reference=kwargs["reference"],
                amount_minor=5000,
                currency="NGN",
                checkout_url="https://checkout.example/payment",
                access_code="access-001",
            ),
        },
    )()

    first = initialize_external_payment(
        sale_id=sale.sale_id,
        customer_email="customer@example.com",
        provider=provider,
        idempotency_key="paystack-init-retry-001",
    )
    second = initialize_external_payment(
        sale_id=sale.sale_id,
        customer_email="customer@example.com",
        provider=provider,
        idempotency_key="paystack-init-retry-001",
    )

    assert first == second
    assert Payment.objects.count() == 1


@pytest.mark.django_db
def test_paystack_payment_initiation_endpoint_returns_checkout_data(
    monkeypatch,
    pos_operator,
    pending_external_payment,
):
    user, _, _ = pos_operator
    _, sale = pending_external_payment
    monkeypatch.setenv("PAYSTACK_SECRET_KEY", "sk_test_example")

    response_payload = {
        "status": True,
        "message": "Authorization URL created",
        "data": {
            "authorization_url": "https://checkout.paystack.com/example",
            "access_code": "example",
            "reference": "TK-1-ref",
        },
    }

    with patch(
        "transactional.providers.paystack.urlopen",
        return_value=FakeUrlopenResponse(response_payload),
    ):
        client = Client()
        client.force_login(user)
        response = client.post(
            "/api/transactional/payments/paystack/initialize/",
            data=json.dumps(
                {
                    "sale_id": sale.sale_id,
                    "customer_email": "customer@example.com",
                    "idempotency_key": "api-paystack-init-001",
                    "location_code": "MAIN",
                    "terminal_code": "MAIN-01",
                }
            ),
            content_type="application/json",
        )

    assert response.status_code == 201
    payload = response.json()

    assert payload["provider"] == "PAYSTACK"
    assert payload["sale_id"] == sale.sale_id
    assert payload["amount_minor"] == 5000
    assert payload["status"] == Payment.Status.PENDING
    assert payload["checkout_url"] == "https://checkout.paystack.com/example"
    assert payload["access_code"] == "example"
    assert Payment.objects.count() == 1


@pytest.mark.django_db
def test_paystack_webhook_endpoint_rejects_invalid_signature(
    monkeypatch,
):
    monkeypatch.setenv("PAYSTACK_SECRET_KEY", "sk_test_example")

    body = json.dumps(
        {
            "event": "charge.success",
            "data": {"reference": "missing"},
        }
    ).encode()

    response = Client().post(
        "/api/transactional/webhooks/paystack/",
        data=body,
        content_type="application/json",
        HTTP_X_PAYSTACK_SIGNATURE="invalid",
    )

    assert response.status_code == 400
    assert response.json()["error"] == "invalid_signature"


@pytest.mark.django_db
def test_paystack_webhook_endpoint_completes_pending_payment(
    monkeypatch,
    pending_external_payment,
):
    monkeypatch.setenv("PAYSTACK_SECRET_KEY", "sk_test_example")
    product, sale = pending_external_payment

    payment = Payment.objects.create(
        sale_id=sale.sale_id,
        provider="PAYSTACK",
        provider_reference="TK-WEBHOOK-001",
        idempotency_key="paystack-webhook-payment-001",
        method=Payment.Method.EXTERNAL,
        amount_minor=5000,
        currency="NGN",
        status=Payment.Status.PENDING,
    )

    payload = {
        "event": "charge.success",
        "data": {
            "id": 123456,
            "reference": "TK-WEBHOOK-001",
            "amount": 5000,
            "currency": "NGN",
            "status": "success",
        },
    }
    body = json.dumps(payload).encode()
    signature = hmac.new(
        b"sk_test_example",
        body,
        hashlib.sha512,
    ).hexdigest()

    first = Client().post(
        "/api/transactional/webhooks/paystack/",
        data=body,
        content_type="application/json",
        HTTP_X_PAYSTACK_SIGNATURE=signature,
    )
    second = Client().post(
        "/api/transactional/webhooks/paystack/",
        data=body,
        content_type="application/json",
        HTTP_X_PAYSTACK_SIGNATURE=signature,
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["already_processed"] is False
    assert second.json()["already_processed"] is True
    assert Payment.objects.get(id=payment.id).status == Payment.Status.SUCCEEDED
    assert Sale.objects.get(id=sale.sale_id).status == Sale.Status.COMPLETED
    assert InventoryItem.objects.get(product=product).quantity == 3
    assert InventoryMovement.objects.count() == 1
    assert PaymentWebhookEvent.objects.count() == 1


@pytest.mark.django_db
def test_paystack_webhook_endpoint_allows_only_charge_success_event(
    monkeypatch,
):
    monkeypatch.setenv("PAYSTACK_SECRET_KEY", "sk_test_example")
    payload = {"event": "transfer.failed", "data": {}}
    body = json.dumps(payload).encode()
    signature = hmac.new(
        b"sk_test_example",
        body,
        hashlib.sha512,
    ).hexdigest()

    response = Client().post(
        "/api/transactional/webhooks/paystack/",
        data=body,
        content_type="application/json",
        HTTP_X_PAYSTACK_SIGNATURE=signature,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ignored"
    assert PaymentWebhookEvent.objects.count() == 0
