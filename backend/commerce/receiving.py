from decimal import Decimal
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import Product, InventoryLocation, StockBalance, StockMovement
from .permissions import IsManagerOrOwner


class ReceiveItemSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    quantity = serializers.DecimalField(max_digits=14, decimal_places=3, min_value=Decimal("0.001"))
    unit_cost = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0"), required=False, default=Decimal("0"))


class StockReceivingViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated, IsManagerOrOwner]

    @action(detail=False, methods=["post"], url_path="receive")
    @transaction.atomic
    def receive(self, request):
        location_id = request.data.get("location_id")
        items = ReceiveItemSerializer(data=request.data.get("items", []), many=True)
        items.is_valid(raise_exception=True)
        location = get_object_or_404(InventoryLocation, pk=location_id, active=True)
        received = []
        for row in items.validated_data:
            product = get_object_or_404(Product, pk=row["product_id"], active=True)
            balance, _ = StockBalance.objects.select_for_update().get_or_create(product=product, location=location, defaults={"quantity": Decimal("0")})
            balance.quantity += row["quantity"]
            balance.save(update_fields=["quantity"])
            movement = StockMovement.objects.create(
                product=product,
                location=location,
                quantity=row["quantity"],
                movement_type="PURCHASE_RECEIPT",
                unit_cost=row["unit_cost"],
                actor=request.user,
            )
            received.append({"product_id": product.id, "quantity": str(row["quantity"]), "movement_id": movement.id})
        return Response({"location_id": location.id, "items": received}, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"], url_path="stock")
    def stock(self, request):
        location_id = request.query_params.get("location_id")
        qs = StockBalance.objects.select_related("product", "location")
        if location_id:
            qs = qs.filter(location_id=location_id)
        return Response([{"product_id": x.product_id, "product": x.product.name, "location_id": x.location_id, "quantity": str(x.quantity)} for x in qs])
