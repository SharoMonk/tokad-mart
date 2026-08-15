from django.conf import settings
from django.db import models


class Product(models.Model):
    sku = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=255)
    currency = models.CharField(max_length=3, default="NGN")
    unit_price_minor = models.PositiveBigIntegerField()
    is_active = models.BooleanField(default=True)


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


class Sale(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT"
        PENDING_PAYMENT = "PENDING_PAYMENT"
        COMPLETED = "COMPLETED"
        PAYMENT_FAILED = "PAYMENT_FAILED"
        CANCELLED = "CANCELLED"

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


class IdempotencyRecord(models.Model):
    key = models.CharField(max_length=255, unique=True)
    request_fingerprint = models.CharField(max_length=128)
    response_payload = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)


class AuditEvent(models.Model):
    actor = models.CharField(max_length=255)
    action = models.CharField(max_length=128)
    entity_type = models.CharField(max_length=128)
    entity_reference = models.CharField(max_length=255)
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
