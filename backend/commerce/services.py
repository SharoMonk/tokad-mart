from decimal import Decimal
from uuid import uuid4
from django.db import transaction
from rest_framework.exceptions import ValidationError
from .models import Product, Customer, InventoryLocation, StockBalance, StockMovement, Sale, SaleItem, Payment, CashierShift

@transaction.atomic
def checkout(*, user, shift_id, location_id, customer_id, items, payments, idempotency_key):
    existing = Sale.objects.filter(idempotency_key=idempotency_key).first()
    if existing:
        return existing
    shift = CashierShift.objects.select_for_update().get(id=shift_id, user=user, open=True)
    location = InventoryLocation.objects.get(id=location_id, active=True)
    customer = Customer.objects.filter(id=customer_id).first() if customer_id else None
    if not items:
        raise ValidationError('Sale must contain at least one item.')
    subtotal = Decimal('0.00')
    prepared = []
    for item in items:
        product = Product.objects.get(id=item['product_id'], active=True)
        qty = Decimal(str(item['quantity']))
        if qty <= 0:
            raise ValidationError('Quantity must be positive.')
        balance = StockBalance.objects.select_for_update().get(product=product, location=location)
        available = balance.quantity - balance.reserved_quantity
        if available < qty:
            raise ValidationError(f'Insufficient stock for {product.name}. Available: {available}')
        unit_price = product.wholesale_price if customer and customer.wholesale else product.retail_price
        line_total = (unit_price * qty).quantize(Decimal('0.01'))
        subtotal += line_total
        prepared.append((product, qty, unit_price, line_total, balance))
    total = subtotal
    paid = sum((Decimal(str(p['amount'])) for p in payments), Decimal('0.00'))
    if paid != total:
        raise ValidationError({'payments': f'Payment total {paid} does not equal sale total {total}.'})
    sale = Sale.objects.create(number=f'TK-{uuid4().hex[:10].upper()}', customer=customer, cashier=user, location=location, shift=shift, subtotal=subtotal, total=total, idempotency_key=idempotency_key)
    for product, qty, unit_price, line_total, balance in prepared:
        SaleItem.objects.create(sale=sale, product=product, quantity=qty, unit_price=unit_price, line_total=line_total)
        balance.quantity -= qty
        balance.version += 1
        balance.save(update_fields=['quantity','version'])
        StockMovement.objects.create(product=product, location=location, quantity_delta=-qty, movement_type=StockMovement.Type.SALE, reference=sale.number, actor=user)
    for p in payments:
        Payment.objects.create(sale=sale, method=p['method'], amount=Decimal(str(p['amount'])), reference=p.get('reference',''))
    return sale
