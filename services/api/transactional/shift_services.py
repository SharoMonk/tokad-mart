"""Cashier-shift operations backed by the canonical Sale and Payment ledger."""
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.utils import timezone

from .models import AuditEvent, CashierShift, Payment, POSOperator
from .pos_access import authorize_pos_scope


class ShiftError(ValueError):
    pass


def _as_minor(value, field):
    if type(value) is not int or value < 0:
        raise ShiftError(f"{field} must be a non-negative integer in minor units")
    return value


def _operator_shift(user, shift_id, *, lock=False):
    qs = CashierShift.objects.select_related("terminal", "location", "operator")
    if lock:
        qs = qs.select_for_update()
    try:
        shift = qs.get(id=shift_id)
    except (ValueError, TypeError, CashierShift.DoesNotExist) as exc:
        raise ShiftError("shift was not found") from exc
    authorize_pos_scope(
        user=user, location_code=shift.location.code, terminal_code=shift.terminal.code
    )
    if shift.operator.user_id != user.pk:
        raise ShiftError("shift is assigned to a different cashier")
    return shift


@transaction.atomic
def open_shift(*, user, location_code, terminal_code, opening_cash_minor):
    amount = _as_minor(opening_cash_minor, "opening_cash_minor")
    scope = authorize_pos_scope(
        user=user, location_code=location_code, terminal_code=terminal_code
    )
    # Serialize openings per terminal, even when no shift exists yet.
    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
            [f"cashier-shift:{scope.terminal.pk}"],
        )
    if CashierShift.objects.filter(
        terminal=scope.terminal, status=CashierShift.Status.OPEN
    ).exists():
        raise ShiftError("this terminal already has an open shift")
    shift = CashierShift.objects.create(
        operator=scope.operator,
        location=scope.location,
        terminal=scope.terminal,
        opening_cash_minor=amount,
    )
    AuditEvent.objects.create(
        actor=str(user.pk), action="shift.opened",
        entity_type="CashierShift", entity_reference=str(shift.pk),
        metadata={"opening_cash_minor": amount, "terminal_code": terminal_code},
    )
    return shift


@transaction.atomic
def close_shift(*, user, shift_id, closing_cash_minor):
    closing = _as_minor(closing_cash_minor, "closing_cash_minor")
    shift = _operator_shift(user, shift_id, lock=True)
    if shift.status != CashierShift.Status.OPEN:
        raise ShiftError("shift is already closed")
    cash_sales_minor = Payment.objects.filter(
        sale__shift=shift,
        sale__status="COMPLETED",
        method=Payment.Method.CASH,
        status=Payment.Status.SUCCEEDED,
    ).aggregate(total=Sum("amount_minor"))["total"] or 0
    expected = shift.opening_cash_minor + cash_sales_minor
    shift.closing_cash_minor = closing
    shift.expected_cash_minor = expected
    shift.status = CashierShift.Status.CLOSED
    shift.closed_at = timezone.now()
    shift.save(update_fields=[
        "closing_cash_minor", "expected_cash_minor", "status", "closed_at"
    ])
    AuditEvent.objects.create(
        actor=str(user.pk), action="shift.closed",
        entity_type="CashierShift", entity_reference=str(shift.pk),
        metadata={"expected_cash_minor": expected, "closing_cash_minor": closing,
                  "variance_minor": closing - expected},
    )
    return shift


def active_shift(*, user, location_code, terminal_code):
    scope = authorize_pos_scope(
        user=user, location_code=location_code, terminal_code=terminal_code
    )
    return CashierShift.objects.filter(
        operator=scope.operator, location=scope.location,
        terminal=scope.terminal, status=CashierShift.Status.OPEN
    ).first()


def serialize_shift(shift):
    if shift is None:
        return {"shift": None}
    data = {
        "id": shift.pk,
        "location_code": shift.location.code,
        "terminal_code": shift.terminal.code,
        "status": shift.status,
        "opening_cash_minor": shift.opening_cash_minor,
        "opened_at": shift.opened_at.isoformat(),
    }
    if shift.status == CashierShift.Status.CLOSED:
        data.update({
            "closing_cash_minor": shift.closing_cash_minor,
            "expected_cash_minor": shift.expected_cash_minor,
            "variance_minor": shift.closing_cash_minor - shift.expected_cash_minor,
        })
    return {"shift": data}
