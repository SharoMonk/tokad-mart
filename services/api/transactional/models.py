from django.conf import settings
from django.db import models


class Product(models.Model):
    sku = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=255)
    currency = models.CharField(max_length=3, default="NGN")
    unit_price_minor = models.PositiveBigIntegerField()
    is_active = models.BooleanField(default=True)


class ProductBarcode(models.Model):
    """One physical barcode maps to one canonical product; preserve leading zeros."""
    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name="barcodes"
    )
    code = models.CharField(max_length=64, unique=True)

    def __str__(self):
        return self.code


class InventoryItem(models.Model):
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="inventory_items")
    location_code = models.CharField(max_length=64)
    quantity = models.BigIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["product", "location_code"], name="uniq_inventory_product_location"),
        ]


class Customer(models.Model):
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=32, blank=True)


class POSLocation(models.Model):
    code = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)


class POSTerminal(models.Model):
    location = models.ForeignKey(POSLocation, on_delete=models.PROTECT, related_name="terminals")
    code = models.CharField(max_length=64)
    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["location", "code"], name="uniq_pos_terminal_location_code"),
        ]


class POSOperator(models.Model):
    class Role(models.TextChoices):
        OPERATOR = "OPERATOR"
        SUPERVISOR = "SUPERVISOR"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="pos_operator")
    role = models.CharField(max_length=32, choices=Role.choices, default=Role.OPERATOR)
    is_active = models.BooleanField(default=True)
    locations = models.ManyToManyField(POSLocation, through="POSOperatorLocation", related_name="operators")
    terminals = models.ManyToManyField(POSTerminal, through="POSOperatorTerminal", related_name="operators")


class POSOperatorLocation(models.Model):
    operator = models.ForeignKey(POSOperator, on_delete=models.CASCADE, related_name="location_assignments")
    location = models.ForeignKey(POSLocation, on_delete=models.CASCADE, related_name="operator_assignments")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["operator", "location"], name="uniq_pos_operator_location"),
        ]


class POSOperatorTerminal(models.Model):
    operator = models.ForeignKey(POSOperator, on_delete=models.CASCADE, related_name="terminal_assignments")
    terminal = models.ForeignKey(POSTerminal, on_delete=models.CASCADE, related_name="operator_assignments")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["operator", "terminal"], name="uniq_pos_operator_terminal"),
        ]


class CashierShift(models.Model):
    class Status(models.TextChoices):
        OPEN = "OPEN"
        CLOSED = "CLOSED"

    operator = models.ForeignKey(POSOperator, on_delete=models.PROTECT, related_name="cashier_shifts")
    location = models.ForeignKey(POSLocation, on_delete=models.PROTECT)
    terminal = models.ForeignKey(POSTerminal, on_delete=models.PROTECT)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.OPEN)
    opening_cash_minor = models.PositiveBigIntegerField(default=0)
    closing_cash_minor = models.PositiveBigIntegerField(null=True, blank=True)
    expected_cash_minor = models.PositiveBigIntegerField(null=True, blank=True)
    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["terminal"],
                condition=models.Q(status="OPEN"),
                name="uniq_open_cashier_shift_per_terminal",
            ),
        ]




class ShiftReconciliationReview(models.Model):
    class Decision(models.TextChoices):
        APPROVED = "APPROVED"
        REJECTED = "REJECTED"

    shift = models.OneToOneField(CashierShift, on_delete=models.PROTECT, related_name="reconciliation_review")
    supervisor = models.ForeignKey(POSOperator, on_delete=models.PROTECT, related_name="shift_reviews")
    decision = models.CharField(max_length=16, choices=Decision.choices)
    notes = models.TextField()
    reviewed_at = models.DateTimeField(auto_now_add=True)

class Sale(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT"
        PENDING_PAYMENT = "PENDING_PAYMENT"
        COMPLETED = "COMPLETED"
        PAYMENT_FAILED = "PAYMENT_FAILED"
        CANCELLED = "CANCELLED"

    shift = models.ForeignKey(CashierShift, null=True, blank=True, on_delete=models.PROTECT, related_name="sales")
    reference = models.UUIDField(unique=True)
    customer = models.ForeignKey(Customer, null=True, blank=True, on_delete=models.PROTECT)
    location_code = models.CharField(max_length=64)
    currency = models.CharField(max_length=3)
    subtotal_minor = models.PositiveBigIntegerField(default=0)
    total_minor = models.PositiveBigIntegerField(default=0)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)


class SaleLine(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.PROTECT, related_name="lines")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    sku_snapshot = models.CharField(max_length=64)
    name_snapshot = models.CharField(max_length=255)
    quantity = models.PositiveBigIntegerField()
    unit_price_minor = models.PositiveBigIntegerField()
    line_total_minor = models.PositiveBigIntegerField()


