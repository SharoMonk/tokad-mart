from decimal import Decimal, InvalidOperation
from uuid import uuid4
from django.db import transaction
from rest_framework.exceptions import ValidationError
from .models import Product, Customer, InventoryLocation, StockBalance, StockMovement, Sale, SaleItem, Payment, CashierShift, IdempotencyKey

MONEY = Decimal('0.01')

@transaction.atomic
def checkout(*, user, shift_id, location_id, customer_id, items, payments, idempotency_key):
    if not idempotency_key:
        raise ValidationError('Idempotency key is required.')
    if len(idempotency_key) > 128:
        raise ValidationError('Idempotency key is too long.')

    idem, _ = IdempotencyKey.objects.get_or_create(key=idempotency_key)
    idem = IdempotencyKey.objects.select_for_update().select_related('response_sale').get(pk=idem.pk)
    if idem.response_sale_id:
        return idem.response_sale

    shift = CashierShift.objects.select_for_update().filter(id=shift_id, user=user, open=True).first()
    if not shift:
        raise ValidationError('Open cashier shift not found.')
    if location_id and int(location_id) != shift.location_id:
        raise ValidationError('Sale location must match the cashier shift location.')
    location = shift.location
    customer = Customer.objects.filter(id=customer_id).first() if customer_id else None
    if customer_id and not customer:
        raise ValidationError('Customer not found.')
    if not items:
        raise ValidationError('Sale must contain at least one item.')
    if not payments:
        raise ValidationError('Sale must contain at least one payment.')

    subtotal = Decimal('0.00')
    prepared = []
    seen_products = set()
    for item in items:
        try:
            product_id = int(item['product_id'])
            qty = Decimal(str(item['quantity']))
        except (KeyError, ValueError, InvalidOperation):
            raise ValidationError('Each item requires a valid product_id and quantity.')
        if product_id in seen_products:
            raise ValidationError('Duplicate product lines are not allowed; consolidate quantities.')
        seen_products.add(product_id)
        if qty <= 0:
            raise ValidationError('Quantity must be positive.')
        product = Product.objects.filter(id=product_id, active=True).first()
        if not product:
            raise ValidationError(f'Product {product_id} is not available.')
        balance = StockBalance.objects.select_for_update().filter(product=product, location=location).first()
        if not balance:
            raise ValidationError(f'No stock balance exists for {product.name}.')
        available = balance.quantity - balance.reserved_quantity
        if available < qty:
            raise ValidationError(f'Insufficient stock for {product.name}. Available: {available}')
        unit_price = product.wholesale_price if customer and customer.wholesale else product.retail_price
        line_total = (unit_price * qty).quantize(MONEY)
        subtotal += line_total
        prepared.append((product, qty, unit_price, line_total, balance))

    total = subtotal.quantize(MONEY)
    paid = Decimal('0.00')
    for payment in payments:
        try:
            amount = Decimal(str(payment['amount'])).quantize(MONEY)
        except (KeyError, InvalidOperation):
            raise ValidationError('Each payment requires a valid amount.')
        if amount <= 0:
            raise ValidationError('Payment amount must be positive.')
        if payment.get('method') not in Payment.Method.values:
            raise ValidationError(f"Unsupported payment method: {payment.get('method')}")
        paid += amount
    if paid != total:
        raise ValidationError({'payments': f'Payment total {paid} does not equal sale total {total}.'})

    sale = Sale.objects.create(number=f'TK-{uuid4().hex[:10].upper()}', customer=customer, cashier=user,
        location=location, shift=shift, subtotal=subtotal, total=total, idempotency_key=idempotency_key)
    for product, qty, unit_price, line_total, balance in prepared:
        SaleItem.objects.create(sale=sale, product=product, quantity=qty, unit_price=unit_price, line_total=line_total)
        balance.quantity -= qty
        balance.version += 1
        balance.save(update_fields=['quantity', 'version'])
        StockMovement.objects.create(product=product, location=location, quantity_delta=-qty,
            movement_type=StockMovement.Type.SALE, reference=sale.number, actor=user)
    for payment in payments:
        Payment.objects.create(sale=sale, method=payment['method'], amount=Decimal(str(payment['amount'])).quantize(MONEY), reference=payment.get('reference', ''))
    idem.response_sale = sale
    idem.save(update_fields=['response_sale'])
    return sale
