from django.urls import path

from .views import (
    health,
    initiate_paystack_payment,
    paystack_webhook,
    pos_cash_sale,
    reconcile_payment_endpoint,
    refund_payment,
)


urlpatterns = [
    path(
        "health/",
        health,
        name="transactional-health",
    ),
    path(
        "pos/sales/",
        pos_cash_sale,
        name="pos-cash-sale",
    ),
    path(
        "payments/paystack/initialize/",
        initiate_paystack_payment,
        name="paystack-payment-initiate",
    ),
    path(
        "payments/refund/",
        refund_payment,
        name="payment-refund",
    ),
    path(
        "payments/reconcile/",
        reconcile_payment_endpoint,
        name="payment-reconcile",
    ),
    path(
        "webhooks/paystack/",
        paystack_webhook,
        name="paystack-webhook",
    ),
]