class Payment(models.Model):
    class Method(models.TextChoices):
        CASH = "CASH"
        CARD = "CARD"
        BANK_TRANSFER = "BANK_TRANSFER"
        MOBILE_MONEY = "MOBILE_MONEY"
        EXTERNAL = "EXTERNAL"

    class Status(models.TextChoices):
        PENDING = "PENDING"
        SUCCEEDED = "SUCCEEDED"
        FAILED = "FAILED"
        CANCELLED = "CANCELLED"
        REFUNDED = "REFUNDED"

    sale = models.ForeignKey(Sale, on_delete=models.PROTECT, related_name="payments")
    provider = models.CharField(max_length=64)
    provider_reference = models.CharField(max_length=255, unique=True)
    idempotency_key = models.CharField(max_length=255, unique=True)
    method = models.CharField(max_length=32, choices=Method.choices)
    amount_minor = models.PositiveBigIntegerField()
    currency = models.CharField(max_length=3)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.PENDING)
    provider_metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)


class PaymentRefund(models.Model):
    class Status(models.TextChoices):
        REQUESTED = "REQUESTED"
        SUCCEEDED = "SUCCEEDED"
        FAILED = "FAILED"

    payment = models.ForeignKey(Payment, on_delete=models.PROTECT, related_name="refunds")
    provider = models.CharField(max_length=64)
    provider_reference = models.CharField(max_length=255)
    provider_refund_reference = models.CharField(max_length=255, unique=True, null=True, blank=True)
    idempotency_key = models.CharField(max_length=255, unique=True)
    amount_minor = models.PositiveBigIntegerField()
    currency = models.CharField(max_length=3)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.REQUESTED)
    provider_metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)


class PaymentWebhookEvent(models.Model):
    provider = models.CharField(max_length=64)
    event_id = models.CharField(max_length=255)
    payment = models.ForeignKey(Payment, on_delete=models.PROTECT, related_name="webhook_events")
    payload = models.JSONField(default=dict)
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "event_id"],
                name="uniq_payment_webhook_provider_event",
            ),
        ]


class OutboxEvent(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING"
        PROCESSING = "PROCESSING"
        COMPLETED = "COMPLETED"
        FAILED = "FAILED"

    event_type = models.CharField(max_length=128)
    aggregate_type = models.CharField(max_length=128)
    aggregate_id = models.CharField(max_length=128)
    idempotency_key = models.CharField(max_length=255, unique=True)
    payload = models.JSONField(default=dict)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.PENDING)
    attempts = models.PositiveIntegerField(default=0)
    available_at = models.DateTimeField()
    locked_until = models.DateTimeField(null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["status", "available_at"], name="transaction_status_c5bc91_idx"),
            models.Index(fields=["aggregate_type", "aggregate_id"], name="transaction_aggrega_c37442_idx"),
        ]


class InventoryMovement(models.Model):
    class Reason(models.TextChoices):
        SALE = "SALE"
        RETURN = "RETURN"
        PURCHASE = "PURCHASE"
        ADJUSTMENT = "ADJUSTMENT"
        TRANSFER_IN = "TRANSFER_IN"
        TRANSFER_OUT = "TRANSFER_OUT"
        DAMAGE = "DAMAGE"

    inventory_item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT, related_name="movements")
    quantity_delta = models.BigIntegerField()
    reason = models.CharField(max_length=32, choices=Reason.choices)
    reference = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class StockOperation(models.Model):
    """Idempotent supervisor stock write linked to the inventory movement."""
    key = models.CharField(max_length=128, unique=True)
    request_fingerprint = models.CharField(max_length=64)
    movement = models.OneToOneField(
        InventoryMovement, on_delete=models.PROTECT, related_name="stock_operation"
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT
    )
    quantity_after = models.BigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)


class IdempotencyRecord(models.Model):
    key = models.CharField(max_length=255, unique=True)
    request_fingerprint = models.CharField(max_length=128)
    response_payload = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)


class Supplier(models.Model):
    code = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=255)
    contact = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)


class PurchaseOrder(models.Model):
    reference = models.CharField(max_length=64, unique=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="orders")
    location = models.ForeignKey(POSLocation, on_delete=models.PROTECT, related_name="purchase_orders")
    created_by = models.ForeignKey(POSOperator, on_delete=models.PROTECT)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class PurchaseOrderLine(models.Model):
    order = models.ForeignKey(PurchaseOrder, on_delete=models.PROTECT, related_name="lines")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity_ordered = models.PositiveIntegerField()
    quantity_received = models.PositiveIntegerField(default=0)
    unit_cost_minor = models.PositiveBigIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["order", "product"], name="uniq_po_order_product")
        ]


class GoodsReceipt(models.Model):
    order = models.ForeignKey(PurchaseOrder, on_delete=models.PROTECT, related_name="receipts")
    reference = models.CharField(max_length=128)
    key = models.CharField(max_length=128, unique=True)
    request_fingerprint = models.CharField(max_length=64)
    received_by = models.ForeignKey(POSOperator, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["order", "reference"], name="uniq_po_receipt_ref")
        ]


