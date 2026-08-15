from dataclasses import dataclass

from django.contrib.auth import get_user_model

from .models import POSLocation, POSOperator, POSTerminal


class POSAccessError(Exception):
    """Raised when a POS operator cannot access the requested scope."""


@dataclass(frozen=True)
class POSAccessContext:
    operator: POSOperator
    location: POSLocation
    terminal: POSTerminal


def authorize_pos_scope(
    *,
    user: object,
    location_code: str,
    terminal_code: str,
) -> POSAccessContext:
    if not getattr(user, "is_authenticated", False):
        raise POSAccessError("authentication is required")

    if not getattr(user, "is_staff", False):
        raise POSAccessError("POS operator permission is required")

    try:
        operator = POSOperator.objects.select_related("user").get(
            user=user,
            is_active=True,
        )
    except POSOperator.DoesNotExist as exc:
        raise POSAccessError("active POS operator profile was not found") from exc

    try:
        location = POSLocation.objects.get(code=location_code)
    except POSLocation.DoesNotExist as exc:
        raise POSAccessError("POS location was not found") from exc

    if not location.is_active:
        raise POSAccessError("POS location is inactive")

    if not operator.locations.filter(id=location.id).exists():
        raise POSAccessError("operator is not assigned to this POS location")

    try:
        terminal = POSTerminal.objects.select_related("location").get(
            location=location,
            code=terminal_code,
        )
    except POSTerminal.DoesNotExist as exc:
        raise POSAccessError("POS terminal was not found for this location") from exc

    if not terminal.is_active:
        raise POSAccessError("POS terminal is inactive")

    if not operator.terminals.filter(id=terminal.id).exists():
        raise POSAccessError("operator is not assigned to this POS terminal")

    return POSAccessContext(
        operator=operator,
        location=location,
        terminal=terminal,
    )
