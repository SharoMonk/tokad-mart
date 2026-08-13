from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers, viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import Product, Customer, InventoryLocation, StockBalance, CashierShift, Sale
from .services import checkout
from .services_inventory import adjust_stock, return_sale
from .receiving import StockReceivingViewSet
from .permissions import CanOperatePOS, IsManagerOrOwner
from .reconciliation import ShiftReconciliationViewSet
from .scan import ScanViewSet
from .printer import PrinterViewSet

class ProductSerializer(serializers.ModelSerializer):
    class Meta: model=Product; fields='__all__'
class CustomerSerializer(serializers.ModelSerializer):
    class Meta: model=Customer; fields='__all__'
class LocationSerializer(serializers.ModelSerializer):
    class Meta: model=InventoryLocation; fields='__all__'
class ShiftSerializer(serializers.ModelSerializer):
    class Meta:
        model=CashierShift; fields=['id','user','location','opening_cash','closing_cash','opened_at','closed_at','open']; read_only_fields=['user','opened_at','closed_at','open']
class SaleSerializer(serializers.ModelSerializer):
    items=serializers.SerializerMethodField(); payments=serializers.SerializerMethodField()
    class Meta:
        model=Sale; fields=['id','number','customer','cashier','location','shift','subtotal','discount','tax','total','status','created_at','items','payments']
    def get_items(self,obj): return [{'id':i.id,'product_id':i.product_id,'name':i.product.name,'quantity':str(i.quantity),'unit_price':str(i.unit_price),'line_total':str(i.line_total)} for i in obj.items.select_related('product')]
    def get_payments(self,obj): return [{'method':p.method,'amount':str(p.amount),'reference':p.reference} for p in obj.payments.all()]
class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    queryset=Product.objects.filter(active=True); serializer_class=ProductSerializer
    def get_queryset(self):
        qs=super().get_queryset(); q=self.request.query_params.get('q','').strip()
        return (qs.filter(name__icontains=q)|qs.filter(sku__iexact=q)|qs.filter(barcode__iexact=q)) if q else qs
class CustomerViewSet(viewsets.ModelViewSet):
    queryset=Customer.objects.all(); serializer_class=CustomerSerializer
class LocationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset=InventoryLocation.objects.filter(active=True); serializer_class=LocationSerializer
class SaleViewSet(viewsets.ReadOnlyModelViewSet):
    queryset=Sale.objects.select_related('customer','cashier','location','shift').prefetch_related('items__product','payments'); serializer_class=SaleSerializer; permission_classes=[CanOperatePOS]
    @action(detail=False,methods=['post'],url_path='checkout')
    def checkout_action(self,request):
        data=request.data; key=request.headers.get('Idempotency-Key') or data.get('idempotency_key','')
        if not key: return Response({'detail':'Idempotency-Key header is required.'},status=400)
        sale=checkout(user=request.user,shift_id=data.get('shift_id'),location_id=data.get('location_id'),customer_id=data.get('customer_id'),items=data.get('items',[]),payments=data.get('payments',[]),idempotency_key=key)
        return Response(SaleSerializer(sale).data,status=status.HTTP_201_CREATED)
    @action(detail=True,methods=['get'],url_path='receipt')
    def receipt(self,request,pk=None):
        sale=self.get_object(); data=SaleSerializer(sale).data
        return Response({'sale_number':sale.number,'created_at':sale.created_at,'cashier':sale.cashier.get_username(),'customer':sale.customer.name if sale.customer else None,'items':data['items'],'subtotal':str(sale.subtotal),'discount':str(sale.discount),'tax':str(sale.tax),'total':str(sale.total),'payments':data['payments']})
    @action(detail=True,methods=['post'],url_path='return')
    @transaction.atomic
    def return_sale_action(self,request,pk=None):
        document=return_sale(user=request.user,sale_id=pk,items=request.data.get('items',[]),reason=request.data.get('reason',''))
        return Response({'number':document.number,'sale_id':document.sale_id,'total':str(document.total)},status=201)
class ShiftViewSet(viewsets.ModelViewSet):
    serializer_class=ShiftSerializer; permission_classes=[CanOperatePOS]; http_method_names=['get','post','head','options']
    def get_queryset(self): return CashierShift.objects.filter(user=self.request.user).select_related('location')
    @transaction.atomic
    def create(self,request,*args,**kwargs):
        if CashierShift.objects.filter(user=request.user,open=True).exists(): return Response({'detail':'Cashier already has an open shift.'},status=400)
        opening=Decimal(str(request.data.get('opening_cash','0')))
        if opening<0: return Response({'detail':'Opening cash cannot be negative.'},status=400)
        shift=CashierShift.objects.create(user=request.user,location_id=request.data['location_id'],opening_cash=opening)
        return Response(ShiftSerializer(shift).data,status=201)
    @action(detail=True,methods=['post'],url_path='close')
    @transaction.atomic
    def close(self,request,pk=None):
        shift=CashierShift.objects.select_for_update().filter(id=pk,user=request.user).first()
        if not shift: return Response({'detail':'Shift not found.'},status=404)
        if not shift.open: return Response(ShiftSerializer(shift).data)
        closing=Decimal(str(request.data.get('closing_cash','0')))
        if closing<0: return Response({'detail':'Closing cash cannot be negative.'},status=400)
        shift.closing_cash=closing; shift.closed_at=timezone.now(); shift.open=False; shift.save(update_fields=['closing_cash','closed_at','open'])
        return Response(ShiftSerializer(shift).data)
class InventoryViewSet(viewsets.ViewSet):
    permission_classes=[IsAuthenticated]
    @action(detail=False,methods=['post'],url_path='adjust',permission_classes=[IsManagerOrOwner])
    def adjust(self,request):
        adjustment=adjust_stock(user=request.user,product_id=request.data.get('product_id'),location_id=request.data.get('location_id'),quantity_delta=request.data.get('quantity_delta'),reason=request.data.get('reason',''))
        return Response({'number':adjustment.number,'quantity_delta':str(adjustment.quantity_delta)},status=201)
    @action(detail=False,methods=['get'],url_path='stock')
    def stock(self,request):
        qs=StockBalance.objects.select_related('product','location').filter(location_id=request.query_params.get('location_id'))
        return Response([{'product_id':x.product_id,'product':x.product.name,'quantity':str(x.quantity),'reserved':str(x.reserved_quantity)} for x in qs])

from rest_framework.routers import DefaultRouter
api=DefaultRouter()
api.register('products',ProductViewSet); api.register('customers',CustomerViewSet); api.register('locations',LocationViewSet)
api.register('sales',SaleViewSet); api.register('shifts',ShiftViewSet,basename='shift'); api.register('inventory',InventoryViewSet,basename='inventory')
api.register('receiving',StockReceivingViewSet,basename='receiving'); api.register('reconciliation',ShiftReconciliationViewSet,basename='reconciliation')
api.register('scan',ScanViewSet,basename='scan'); api.register('printers',PrinterViewSet,basename='printer')
