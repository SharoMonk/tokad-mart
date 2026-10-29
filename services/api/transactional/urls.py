from django.urls import path

from .payment_initiation_api import initiate_paystack_payment
from .pos_read_api import pos_catalog, pos_receipt, pos_scope, pos_barcode
from .shift_api import cashier_shifts, cashier_shift_close
from .supervisor_review_api import supervisor_reconciliation
from .supervisor_catalog_api import supervisor_product_create, supervisor_product_barcodes
from .supervisor_inventory_api import supervisor_stock_operation, supervisor_inventory_report
from .supervisor_procurement_api import suppliers, purchase_orders, purchase_order_detail, receive_purchase_order, replenishment_report
from .procurement_approval_api import approve_purchase_order, supplier_invoices, accounts_payable_register
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
    path("pos/manage/purchase-orders/<int:order_id>/approve/", approve_purchase_order, name="po-approve"),
    path("pos/manage/supplier-invoices/", supplier_invoices, name="supplier-invoices"),
    path("pos/manage/accounts-payable/", accounts_payable_register, name="accounts-payable-register"),
    path("pos/manage/suppliers/", suppliers, name="pos-suppliers"),
    path("pos/manage/purchase-orders/", purchase_orders, name="pos-purchase-orders"),
    path("pos/manage/purchase-orders/<int:order_id>/", purchase_order_detail, name="pos-purchase-order-detail"),
    path("pos/manage/purchase-orders/<int:order_id>/receive/", receive_purchase_order, name="pos-purchase-order-receive"),
    path("pos/manage/replenishment/", replenishment_report, name="pos-replenishment-report"),
    path("pos/manage/inventory-report/", supervisor_inventory_report, name="supervisor-inventory-report"),
    path("pos/manage/stock/", supervisor_stock_operation, name="supervisor-stock-operation"),
    path("pos/manage/products/", supervisor_product_create, name="supervisor-product-create"),
    path("pos/manage/products/<int:product_id>/barcodes/", supervisor_product_barcodes, name="supervisor-product-barcodes"),
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
