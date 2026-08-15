import json
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from transactional.models import (
    AuditEvent,
    InventoryItem,
    InventoryMovement,
    POSLocation,
    POSOperator,
    POSOperatorLocation,
    POSOperatorTerminal,
    POSTerminal,
    Payment,
    Product,
    Sale,
    SaleLine,
)


def make_product(*, quantity=5):
    product = Product.objects.create(
        sku="SKU-POS-API-001",
        name="POS API Product",
        currency="NGN",
        unit_price_minor=1000,
    )

    InventoryItem.objects.create(
        product=product,
        location_code="MAIN",
        quantity=quantity,
    )

    return product


def authenticated_pos_client(*, location_code="MAIN", terminal_code="MAIN-01"):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="pos-operator",
        password="test-password",
        is_staff=True,
    )

    location = POSLocation.objects.create(
        code=location_code,
        name="Main Store",
    )
    terminal = POSTerminal.objects.create(
        location=location,
        code=terminal_code,
        name="Main Terminal 01",
    )

    operator = POSOperator.objects.create(user=user)
    POSOperatorLocation.objects.create(
        operator=operator,
        location=location,
    )
    POSOperatorTerminal.objects.create(
        operator=operator,
        terminal=terminal,
    )

    client = Client()
    client.force_login(user)

    return client


def authorized_payload(**overrides):
    payload = {
        "lines": [],
        "location_code": "MAIN",
        "terminal_code": "MAIN-01",
        "currency": "NGN",
        "amount_minor": 1000,
        "sale_idempotency_key": "api-sale-default",
        "payment_idempotency_key": "api-payment-default",
        "provider_reference": "API-POS-DEFAULT",
    }
    payload.update(overrides)
    return payload


@pytest.mark.django_db
def test_pos_cash_sale_endpoint_completes_sale():
    client = authenticated_pos_client()
    product = make_product()

    response = client.post(
        "/api/transactional/pos/sales/",
        data=json.dumps(
            authorized_payload(
                lines=[{"product_id": product.id, "quantity": 2}],
                amount_minor=2000,
                sale_idempotency_key="api-sale-001",
                payment_idempotency_key="api-payment-001",
                provider_reference="API-POS-001",
            )
        ),
        content_type="application/json",
    )

    assert response.status_code == 201

    payload = response.json()
    assert payload["sale_id"] > 0
    assert payload["payment_id"] > 0
    assert payload["total_minor"] == 2000
    assert payload["currency"] == "NGN"
    assert payload["sale_status"] == Sale.Status.COMPLETED
    assert payload["payment_status"] == Payment.Status.SUCCEEDED
    assert payload["terminal_code"] == "MAIN-01"

    assert Sale.objects.count() == 1
    assert SaleLine.objects.count() == 1
    assert Payment.objects.count() == 1
    assert InventoryMovement.objects.count() == 1
    assert InventoryItem.objects.get(product=product).quantity == 3
    assert AuditEvent.objects.count() == 2


