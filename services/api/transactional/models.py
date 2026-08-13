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
    class Status(models.TextChoices):
        PENDING = "PENDING"
        SUCCEEDED = "SUCCEEDED"
        FAILED = "FAILED"
        CANCELLED = "CANCELLED"
        REFUNDED = "REFUNDED"

    sale = models.ForeignKey(Sale, on_delete=models.PROTECT, related_name="payments")
    provider = models.CharField(max_length=64)
    provider_reference = models.CharField(max_length=255, unique=True)
    amount_minor = models.PositiveBigIntegerField()
    currency = models.CharField(max_length=3)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)


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
