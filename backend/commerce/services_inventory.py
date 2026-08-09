from decimal import Decimal
from uuid import uuid4
from django.db import transaction
from rest_framework.exceptions import ValidationError
from .models import InventoryAdjustment, Product, InventoryLocation, StockBalance, StockMovement, Sale, SaleItem, SaleReturn, SaleReturnItem


def _number(prefix):
    return f'{prefix}-{uuid4().hex[:10].upper()}'

@transaction.atomic
def adjust_stock(*, user, product_id, location_id, quantity_delta, reason):
    quantity_delta=Decimal(str(quantity_delta))
    if quantity_delta == 0 or not reason.strip(): raise ValidationError('A non-zero quantity and reason are required.')
    product=Product.objects.get(id=product_id,active=True); location=InventoryLocation.objects.get(id=location_id,active=True)
    balance=StockBalance.objects.select_for_update().filter(product=product,location=location).first()
    if not balance: balance=StockBalance.objects.create(product=product,location=location)
    if balance.quantity + quantity_delta < 0: raise ValidationError('Adjustment would make stock negative.')
    ref=_number('ADJ'); balance.quantity += quantity_delta; balance.version += 1; balance.save(update_fields=['quantity','version'])
    adjustment=InventoryAdjustment.objects.create(number=ref,product=product,location=location,quantity_delta=quantity_delta,reason=reason.strip(),actor=user)
    StockMovement.objects.create(product=product,location=location,quantity_delta=quantity_delta,movement_type=StockMovement.Type.ADJUSTMENT,reference=ref,actor=user)
    return adjustment

@transaction.atomic
def return_sale(*, user, sale_id, items, reason=''):
    sale=Sale.objects.select_for_update().select_related('location').get(id=sale_id,status=Sale.Status.COMPLETED)
    requested={int(x['sale_item_id']): Decimal(str(x['quantity'])) for x in items}
    if not requested: raise ValidationError('Return must contain at least one item.')
    existing={}
    for r in SaleReturnItem.objects.filter(return_document__sale=sale): existing[r.sale_item_id]=existing.get(r.sale_item_id,Decimal('0'))+r.quantity
    total=Decimal('0.00'); prepared=[]
    for item_id,qty in requested.items():
        item=SaleItem.objects.select_for_update().get(id=item_id,sale=sale)
        if qty <= 0 or existing.get(item.id,Decimal('0'))+qty > item.quantity: raise ValidationError(f'Invalid return quantity for {item.product.name}.')
        refund=(item.unit_price*qty).quantize(Decimal('0.01')); total += refund; prepared.append((item,qty,refund))
    ref=_number('RET'); document=SaleReturn.objects.create(number=ref,sale=sale,cashier=user,location=sale.location,total=total,reason=reason.strip())
    for item,qty,refund in prepared:
        SaleReturnItem.objects.create(return_document=document,sale_item=item,quantity=qty,refund_amount=refund)
        balance=StockBalance.objects.select_for_update().filter(product=item.product,location=sale.location).first()
        if not balance: balance=StockBalance.objects.create(product=item.product,location=sale.location)
        balance.quantity += qty; balance.version += 1; balance.save(update_fields=['quantity','version'])
        StockMovement.objects.create(product=item.product,location=sale.location,quantity_delta=qty,movement_type=StockMovement.Type.SALE_RETURN,reference=ref,actor=user)
    return document
