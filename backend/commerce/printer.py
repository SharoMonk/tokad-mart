from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


class PrinterSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120)
    kind = serializers.ChoiceField(choices=["THERMAL", "BROWSER"])
    host = serializers.CharField(max_length=255, required=False, allow_blank=True)
    port = serializers.IntegerField(required=False, min_value=1, max_value=65535)
    enabled = serializers.BooleanField(default=True)


class PrinterViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["post"], url_path="test")
    def test(self, request):
        serializer = PrinterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        config = serializer.validated_data
        # The backend intentionally does not open arbitrary sockets. A local
        # print bridge consumes this validated configuration and performs the
        # hardware operation inside the shop network.
        return Response({"ok": True, "printer": config, "message": "Printer configuration accepted for local bridge."})


# Receipt output is deliberately transport-neutral. The POS can render this
# payload to browser print, while the future LAN bridge can render ESC/POS.
def receipt_payload(sale):
    return {
        "sale_number": sale.number,
        "created_at": sale.created_at,
        "cashier": sale.cashier.get_username(),
        "items": [
            {"name": item.product.name, "quantity": str(item.quantity), "unit_price": str(item.unit_price), "total": str(item.line_total)}
            for item in sale.items.select_related("product")
        ],
        "subtotal": str(sale.subtotal),
        "discount": str(sale.discount),
        "tax": str(sale.tax),
        "total": str(sale.total),
        "payments": [{"method": p.method, "amount": str(p.amount)} for p in sale.payments.all()],
    }
