from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import Product


class ScanSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=128)


class ScanViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["post"], url_path="resolve")
    def resolve(self, request):
        serializer = ScanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        code = serializer.validated_data["code"].strip()
        product = Product.objects.filter(active=True, barcode__iexact=code).first()
        if not product:
            product = Product.objects.filter(active=True, sku__iexact=code).first()
        if not product:
            return Response({"detail": "Product not found for scanned code."}, status=404)
        return Response({"id": product.id, "sku": product.sku, "barcode": product.barcode, "name": product.name, "retail_price": str(product.retail_price), "wholesale_price": str(product.wholesale_price), "unit": product.unit})
