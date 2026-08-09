from decimal import Decimal
from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient
from .models import Product, InventoryLocation, StockBalance, StockMovement, Sale, Payment, CashierShift

class TransactionalPOSTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='cashier', password='secret')
        self.token = Token.objects.create(user=self.user)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        self.location = InventoryLocation.objects.create(name='Main Shop')
        self.product = Product.objects.create(sku='SKU-001', barcode='123456', name='Test Product', retail_price='100.00', wholesale_price='80.00')
        StockBalance.objects.create(product=self.product, location=self.location, quantity='10')

    def open_shift(self):
        response = self.client.post('/api/shifts/', {'location_id': self.location.id, 'opening_cash': '5000.00'}, format='json')
        self.assertEqual(response.status_code, 201)
        return response.data['id']

    def test_checkout_deducts_stock_and_records_payment(self):
        shift_id = self.open_shift()
        response = self.client.post('/api/sales/checkout/', {
            'shift_id': shift_id,
            'location_id': self.location.id,
            'items': [{'product_id': self.product.id, 'quantity': 2}],
            'payments': [{'method': 'CASH', 'amount': '200.00'}],
        }, format='json', HTTP_IDEMPOTENCY_KEY='sale-test-1')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['total'], '200.00')
        self.assertEqual(StockBalance.objects.get(product=self.product, location=self.location).quantity, Decimal('8'))
        self.assertEqual(StockMovement.objects.filter(reference=response.data['number']).count(), 1)
        self.assertEqual(Payment.objects.filter(sale_id=response.data['id']).count(), 1)

    def test_idempotent_retry_returns_same_sale(self):
        shift_id = self.open_shift()
        payload = {'shift_id': shift_id, 'location_id': self.location.id, 'items': [{'product_id': self.product.id, 'quantity': 1}], 'payments': [{'method': 'CASH', 'amount': '100.00'}]}
        first = self.client.post('/api/sales/checkout/', payload, format='json', HTTP_IDEMPOTENCY_KEY='retry-1')
        second = self.client.post('/api/sales/checkout/', payload, format='json', HTTP_IDEMPOTENCY_KEY='retry-1')
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        self.assertEqual(first.data['id'], second.data['id'])
        self.assertEqual(Sale.objects.count(), 1)
        self.assertEqual(StockBalance.objects.get(product=self.product, location=self.location).quantity, Decimal('9'))

    def test_payment_must_equal_total(self):
        shift_id = self.open_shift()
        response = self.client.post('/api/sales/checkout/', {
            'shift_id': shift_id, 'location_id': self.location.id,
            'items': [{'product_id': self.product.id, 'quantity': 1}],
            'payments': [{'method': 'CASH', 'amount': '90.00'}],
        }, format='json', HTTP_IDEMPOTENCY_KEY='payment-1')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Sale.objects.count(), 0)

    def test_shift_can_be_closed(self):
        shift_id = self.open_shift()
        response = self.client.post(f'/api/shifts/{shift_id}/close/', {'closing_cash': '5100.00'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['open'])
        self.assertIsNotNone(response.data['closed_at'])
