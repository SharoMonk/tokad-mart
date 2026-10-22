from django.urls import path

from .payment_initiation_api import initiate_paystack_payment
from .pos_read_api import pos_catalog, pos_receipt, pos_scope, pos_barcode
from .shift_api import cashier_shifts, cashier_shift_close
from .supervisor_review_api import supervisor_reconciliation
from .session_api import pos_session, pos_login, pos_logout
from .shift_sales_api import shift_cash_sale
from .views import (
    health,
    paystack_webhook,
    pos_cash_sale,
    reconcile_payment_endpoint,
    refund_payment,
)


urlpatterns = [
    path("pos/barcode/", pos_barcode, name="pos-barcode"),
    path("pos/shifts/<int:shift_id>/review/", supervisor_reconciliation, name="supervisor-shift-review"),
    path("pos/shift-sales/", shift_cash_sale, name="pos-shift-cash-sale"),
    path("pos/session/", pos_session, name="pos-session"),
    path("pos/login/", pos_login, name="pos-login"),
    path("pos/logout/", pos_logout, name="pos-logout"),
    path("pos/shifts/", cashier_shifts, name="cashier-shifts"),
    path("pos/shifts/<int:shift_id>/close/", cashier_shift_close, name="cashier-shift-close"),
    path("pos/scope/", pos_scope, name="pos-scope"),
    path("pos/catalog/", pos_catalog, name="pos-catalog"),
    path("pos/sales/<int:sale_id>/receipt/", pos_receipt, name="pos-receipt"),
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