@pytest.mark.django_db
def test_pos_cash_sale_endpoint_retry_is_idempotent():
    client = authenticated_pos_client()
    product = make_product()

    payload = authorized_payload(
        lines=[{"product_id": product.id, "quantity": 2}],
        amount_minor=2000,
        sale_idempotency_key="api-retry-sale-001",
        payment_idempotency_key="api-retry-payment-001",
        provider_reference="API-POS-RETRY-001",
    )

    first = client.post(
        "/api/transactional/pos/sales/",
        data=json.dumps(payload),
        content_type="application/json",
    )
    second = client.post(
        "/api/transactional/pos/sales/",
        data=json.dumps(payload),
        content_type="application/json",
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json() == second.json()
    assert Sale.objects.count() == 1
    assert Payment.objects.count() == 1
    assert SaleLine.objects.count() == 1
    assert InventoryMovement.objects.count() == 1
    assert InventoryItem.objects.get(product=product).quantity == 3


@pytest.mark.django_db
def test_pos_cash_sale_endpoint_rejects_missing_fields():
    client = authenticated_pos_client()

    response = client.post(
        "/api/transactional/pos/sales/",
        data=json.dumps({"lines": []}),
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.json()["error"] == "invalid_request"


@pytest.mark.django_db
def test_pos_cash_sale_endpoint_rejects_invalid_json():
    client = authenticated_pos_client()

    response = client.post(
        "/api/transactional/pos/sales/",
        data="{invalid",
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.json()["error"] == "invalid_json"


@pytest.mark.django_db
def test_pos_cash_sale_endpoint_rejects_amount_mismatch():
    client = authenticated_pos_client()
    product = make_product()

    response = client.post(
        "/api/transactional/pos/sales/",
        data=json.dumps(
            authorized_payload(
                lines=[{"product_id": product.id, "quantity": 1}],
                amount_minor=999,
                sale_idempotency_key="api-amount-sale-001",
                payment_idempotency_key="api-amount-payment-001",
                provider_reference="API-POS-AMOUNT-001",
            )
        ),
        content_type="application/json",
    )

    assert response.status_code == 409
    assert response.json()["error"] == "payment_error"
    assert Sale.objects.count() == 0
    assert Payment.objects.count() == 0
    assert InventoryMovement.objects.count() == 0
    assert InventoryItem.objects.get(product=product).quantity == 5


@pytest.mark.django_db
def test_pos_cash_sale_endpoint_returns_404_for_missing_product():
    client = authenticated_pos_client()

    response = client.post(
        "/api/transactional/pos/sales/",
        data=json.dumps(
            authorized_payload(
                lines=[{"product_id": 999999, "quantity": 1}],
                sale_idempotency_key="api-missing-product-sale",
                payment_idempotency_key="api-missing-product-payment",
                provider_reference="API-MISSING-PRODUCT",
            )
        ),
        content_type="application/json",
    )

    assert response.status_code == 404
    assert response.json()["error"] == "product_unavailable"


@pytest.mark.django_db
def test_pos_cash_sale_endpoint_returns_409_for_insufficient_stock():
    client = authenticated_pos_client()
    product = make_product(quantity=1)

    response = client.post(
        "/api/transactional/pos/sales/",
        data=json.dumps(
            authorized_payload(
                lines=[{"product_id": product.id, "quantity": 2}],
                amount_minor=2000,
                sale_idempotency_key="api-stock-sale",
                payment_idempotency_key="api-stock-payment",
                provider_reference="API-STOCK",
            )
        ),
        content_type="application/json",
    )

    assert response.status_code == 409
    assert response.json()["error"] == "insufficient_stock"
    assert Sale.objects.count() == 0
    assert Payment.objects.count() == 0
    assert InventoryItem.objects.get(product=product).quantity == 1


@pytest.mark.django_db
def test_pos_cash_sale_endpoint_returns_500_for_unexpected_failure():
    client = authenticated_pos_client()
    product = make_product()

    with patch(
        "transactional.views.process_pos_cash_sale",
        side_effect=RuntimeError("unexpected internal failure"),
    ):
        response = client.post(
            "/api/transactional/pos/sales/",
            data=json.dumps(
                authorized_payload(
                    lines=[{"product_id": product.id, "quantity": 1}],
                    sale_idempotency_key="api-500-sale",
                    payment_idempotency_key="api-500-payment",
                    provider_reference="API-500",
                )
            ),
            content_type="application/json",
        )

    assert response.status_code == 500
    assert response.json() == {
        "error": "internal_error",
        "message": "POS sale could not be completed",
    }


@pytest.mark.django_db
def test_pos_cash_sale_requires_authentication():
    client = Client()

    response = client.post(
        "/api/transactional/pos/sales/",
        data="{}",
        content_type="application/json",
    )

    assert response.status_code in {401, 403}


@pytest.mark.django_db
def test_authenticated_non_staff_user_cannot_use_pos():
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="cashier",
        password="test-password",
    )

    client = Client()
    client.force_login(user)

    response = client.post(
        "/api/transactional/pos/sales/",
        data="{}",
        content_type="application/json",
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_staff_user_without_operator_profile_cannot_use_pos():
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="staff-without-pos-profile",
        password="test-password",
        is_staff=True,
    )

    client = Client()
    client.force_login(user)

    response = client.post(
        "/api/transactional/pos/sales/",
        data="{}",
        content_type="application/json",
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_inactive_pos_operator_cannot_use_pos():
    client = authenticated_pos_client()
    user = get_user_model().objects.get(username="pos-operator")
    operator = POSOperator.objects.get(user=user)
    operator.is_active = False
    operator.save(update_fields=["is_active"])

    response = client.post(
        "/api/transactional/pos/sales/",
        data=json.dumps({}),
        content_type="application/json",
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_operator_cannot_use_unassigned_location():
    client = authenticated_pos_client()
    product = make_product()
    other_location = POSLocation.objects.create(
        code="OTHER",
        name="Other Store",
    )

    response = client.post(
        "/api/transactional/pos/sales/",
        data=json.dumps(
            authorized_payload(
                location_code=other_location.code,
                lines=[{"product_id": product.id, "quantity": 1}],
            )
        ),
        content_type="application/json",
    )

    assert response.status_code == 403
    assert response.json()["error"] == "pos_access_denied"


@pytest.mark.django_db
def test_operator_cannot_use_unassigned_terminal():
    client = authenticated_pos_client()
    product = make_product()
    location = POSLocation.objects.get(code="MAIN")
    POSTerminal.objects.create(
        location=location,
        code="MAIN-02",
        name="Main Terminal 02",
    )

    response = client.post(
        "/api/transactional/pos/sales/",
        data=json.dumps(
            authorized_payload(
                terminal_code="MAIN-02",
                lines=[{"product_id": product.id, "quantity": 1}],
            )
        ),
        content_type="application/json",
    )

    assert response.status_code == 403
    assert response.json()["error"] == "pos_access_denied"


@pytest.mark.django_db
def test_operator_cannot_use_terminal_from_another_location():
    client = authenticated_pos_client()
    product = make_product()
    other_location = POSLocation.objects.create(
        code="OTHER",
        name="Other Store",
    )
    other_terminal = POSTerminal.objects.create(
        location=other_location,
        code="OTHER-01",
        name="Other Terminal 01",
    )

    response = client.post(
        "/api/transactional/pos/sales/",
        data=json.dumps(
            authorized_payload(
                terminal_code=other_terminal.code,
                lines=[{"product_id": product.id, "quantity": 1}],
            )
        ),
        content_type="application/json",
    )

    assert response.status_code == 403
    assert response.json()["error"] == "pos_access_denied"


@pytest.mark.django_db
def test_inactive_location_is_rejected():
    client = authenticated_pos_client()
    product = make_product()
    location = POSLocation.objects.get(code="MAIN")
    location.is_active = False
    location.save(update_fields=["is_active"])

    response = client.post(
        "/api/transactional/pos/sales/",
        data=json.dumps(
            authorized_payload(
                lines=[{"product_id": product.id, "quantity": 1}],
            )
        ),
        content_type="application/json",
    )

    assert response.status_code == 403
    assert response.json()["error"] == "pos_access_denied"


@pytest.mark.django_db
def test_inactive_terminal_is_rejected():
    client = authenticated_pos_client()
    product = make_product()
    terminal = POSTerminal.objects.get(code="MAIN-01")
    terminal.is_active = False
    terminal.save(update_fields=["is_active"])

    response = client.post(
        "/api/transactional/pos/sales/",
        data=json.dumps(
            authorized_payload(
                lines=[{"product_id": product.id, "quantity": 1}],
            )
        ),
        content_type="application/json",
    )

    assert response.status_code == 403
    assert response.json()["error"] == "pos_access_denied"
