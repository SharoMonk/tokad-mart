from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from .models import Product, InventoryLocation, StockBalance, CashierShift, Sale, Payment, StockMovement


class TransactionalCheckoutTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="cashier", password="test-password")
        self.location = InventoryLocation.objects.create(name="Main Shop", active=True)
        self.product = Product.objects.create(name="Test Product", sku="TP-001", barcode="123456", retail_price=Decimal("100.00"), wholesale_price=Decimal("90.00"), unit="pcs", active=True)
        StockBalance.objects.create(product=self.product, location=self.location, quantity=Decimal("10"), reserved_quantity=Decimal("0"))
        self.shift = CashierShift.objects.create(user=self.user, location=self.location, opening_cash=Decimal("500"), open=True)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_checkout_creates_sale_payment_and_stock_ledger(self):
        response = self.client.post("/api/sales/checkout/", {"shift_id": self.shift.id, "location_id": self.location.id, "items": [{"product_id": self.product.id, "quantity": 2}], "payments": [{"method": "CASH", "amount": "200.00"}]}, format="json", HTTP_IDEMPOTENCY_KEY="test-1")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Sale.objects.count(), 1)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(StockBalance.objects.get(product=self.product, location=self.location).quantity, Decimal("8"))
        self.assertTrue(StockMovement.objects.filter(movement_type="SALE", product=self.product).exists())

    def test_checkout_is_idempotent(self):
        payload = {"shift_id": self.shift.id, "location_id": self.location.id, "items": [{"product_id": self.product.id, "quantity": 1}], "payments": [{"method": "CASH", "amount": "100.00"}]}
        first = self.client.post("/api/sales/checkout/", payload, format="json", HTTP_IDEMPOTENCY_KEY="same-key")
        second = self.client.post("/api/sales/checkout/", payload, format="json", HTTP_IDEMPOTENCY_KEY="same-key")
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        self.assertEqual(Sale.objects.count(), 1)
        self.assertEqual(StockBalance.objects.get(product=self.product, location=self.location).quantity, Decimal("9"))

    def test_payment_mismatch_does_not_create_sale(self):
        response = self.client.post("/api/sales/checkout/", {"shift_id": self.shift.id, "location_id": self.location.id, "items": [{"product_id": self.product.id, "quantity": 1}], "payments": [{"method": "CASH", "amount": "99.00"}]}, format="json", HTTP_IDEMPOTENCY_KEY="mismatch")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Sale.objects.count(), 0)
        self.assertEqual(StockBalance.objects.get(product=self.product, location=self.location).quantity, Decimal("10"))
