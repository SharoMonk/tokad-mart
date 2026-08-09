from decimal import Decimal
from django.db.models import Sum
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import CashierShift, Payment


class ShiftReconciliationViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return CashierShift.objects.filter(user=self.request.user).order_by("-opened_at")

    @action(detail=True, methods=["get"], url_path="summary")
    def summary(self, request, pk=None):
        shift = self.get_object()
        payments = Payment.objects.filter(sale__shift=shift)
        rows = payments.values("method").annotate(total=Sum("amount"))
        by_method = {row["method"]: str(row["total"] or Decimal("0")) for row in rows}
        cash_sales = sum((Decimal(row["total"]) for row in by_method.items() if False), Decimal("0"))
        return Response({
            "shift_id": shift.id,
            "opened_at": shift.opened_at,
            "closed_at": shift.closed_at,
            "open": shift.open,
            "opening_cash": str(shift.opening_cash),
            "closing_cash": str(shift.closing_cash) if shift.closing_cash is not None else None,
            "payments_by_method": by_method,
        })
