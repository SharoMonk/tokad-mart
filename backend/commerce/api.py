from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers, viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import Product, Customer, InventoryLocation, StockBalance, CashierShift, Sale, Payment
from .services import checkout

class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = '__all__'

class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = '__all__'

class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryLocation
        fields = '__all__'

class ShiftSerializer(serializers.ModelSerializer):
    class Meta:
        model = CashierShift
        fields = ['id', 'user', 'location', 'opening_cash', 'closing_cash', 'opened_at', 'closed_at', 'open']
        read_only_fields = ['user', 'opened_at', 'closed_at', 'open']

class SaleSerializer(serializers.ModelSerializer):
    items = serializers.SerializerMethodField()
    payments = serializers.SerializerMethodField()

    class Meta:
        model = Sale
        fields = ['id','number','customer','cashier','location','shift','subtotal','discount','tax','total','status','created_at','items','payments']

    def get_items(self, obj):
        return [
            {'product_id': i.product_id, 'name': i.product.name, 'quantity': str(i.quantity),
             'unit_price': str(i.unit_price), 'line_total': str(i.line_total)}
            for i in obj.items.select_related('product')
        ]

    def get_payments(self, obj):
        return [{'method': p.method, 'amount': str(p.amount), 'reference': p.reference} for p in obj.payments.all()]

class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Product.objects.filter(active=True)
    serializer_class = ProductSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.query_params.get('q', '').strip()
        if not q:
            return qs
        return qs.filter(name__icontains=q) | qs.filter(sku__iexact=q) | qs.filter(barcode__iexact=q)

class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer

class LocationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = InventoryLocation.objects.filter(active=True)
    serializer_class = LocationSerializer

class SaleViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Sale.objects.select_related('customer','cashier','location','shift').prefetch_related('items__product','payments')
    serializer_class = SaleSerializer

    @action(detail=False, methods=['post'], url_path='checkout')
    def checkout_action(self, request):
        data = request.data
        idempotency_key = request.headers.get('Idempotency-Key') or data.get('idempotency_key', '')
        if not idempotency_key:
            return Response({'detail': 'Idempotency-Key header is required.'}, status=400)
        sale = checkout(
            user=request.user,
            shift_id=data.get('shift_id'),
            location_id=data.get('location_id'),
            customer_id=data.get('customer_id'),
            items=data.get('items', []),
            payments=data.get('payments', []),
            idempotency_key=idempotency_key,
        )
        return Response(SaleSerializer(sale).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'], url_path='receipt')
    def receipt(self, request, pk=None):
        sale = self.get_object()
        return Response({
            'sale_number': sale.number,
            'created_at': sale.created_at,
            'cashier': sale.cashier.get_username(),
            'customer': sale.customer.name if sale.customer else None,
            'items': SaleSerializer(sale).data['items'],
            'subtotal': str(sale.subtotal),
            'discount': str(sale.discount),
            'tax': str(sale.tax),
            'total': str(sale.total),
            'payments': SaleSerializer(sale).data['payments'],
        })

class ShiftViewSet(viewsets.ModelViewSet):
    serializer_class = ShiftSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        return CashierShift.objects.filter(user=self.request.user).select_related('location')

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        if CashierShift.objects.filter(user=request.user, open=True).exists():
            return Response({'detail': 'Cashier already has an open shift.'}, status=400)
        opening_cash = Decimal(str(request.data.get('opening_cash', '0')))
        if opening_cash < 0:
            return Response({'detail': 'Opening cash cannot be negative.'}, status=400)
        shift = CashierShift.objects.create(user=request.user, location_id=request.data['location_id'], opening_cash=opening_cash)
        return Response(ShiftSerializer(shift).data, status=201)

    @action(detail=True, methods=['post'], url_path='close')
    @transaction.atomic
    def close(self, request, pk=None):
        shift = CashierShift.objects.select_for_update().filter(id=pk, user=request.user).first()
        if not shift:
            return Response({'detail': 'Shift not found.'}, status=404)
        if not shift.open:
            return Response(ShiftSerializer(shift).data)
        closing_cash = Decimal(str(request.data.get('closing_cash', '0')))
        if closing_cash < 0:
            return Response({'detail': 'Closing cash cannot be negative.'}, status=400)
        shift.closing_cash = closing_cash
        shift.closed_at = timezone.now()
        shift.open = False
        shift.save(update_fields=['closing_cash', 'closed_at', 'open'])
        return Response(ShiftSerializer(shift).data)

from rest_framework.routers import DefaultRouter
api = DefaultRouter()
api.register('products', ProductViewSet)
api.register('customers', CustomerViewSet)
api.register('locations', LocationViewSet)
api.register('sales', SaleViewSet)
api.register('shifts', ShiftViewSet, basename='shift')