class GoodsReceiptLine(models.Model):
    receipt = models.ForeignKey(GoodsReceipt, on_delete=models.PROTECT, related_name="lines")
    order_line = models.ForeignKey(PurchaseOrderLine, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    movement = models.OneToOneField(InventoryMovement, on_delete=models.PROTECT)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["receipt", "order_line"], name="uniq_goods_receipt_line")
        ]


class PurchaseOrderApproval(models.Model):
    """Immutable second-person authorization before PO goods receipts."""
    order = models.OneToOneField(PurchaseOrder, on_delete=models.PROTECT, related_name="approval")
    approved_by = models.ForeignKey(POSOperator, on_delete=models.PROTECT)
    note = models.CharField(max_length=500)
    approved_at = models.DateTimeField(auto_now_add=True)


class SupplierInvoice(models.Model):
    """A reviewed supplier liability, not proof of a payment."""
    class Status(models.TextChoices):
        MATCHED = "MATCHED", "Matched"
        EXCEPTION = "EXCEPTION", "Exception"

    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="invoices")
    receipt = models.OneToOneField(GoodsReceipt, on_delete=models.PROTECT, related_name="supplier_invoice")
    number = models.CharField(max_length=128)
    amount_minor = models.PositiveBigIntegerField()
    expected_minor = models.PositiveBigIntegerField()
    status = models.CharField(max_length=12, choices=Status.choices)
    notes = models.CharField(max_length=1000)
    recorded_by = models.ForeignKey(POSOperator, on_delete=models.PROTECT)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["supplier", "number"], name="uniq_supplier_invoice_number")
        ]


class SupplierPaymentEvidence(models.Model):
    """Manual evidence of a supplier payment; verification is not bank confirmation."""
    class Status(models.TextChoices):
        RECORDED = "RECORDED", "Recorded"
        VERIFIED = "VERIFIED", "Manually verified"

    invoice = models.ForeignKey(SupplierInvoice, on_delete=models.PROTECT, related_name="payment_evidence")
    reference = models.CharField(max_length=128, unique=True)
    idempotency_key = models.CharField(max_length=128, unique=True)
    fingerprint = models.CharField(max_length=64)
    amount_minor = models.PositiveBigIntegerField()
    notes = models.CharField(max_length=1000)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.RECORDED)
    recorded_by = models.ForeignKey(POSOperator, on_delete=models.PROTECT, related_name="supplier_payments_recorded")
    verified_by = models.ForeignKey(POSOperator, on_delete=models.PROTECT, null=True, blank=True, related_name="supplier_payments_verified")
    verification_notes = models.CharField(max_length=1000, blank=True)
    recorded_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)


class StoreExpense(models.Model):
    """Manually recorded operating expense; not a confirmed cash disbursement."""
    location = models.ForeignKey(POSLocation, on_delete=models.PROTECT, related_name="expenses")
    reference = models.CharField(max_length=128, unique=True)
    category = models.CharField(max_length=64)
    description = models.CharField(max_length=500)
    amount_minor = models.PositiveBigIntegerField()
    incurred_on = models.DateField()
    recorded_by = models.ForeignKey(POSOperator, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class ExpenseReview(models.Model):
    expense = models.OneToOneField(StoreExpense, on_delete=models.PROTECT, related_name="review")
    reviewed_by = models.ForeignKey(POSOperator, on_delete=models.PROTECT)
    decision = models.CharField(max_length=12, choices=[("APPROVED", "Approved"), ("REJECTED", "Rejected")])
    notes = models.CharField(max_length=1000)
    reviewed_at = models.DateTimeField(auto_now_add=True)


class ScheduledManagementReport(models.Model):
    class Frequency(models.TextChoices):
        DAILY = "DAILY", "Daily"
        WEEKLY = "WEEKLY", "Weekly"

    location = models.ForeignKey(POSLocation, on_delete=models.PROTECT)
    created_by = models.ForeignKey(POSOperator, on_delete=models.PROTECT)
    recipient_email = models.EmailField(max_length=254)
    frequency = models.CharField(max_length=8, choices=Frequency.choices)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)


class ManagementReportRun(models.Model):
    class Status(models.TextChoices):
        CLAIMED = "CLAIMED", "Claimed"
        SUCCEEDED = "SUCCEEDED", "Succeeded"
        FAILED = "FAILED", "Failed"

    schedule = models.ForeignKey(ScheduledManagementReport, on_delete=models.PROTECT, related_name="runs")
    period_start = models.DateField()
    period_end = models.DateField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.CLAIMED)
    detail = models.CharField(max_length=500, blank=True)
    claimed_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["schedule", "period_end"], name="uniq_management_report_period")
        ]


class AuditEvent(models.Model):
    actor = models.CharField(max_length=255)
    action = models.CharField(max_length=128)
    entity_type = models.CharField(max_length=128)
    entity_reference = models.CharField(max_length=255)
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
