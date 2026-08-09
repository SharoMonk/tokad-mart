from rest_framework import serializers, viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Product, Customer, InventoryLocation, StockBalance, CashierShift, Sale
from .services import checkout

class ProductSerializer(serializers.ModelSerializer):
    class Meta: model=Product; fields='__all__'
class CustomerSerializer(serializers.ModelSerializer):
    class Meta: model=Customer; fields='__all__'
class LocationSerializer(serializers.ModelSerializer):
    class Meta: model=InventoryLocation; fields='__all__'
class SaleSerializer(serializers.ModelSerializer):
    items = serializers.SerializerMethodField(); payments = serializers.SerializerMethodField()
    class Meta: model=Sale; fields=['id','number','customer','subtotal','discount','tax','total','status','created_at','items','payments']
    def get_items(self,obj): return [{'product_id':i.product_id,'name':i.product.name,'quantity':str(i.quantity),'unit_price':str(i.unit_price),'line_total':str(i.line_total)} for i in obj.items.select_related('product')]
    def get_payments(self,obj): return [{'method':p.method,'amount':str(p.amount),'reference':p.reference} for p in obj.payments.all()]

class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    queryset=Product.objects.filter(active=True); serializer_class=ProductSerializer
    def get_queryset(self):
        qs=super().get_queryset(); q=self.request.query_params.get('q')
        return qs.filter(name__icontains=q) | qs.filter(sku__iexact=q) | qs.filter(barcode__iexact=q) if q else qs
class CustomerViewSet(viewsets.ModelViewSet):
    queryset=Customer.objects.all(); serializer_class=CustomerSerializer
class LocationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset=InventoryLocation.objects.filter(active=True); serializer_class=LocationSerializer
class SaleViewSet(viewsets.ReadOnlyModelViewSet):
    queryset=Sale.objects.select_related('customer','location','shift').prefetch_related('items__product','payments'); serializer_class=SaleSerializer
    @action(detail=False, methods=['post'], url_path='checkout')
    def checkout_action(self, request):
        data=request.data
        sale=checkout(user=request.user, shift_id=data['shift_id'], location_id=data['location_id'], customer_id=data.get('customer_id'), items=data.get('items',[]), payments=data.get('payments',[]), idempotency_key=request.headers.get('Idempotency-Key') or data.get('idempotency_key',''))
        return Response(SaleSerializer(sale).data, status=status.HTTP_201_CREATED)

class ShiftViewSet(viewsets.ModelViewSet):
    queryset=CashierShift.objects.all(); http_method_names=['get','post','head','options']
    def create(self, request, *args, **kwargs):
        if CashierShift.objects.filter(user=request.user, open=True).exists(): return Response({'detail':'Cashier already has an open shift.'}, status=400)
        shift=CashierShift.objects.create(user=request.user, location_id=request.data['location_id'], opening_cash=request.data.get('opening_cash',0))
        return Response({'id':shift.id,'open':shift.open}, status=201)

from rest_framework.routers import DefaultRouter
api=DefaultRouter()
api.register('products',ProductViewSet); api.register('customers',CustomerViewSet); api.register('locations',LocationViewSet); api.register('sales',SaleViewSet); api.register('shifts',ShiftViewSet)
