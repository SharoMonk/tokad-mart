from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from decimal import Decimal
import uuid

class Product(models.Model):
    sku = models.CharField(max_length=64, unique=True)
    barcode = models.CharField(max_length=128, unique=True, null=True, blank=True)
    name = models.CharField(max_length=255)
    unit = models.CharField(max_length=32, default='pcs')
    retail_price = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    wholesale_price = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class Customer(models.Model):
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=32, blank=True, default='')
    email = models.EmailField(blank=True, default='')
    wholesale = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

class InventoryLocation(models.Model):
    name = models.CharField(max_length=120, unique=True)
    active = models.BooleanField(default=True)

class StockBalance(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    location = models.ForeignKey(InventoryLocation, on_delete=models.CASCADE)
    quantity = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    reserved_quantity = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    version = models.PositiveBigIntegerField(default=0)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['product','location'], name='unique_stock_balance')]

class StockMovement(models.Model):
    class Type(models.TextChoices):
        PURCHASE='PURCHASE'; SALE='SALE'; SALE_RETURN='SALE_RETURN'; ADJUSTMENT='ADJUSTMENT'
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    location = models.ForeignKey(InventoryLocation, on_delete=models.PROTECT)
    quantity_delta = models.DecimalField(max_digits=14, decimal_places=3)
    movement_type = models.CharField(max_length=32, choices=Type.choices)
    reference = models.CharField(max_length=128)
    actor = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

class CashierShift(models.Model):
    user = models.ForeignKey(User, on_delete=models.PROTECT)
    location = models.ForeignKey(InventoryLocation, on_delete=models.PROTECT)
    opening_cash = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal('0'))])
    closing_cash = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    open = models.BooleanField(default=True)

class Sale(models.Model):
    class Status(models.TextChoices):
        COMPLETED='COMPLETED'; VOID='VOID'
    number = models.CharField(max_length=32, unique=True)
    customer = models.ForeignKey(Customer, null=True, blank=True, on_delete=models.PROTECT)
    cashier = models.ForeignKey(User, on_delete=models.PROTECT)
    location = models.ForeignKey(InventoryLocation, on_delete=models.PROTECT)
    shift = models.ForeignKey(CashierShift, on_delete=models.PROTECT)
    subtotal = models.DecimalField(max_digits=14, decimal_places=2)
    discount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=14, decimal_places=2)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.COMPLETED)
    idempotency_key = models.CharField(max_length=128, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, related_name='items', on_delete=models.PROTECT)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=14, decimal_places=3, validators=[MinValueValidator(Decimal('0.001'))])
    unit_price = models.DecimalField(max_digits=14, decimal_places=2)
    discount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=14, decimal_places=2)

class Payment(models.Model):
    class Method(models.TextChoices):
        CASH='CASH'; POS='POS'; TRANSFER='TRANSFER'
    sale = models.ForeignKey(Sale, related_name='payments', on_delete=models.PROTECT)
    method = models.CharField(max_length=16, choices=Method.choices)
    amount = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    reference = models.CharField(max_length=128, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

class IdempotencyKey(models.Model):
    key = models.CharField(max_length=128, unique=True)
    response_sale = models.ForeignKey(Sale, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
