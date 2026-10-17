import pytest
from unittest.mock import Mock

from transactional.models import OutboxEvent, Payment, Product, InventoryItem, Sale
from transactional.payment_initiation import (
    PAYMENT_INITIATION_REQUESTED_EVENT,
    request_external_payment_initialization,
)
from transactional.payment_initiation_outbox import make_payment_initiation_outbox_handler
from transactional.payment_providers import PaymentIntent, PaymentProviderError
from transactional.payment_services import create_pending_sale
from transactional.outbox_dispatcher import dispatch_outbox_events
from transactional.services import CheckoutLine


def make_pending_sale():
    product = Product.objects.create(
        sku="SKU-INIT-OUTBOX-001",
        name="Initiation Outbox Product",
        currency="NGN",
        unit_price_minor=2500,
    )
    InventoryItem.objects.create(
        product=product,
        location_code="MAIN",
        quantity=5,
    )
    return create_pending_sale(
        lines=[CheckoutLine(product_id=product.id, quantity=2)],
        location_code="MAIN",
        currency="NGN",
        idempotency_key="init-outbox-sale-001",
    )


def make_provider(*, fail=False):
    provider = Mock(name="PaystackProvider")
    provider.name = "PAYSTACK"
    if fail:
        provider.initiate_payment.side_effect = PaymentProviderError(
            "provider unavailable"
        )
    else:
        provider.initiate_payment.side_effect = lambda **kwargs: PaymentIntent(
            provider="PAYSTACK",
            provider_reference=kwargs["reference"],
            amount_minor=kwargs["amount_minor"],
            currency=kwargs["currency"],
            checkout_url="https://checkout.example/payment",
            access_code="access-001",
        )
    return provider


@pytest.mark.django_db
def test_request_external_payment_initialization_creates_pending_payment_and_outbox():
    sale = make_pending_sale()
    provider = make_provider()

    result = request_external_payment_initialization(
        sale_id=sale.sale_id,
        customer_email="customer@example.com",
        provider=provider,
        idempotency_key="init-outbox-001",
    )

    payment = Payment.objects.get(id=result.payment_id)
    event = OutboxEvent.objects.get(idempotency_key="payment-initiation:init-outbox-001")

    assert result.status == Payment.Status.PENDING
    assert result.checkout_url is None
    assert result.access_code is None
    assert payment.status == Payment.Status.PENDING
    assert payment.provider_reference.startswith(f"TK-{sale.sale_id}-")
    assert payment.provider_metadata["customer_email"] == "customer@example.com"
    assert event.event_type == PAYMENT_INITIATION_REQUESTED_EVENT
    assert event.payload["payment_id"] == payment.id
    assert event.payload["provider"] == "PAYSTACK"
    assert event.payload["customer_email"] == "customer@example.com"
    provider.initiate_payment.assert_not_called()


@pytest.mark.django_db
def test_request_external_payment_initialization_is_idempotent():
    sale = make_pending_sale()
    provider = make_provider()

    first = request_external_payment_initialization(
        sale_id=sale.sale_id,
        customer_email="customer@example.com",
        provider=provider,
        idempotency_key="init-outbox-retry-001",
    )
    second = request_external_payment_initialization(
        sale_id=sale.sale_id,
        customer_email="customer@example.com",
        provider=provider,
        idempotency_key="init-outbox-retry-001",
    )

    assert first == second
    assert Payment.objects.count() == 1
    assert OutboxEvent.objects.filter(
        event_type=PAYMENT_INITIATION_REQUESTED_EVENT,
    ).count() == 1


@pytest.mark.django_db
def test_payment_initiation_outbox_handler_persists_checkout_data():
    sale = make_pending_sale()
    provider = make_provider()

    result = request_external_payment_initialization(
        sale_id=sale.sale_id,
        customer_email="customer@example.com",
        provider=provider,
        idempotency_key="init-outbox-handler-001",
    )

    dispatch_result = dispatch_outbox_events(
        {
            PAYMENT_INITIATION_REQUESTED_EVENT: make_payment_initiation_outbox_handler(
                provider
            )
        },
        limit=1,
    )

    payment = Payment.objects.get(id=result.payment_id)
    event = OutboxEvent.objects.get(
        idempotency_key="payment-initiation:init-outbox-handler-001"
    )

    assert dispatch_result.completed == 1
    assert dispatch_result.failed == 0
    assert payment.provider_metadata["checkout_url"] == "https://checkout.example/payment"
    assert payment.provider_metadata["access_code"] == "access-001"
    assert event.status == OutboxEvent.Status.COMPLETED
    assert provider.initiate_payment.call_count == 1


@pytest.mark.django_db
def test_payment_initiation_provider_failure_is_retryable():
    sale = make_pending_sale()
    failing_provider = make_provider(fail=True)

    result = request_external_payment_initialization(
        sale_id=sale.sale_id,
        customer_email="customer@example.com",
        provider=failing_provider,
        idempotency_key="init-outbox-failure-001",
    )

    first_dispatch = dispatch_outbox_events(
        {
            PAYMENT_INITIATION_REQUESTED_EVENT: make_payment_initiation_outbox_handler(
                failing_provider
            )
        },
        limit=1,
    )

    payment = Payment.objects.get(id=result.payment_id)
    event = OutboxEvent.objects.get(
        idempotency_key="payment-initiation:init-outbox-failure-001"
    )

    assert first_dispatch.failed == 1
    assert payment.status == Payment.Status.PENDING
    assert event.status == OutboxEvent.Status.FAILED
    assert event.last_error == "provider unavailable"

    event.available_at = event.created_at
    event.save(update_fields=["available_at"])

    succeeding_provider = make_provider()
    second_dispatch = dispatch_outbox_events(
        {
            PAYMENT_INITIATION_REQUESTED_EVENT: make_payment_initiation_outbox_handler(
                succeeding_provider
            )
        },
        limit=1,
    )

    payment.refresh_from_db()
    event.refresh_from_db()

    assert second_dispatch.completed == 1
    assert event.status == OutboxEvent.Status.COMPLETED
    assert payment.provider_metadata["checkout_url"] == "https://checkout.example/payment"
    assert payment.provider_metadata["access_code"] == "access-001"


@pytest.mark.django_db
def test_payment_initiation_retry_after_failed_event_requeues_same_event():
    sale = make_pending_sale()
    failing_provider = make_provider(fail=True)

    first = request_external_payment_initialization(
        sale_id=sale.sale_id,
        customer_email="customer@example.com",
        provider=failing_provider,
        idempotency_key="init-outbox-requeue-001",
    )

    dispatch_outbox_events(
        {
            PAYMENT_INITIATION_REQUESTED_EVENT: make_payment_initiation_outbox_handler(
                failing_provider
            )
        },
        limit=1,
    )

    event = OutboxEvent.objects.get(
        idempotency_key="payment-initiation:init-outbox-requeue-001"
    )
    event.available_at = event.created_at
    event.save(update_fields=["available_at"])

    succeeding_provider = make_provider()
    second = request_external_payment_initialization(
        sale_id=sale.sale_id,
        customer_email="customer@example.com",
        provider=succeeding_provider,
        idempotency_key="init-outbox-requeue-001",
    )

    refreshed_event = OutboxEvent.objects.get(id=event.id)

    assert second.payment_id == first.payment_id
    assert OutboxEvent.objects.filter(
        idempotency_key="payment-initiation:init-outbox-requeue-001"
    ).count() == 1
    assert refreshed_event.status == OutboxEvent.Status.PENDING
