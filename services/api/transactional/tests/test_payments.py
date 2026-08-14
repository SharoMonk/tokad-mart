import pytest
from django.db import IntegrityError
from unittest.mock import patch

from transactional.models import (
    AuditEvent,
    IdempotencyRecord,
    InventoryItem,
    InventoryMovement,
    Payment,
    Product,
    Sale,
    SaleLine,
)
from transactional.payment_services import (
    PaymentError,
    create_pending_sale,
    finalize_paid_sale,
    process_pos_cash_sale,
    record_successful_payment,
)
from transactional.services import CheckoutLine


def make_product(*, sku="SKU-PAY-001", price=1000, quantity=5):
    product = Product.objects.create(
        sku=sku,
        name="Payment Product",
        currency="NGN",
        unit_price_minor=price,
    )
    InventoryItem.objects.create(
        product=product,
        location_code="MAIN",
        quantity=quantity,
    )
    return product


@pytest.mark.django_db
def test_pos_cash_sale_completes_sale_and_payment():
    product = make_product()

    result = process_pos_cash_sale(
        lines=[CheckoutLine(product_id=product.id, quantity=2)],
        location_code="MAIN",
        currency="NGN",
        amount_minor=2000,
        sale_idempotency_key="pos-sale-001",
        payment_idempotency_key="pos-payment-001",
        provider_reference="POS-CASH-001",
    )

    sale = Sale.objects.get(id=result.sale_id)
    payment = Payment.objects.get(id=result.payment_id)

    assert sale.status == Sale.Status.COMPLETED
    assert payment.status == Payment.Status.SUCCEEDED
    assert payment.method == Payment.Method.CASH
    assert payment.amount_minor == 2000
    assert InventoryItem.objects.get(product=product).quantity == 3
    assert SaleLine.objects.count() == 1
    assert InventoryMovement.objects.count() == 1
    assert AuditEvent.objects.count() == 2


@pytest.mark.django_db
def test_pos_cash_sale_retry_returns_same_result():
    product = make_product()
    kwargs = dict(
        lines=[CheckoutLine(product_id=product.id, quantity=2)],
        location_code="MAIN",
        currency="NGN",
        amount_minor=2000,
        sale_idempotency_key="pos-sale-retry-001",
        payment_idempotency_key="pos-payment-retry-001",
        provider_reference="POS-CASH-RETRY-001",
    )

    first = process_pos_cash_sale(**kwargs)
    second = process_pos_cash_sale(**kwargs)

    assert first == second
    assert Sale.objects.count() == 1
    assert Payment.objects.count() == 1
    assert SaleLine.objects.count() == 1
    assert InventoryMovement.objects.count() == 1
    assert InventoryItem.objects.get(product=product).quantity == 3


@pytest.mark.django_db
def test_payment_amount_mismatch_rolls_back_pending_sale():
    product = make_product()

    with pytest.raises(PaymentError, match="payment amount"):
        process_pos_cash_sale(
            lines=[CheckoutLine(product_id=product.id, quantity=1)],
            location_code="MAIN",
            currency="NGN",
            amount_minor=999,
            sale_idempotency_key="pos-sale-002",
            payment_idempotency_key="pos-payment-002",
            provider_reference="POS-CASH-002",
        )

    assert Sale.objects.count() == 0
    assert SaleLine.objects.count() == 0
    assert Payment.objects.count() == 0
    assert IdempotencyRecord.objects.count() == 0
    assert InventoryMovement.objects.count() == 0
    assert InventoryItem.objects.get(product=product).quantity == 5


@pytest.mark.django_db
def test_payment_idempotency_returns_existing_payment():
    product = make_product()
    sale = create_pending_sale(
        lines=[CheckoutLine(product_id=product.id, quantity=1)],
        location_code="MAIN",
        currency="NGN",
        idempotency_key="sale-payment-idempotency-001",
    )

    first = record_successful_payment(
        sale_id=sale.sale_id,
        amount_minor=1000,
        currency="NGN",
        method=Payment.Method.CASH,
        provider="POS",
        provider_reference="POS-CASH-003",
        idempotency_key="payment-idempotency-001",
    )
    second = record_successful_payment(
        sale_id=sale.sale_id,
        amount_minor=1000,
        currency="NGN",
        method=Payment.Method.CASH,
        provider="POS",
        provider_reference="POS-CASH-003",
        idempotency_key="payment-idempotency-001",
    )

    assert first == second
    assert Payment.objects.count() == 1


