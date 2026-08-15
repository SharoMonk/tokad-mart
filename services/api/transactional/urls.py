from django.urls import path

from .views import (
    health,
    initiate_paystack_payment,
    paystack_webhook,
    pos_cash_sale,
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
        "webhooks/paystack/",
        paystack_webhook,
        name="paystack-webhook",
    ),
]
