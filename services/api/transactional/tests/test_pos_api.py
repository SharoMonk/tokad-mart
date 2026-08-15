import json

import pytest
from django.test import Client

from transactional.models import (
    AuditEvent,
    InventoryItem,
    InventoryMovement,
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


@pytest.mark.django_db
def test_pos_cash_sale_endpoint_completes_sale():
    client = Client()
    product = make_product()

    response = client.post(
        "/api/transactional/pos/sales/",
        data=json.dumps(
            {
                "lines": [
                    {
                        "product_id": product.id,
                        "quantity": 2,
                    }
                ],
                "location_code": "MAIN",
                "currency": "NGN",
                "amount_minor": 2000,
                "sale_idempotency_key": "api-sale-001",
                "payment_idempotency_key": "api-payment-001",
                "provider_reference": "API-POS-001",
            }
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

    assert Sale.objects.count() == 1
    assert SaleLine.objects.count() == 1
    assert Payment.objects.count() == 1
    assert InventoryMovement.objects.count() == 1
    assert InventoryItem.objects.get(product=product).quantity == 3
    assert AuditEvent.objects.count() == 2


@pytest.mark.django_db
def test_pos_cash_sale_endpoint_retry_is_idempotent():
    client = Client()
    product = make_product()

    payload = {
        "lines": [
            {
                "product_id": product.id,
                "quantity": 2,
            }
        ],
        "location_code": "MAIN",
        "currency": "NGN",
        "amount_minor": 2000,
        "sale_idempotency_key": "api-retry-sale-001",
        "payment_idempotency_key": "api-retry-payment-001",
        "provider_reference": "API-POS-RETRY-001",
    }

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
    client = Client()

    response = client.post(
        "/api/transactional/pos/sales/",
        data=json.dumps(
            {
                "lines": [],
            }
        ),
        content_type="application/json",
    )

    assert response.status_code == 400

    payload = response.json()

    assert payload["error"] == "invalid_request"


@pytest.mark.django_db
def test_pos_cash_sale_endpoint_rejects_invalid_json():
    client = Client()

    response = client.post(
        "/api/transactional/pos/sales/",
        data="{invalid",
        content_type="application/json",
    )

    assert response.status_code == 400

    assert response.json()["error"] == "invalid_json"


@pytest.mark.django_db
def test_pos_cash_sale_endpoint_rejects_amount_mismatch():
    client = Client()
    product = make_product()

    response = client.post(
        "/api/transactional/pos/sales/",
        data=json.dumps(
            {
                "lines": [
                    {
                        "product_id": product.id,
                        "quantity": 1,
                    }
                ],
                "location_code": "MAIN",
                "currency": "NGN",
                "amount_minor": 999,
                "sale_idempotency_key": "api-amount-sale-001",
                "payment_idempotency_key": "api-amount-payment-001",
                "provider_reference": "API-POS-AMOUNT-001",
            }
        ),
        content_type="application/json",
    )

    assert response.status_code == 409

    assert response.json()["error"] == "payment_error"

    assert Sale.objects.count() == 0
    assert Payment.objects.count() == 0
    assert InventoryMovement.objects.count() == 0
    assert InventoryItem.objects.get(product=product).quantity == 5
    
from unittest.mock import patch

from django.test import Client


@pytest.mark.django_db
def test_pos_cash_sale_endpoint_returns_404_for_missing_product():
    client = Client()

    response = client.post(
        "/api/transactional/pos/sales/",
        data=json.dumps(
            {
                "lines": [
                    {
                        "product_id": 999999,
                        "quantity": 1,
                    }
                ],
                "location_code": "MAIN",
                "currency": "NGN",
                "amount_minor": 1000,
                "sale_idempotency_key": "api-missing-product-sale",
                "payment_idempotency_key": "api-missing-product-payment",
                "provider_reference": "API-MISSING-PRODUCT",
            }
        ),
        content_type="application/json",
    )

    assert response.status_code == 404
    assert response.json()["error"] == "product_unavailable"


@pytest.mark.django_db
def test_pos_cash_sale_endpoint_returns_409_for_insufficient_stock():
    client = Client()
    product = make_product(quantity=1)

    response = client.post(
        "/api/transactional/pos/sales/",
        data=json.dumps(
            {
                "lines": [
                    {
                        "product_id": product.id,
                        "quantity": 2,
                    }
                ],
                "location_code": "MAIN",
                "currency": "NGN",
                "amount_minor": 2000,
                "sale_idempotency_key": "api-stock-sale",
                "payment_idempotency_key": "api-stock-payment",
                "provider_reference": "API-STOCK",
            }
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
    client = Client()
    product = make_product()

    with patch(
        "transactional.views.process_pos_cash_sale",
        side_effect=RuntimeError("unexpected internal failure"),
    ):
        response = client.post(
            "/api/transactional/pos/sales/",
            data=json.dumps(
                {
                    "lines": [
                        {
                            "product_id": product.id,
                            "quantity": 1,
                        }
                    ],
                    "location_code": "MAIN",
                    "currency": "NGN",
                    "amount_minor": 1000,
                    "sale_idempotency_key": "api-500-sale",
                    "payment_idempotency_key": "api-500-payment",
                    "provider_reference": "API-500",
                }
            ),
            content_type="application/json",
        )

    assert response.status_code == 500
    assert response.json() == {
        "error": "internal_error",
        "message": "POS sale could not be completed",
    }