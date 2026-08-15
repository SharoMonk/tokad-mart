import pytest
from django.contrib.auth import get_user_model

from transactional.exceptions import PaymentNotFoundError
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
)
from transactional.payment_providers import (
    PaymentProviderError,
    VerifiedPayment,
    validate_verified_payment,
)
from transactional.payment_services import (
    create_pending_sale,
    record_successful_payment,
)
from transactional.payment_webhooks import (
    PaymentWebhookError,
    process_payment_webhook,
)
from transactional.services import CheckoutLine


@pytest.fixture
def payment_setup(db):
    product = Product.objects.create(
        sku="SKU-WEBHOOK-001",
        name="Webhook Product",
        currency="NGN",
        unit_price_minor=1000,
    )
    InventoryItem.objects.create(
        product=product,
        location_code="MAIN",
        quantity=5,
    )

    sale = create_pending_sale(
        lines=[CheckoutLine(product_id=product.id, quantity=1)],
        location_code="MAIN",
        currency="NGN",
        idempotency_key="webhook-sale-001",
    )

    payment = record_successful_payment(
        sale_id=sale.sale_id,
        amount_minor=1000,
        currency="NGN",
        method=Payment.Method.EXTERNAL,
        provider="TEST",
        provider_reference="TEST-PAY-001",
        idempotency_key="webhook-payment-001",
    )

    return product, sale, payment


@pytest.mark.django_db
def test_validate_verified_payment_accepts_matching_success():
    validate_verified_payment(
        expected_amount_minor=1000,
        expected_currency="NGN",
        verified=VerifiedPayment(
            provider="TEST",
            provider_reference="TEST-PAY-001",
            amount_minor=1000,
            currency="NGN",
            succeeded=True,
        ),
    )


@pytest.mark.django_db
def test_validate_verified_payment_rejects_failed_payment():
    with pytest.raises(PaymentProviderError, match="not successful"):
        validate_verified_payment(
            expected_amount_minor=1000,
            expected_currency="NGN",
            verified=VerifiedPayment(
                provider="TEST",
                provider_reference="TEST-PAY-001",
                amount_minor=1000,
                currency="NGN",
                succeeded=False,
            ),
        )


@pytest.mark.django_db
def test_process_payment_webhook_is_idempotent(payment_setup):
    product, sale, payment = payment_setup

    # The helper above records the payment as SUCCEEDED. Reset it to the
    # state expected for provider confirmation.
    Payment.objects.filter(pk=payment.payment_id).update(
        status=Payment.Status.PENDING,
    )

    verified = VerifiedPayment(
        provider="TEST",
        provider_reference="TEST-PAY-001",
        amount_minor=1000,
        currency="NGN",
        succeeded=True,
    )

    first = process_payment_webhook(
        provider="TEST",
        event_id="evt-001",
        provider_reference="TEST-PAY-001",
        verified=verified,
    )
    second = process_payment_webhook(
        provider="TEST",
        event_id="evt-001",
        provider_reference="TEST-PAY-001",
        verified=verified,
    )

    assert first.already_processed is False
    assert second.already_processed is True
    assert first.payment_id == second.payment_id == payment.payment_id
    assert Payment.objects.get(pk=payment.payment_id).status == Payment.Status.SUCCEEDED
    assert Sale.objects.get(pk=sale.sale_id).status == Sale.Status.COMPLETED
    assert InventoryItem.objects.get(product=product).quantity == 4
    assert InventoryMovement.objects.count() == 1
    assert PaymentWebhookEvent.objects.count() == 1


@pytest.mark.django_db
def test_process_payment_webhook_rejects_unknown_payment():
    verified = VerifiedPayment(
        provider="TEST",
        provider_reference="UNKNOWN",
        amount_minor=1000,
        currency="NGN",
        succeeded=True,
    )

    with pytest.raises(PaymentNotFoundError):
        process_payment_webhook(
            provider="TEST",
            event_id="evt-unknown",
            provider_reference="UNKNOWN",
            verified=verified,
        )


@pytest.mark.django_db
def test_process_payment_webhook_rejects_provider_reference_mismatch(payment_setup):
    _, _, payment = payment_setup
    Payment.objects.filter(pk=payment.payment_id).update(status=Payment.Status.PENDING)

    verified = VerifiedPayment(
        provider="TEST",
        provider_reference="OTHER-REFERENCE",
        amount_minor=1000,
        currency="NGN",
        succeeded=True,
    )

    with pytest.raises(PaymentWebhookError, match="reference"):
        process_payment_webhook(
            provider="TEST",
            event_id="evt-mismatch",
            provider_reference="TEST-PAY-001",
            verified=verified,
        )


@pytest.mark.django_db
def test_process_payment_webhook_rejects_amount_mismatch(payment_setup):
    _, _, payment = payment_setup
    Payment.objects.filter(pk=payment.payment_id).update(status=Payment.Status.PENDING)

    verified = VerifiedPayment(
        provider="TEST",
        provider_reference="TEST-PAY-001",
        amount_minor=900,
        currency="NGN",
        succeeded=True,
    )

    with pytest.raises(PaymentWebhookError, match="amount"):
        process_payment_webhook(
            provider="TEST",
            event_id="evt-amount-mismatch",
            provider_reference="TEST-PAY-001",
            verified=verified,
        )


@pytest.mark.django_db
def test_process_payment_webhook_rejects_terminal_payment_state(payment_setup):
    _, sale, payment = payment_setup

    with pytest.raises(PaymentWebhookError, match="SUCCEEDED"):
        process_payment_webhook(
            provider="TEST",
            event_id="evt-completed",
            provider_reference="TEST-PAY-001",
            verified=VerifiedPayment(
                provider="TEST",
                provider_reference="TEST-PAY-001",
                amount_minor=1000,
                currency="NGN",
                succeeded=True,
            ),
        )

    assert Payment.objects.get(pk=payment.payment_id).status == Payment.Status.SUCCEEDED
    assert Sale.objects.get(pk=sale.sale_id).status == Sale.Status.PENDING_PAYMENT
    assert PaymentWebhookEvent.objects.count() == 0