@pytest.mark.django_db
def test_payment_idempotency_key_cannot_change_request():
    product = make_product()
    sale = create_pending_sale(
        lines=[CheckoutLine(product_id=product.id, quantity=1)],
        location_code="MAIN",
        currency="NGN",
        idempotency_key="sale-payment-idempotency-002",
    )

    record_successful_payment(
        sale_id=sale.sale_id,
        amount_minor=1000,
        currency="NGN",
        method=Payment.Method.CASH,
        provider="POS",
        provider_reference="POS-CASH-004",
        idempotency_key="payment-idempotency-002",
    )

    with pytest.raises(PaymentError, match="different request"):
        record_successful_payment(
            sale_id=sale.sale_id,
            amount_minor=900,
            currency="NGN",
            method=Payment.Method.CASH,
            provider="POS",
            provider_reference="POS-CASH-005",
            idempotency_key="payment-idempotency-002",
        )

    assert Payment.objects.count() == 1


@pytest.mark.django_db
def test_finalize_paid_sale_rechecks_inventory():
    product = make_product(quantity=1)
    sale = create_pending_sale(
        lines=[CheckoutLine(product_id=product.id, quantity=1)],
        location_code="MAIN",
        currency="NGN",
        idempotency_key="sale-payment-inventory-001",
    )

    payment = record_successful_payment(
        sale_id=sale.sale_id,
        amount_minor=1000,
        currency="NGN",
        method=Payment.Method.CASH,
        provider="POS",
        provider_reference="POS-CASH-006",
        idempotency_key="payment-inventory-001",
    )

    InventoryItem.objects.filter(product=product).update(quantity=0)

    with pytest.raises(PaymentError, match="insufficient stock"):
        finalize_paid_sale(
            sale_id=sale.sale_id,
            payment_id=payment.payment_id,
        )

    assert Sale.objects.get(id=sale.sale_id).status == Sale.Status.PENDING_PAYMENT
    assert Payment.objects.get(id=payment.payment_id).status == Payment.Status.SUCCEEDED
    assert InventoryMovement.objects.count() == 0


@pytest.mark.django_db
def test_finalize_paid_sale_rolls_back_inventory_movement_failure():
    product = make_product(quantity=5)
    sale = create_pending_sale(
        lines=[CheckoutLine(product_id=product.id, quantity=2)],
        location_code="MAIN",
        currency="NGN",
        idempotency_key="sale-payment-rollback-001",
    )

    payment = record_successful_payment(
        sale_id=sale.sale_id,
        amount_minor=2000,
        currency="NGN",
        method=Payment.Method.CASH,
        provider="POS",
        provider_reference="POS-CASH-007",
        idempotency_key="payment-rollback-001",
    )

    with patch(
        "transactional.payment_services.InventoryMovement.objects.create",
        side_effect=RuntimeError("simulated movement failure"),
    ):
        with pytest.raises(RuntimeError, match="simulated movement failure"):
            finalize_paid_sale(
                sale_id=sale.sale_id,
                payment_id=payment.payment_id,
            )

    assert Sale.objects.get(id=sale.sale_id).status == Sale.Status.PENDING_PAYMENT
    assert InventoryItem.objects.get(product=product).quantity == 5
    assert InventoryMovement.objects.count() == 0


@pytest.mark.django_db
def test_duplicate_provider_reference_is_rejected():
    product = make_product()
    sale_one = create_pending_sale(
        lines=[CheckoutLine(product_id=product.id, quantity=1)],
        location_code="MAIN",
        currency="NGN",
        idempotency_key="sale-provider-ref-001",
    )
    sale_two = create_pending_sale(
        lines=[CheckoutLine(product_id=product.id, quantity=1)],
        location_code="MAIN",
        currency="NGN",
        idempotency_key="sale-provider-ref-002",
    )

    record_successful_payment(
        sale_id=sale_one.sale_id,
        amount_minor=1000,
        currency="NGN",
        method=Payment.Method.CASH,
        provider="POS",
        provider_reference="POS-CASH-DUPLICATE",
        idempotency_key="payment-provider-ref-001",
    )

    with pytest.raises(IntegrityError):
        record_successful_payment(
            sale_id=sale_two.sale_id,
            amount_minor=1000,
            currency="NGN",
            method=Payment.Method.CASH,
            provider="POS",
            provider_reference="POS-CASH-DUPLICATE",
            idempotency_key="payment-provider-ref-002",
        )

    assert Payment.objects.count() == 1
