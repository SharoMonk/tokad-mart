from decimal import Decimal
from django.db.models import Sum
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import CashierShift, Payment


class ShiftReconciliationViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return CashierShift.objects.filter(user=self.request.user).select_related('location').order_by('-opened_at')

    @action(detail=True, methods=['get'], url_path='summary')
    def summary(self, request, pk=None):
        shift = self.get_object()
        rows = Payment.objects.filter(sale__shift=shift).values('method').annotate(total=Sum('amount'))
        by_method = {row['method']: str(row['total'] or Decimal('0.00')) for row in rows}
        cash_sales = sum((Decimal(row['total']) for row in rows if row['method'] == Payment.Method.CASH), Decimal('0.00'))
        expected_cash = shift.opening_cash + cash_sales
        variance = None
        if shift.closing_cash is not None:
            variance = shift.closing_cash - expected_cash
        return Response({
            'shift_id': shift.id,
            'location_id': shift.location_id,
            'opened_at': shift.opened_at,
            'closed_at': shift.closed_at,
            'open': shift.open,
            'opening_cash': str(shift.opening_cash),
            'closing_cash': str(shift.closing_cash) if shift.closing_cash is not None else None,
            'cash_sales': str(cash_sales),
            'expected_cash': str(expected_cash),
            'variance': str(variance) if variance is not None else None,
            'payments_by_method': by_method,
        })
