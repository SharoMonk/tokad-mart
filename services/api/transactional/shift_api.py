import json
from django.http import JsonResponse
from rest_framework.authentication import BasicAuthentication, SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated

from .permissions import IsPOSOperator
from .pos_access import POSAccessError
from .shift_services import (
    ShiftError, active_shift, close_shift, open_shift, serialize_shift,
)


def _error(exc, code, status):
    return JsonResponse({"error": code, "message": str(exc)}, status=status)


@api_view(["GET", "POST"])
@authentication_classes([BasicAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated, IsPOSOperator])
def cashier_shifts(request):
    try:
        if request.method == "GET":
            shift = active_shift(
                user=request.user,
                location_code=request.query_params.get("location_code", ""),
                terminal_code=request.query_params.get("terminal_code", ""),
            )
            return JsonResponse(serialize_shift(shift))
        data = json.loads(request.body)
        if not isinstance(data, dict):
            raise ShiftError("request body must be an object")
        shift = open_shift(
            user=request.user,
            location_code=data.get("location_code", ""),
            terminal_code=data.get("terminal_code", ""),
            opening_cash_minor=data.get("opening_cash_minor"),
        )
        return JsonResponse(serialize_shift(shift), status=201)
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        return _error(exc, "invalid_shift_request", 400)
    except POSAccessError as exc:
        return _error(exc, "pos_access_denied", 403)


@api_view(["POST"])
@authentication_classes([BasicAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated, IsPOSOperator])
def cashier_shift_close(request, shift_id):
    try:
        data = json.loads(request.body)
        if not isinstance(data, dict):
            raise ShiftError("request body must be an object")
        shift = close_shift(
            user=request.user, shift_id=shift_id,
            closing_cash_minor=data.get("closing_cash_minor"),
        )
        return JsonResponse(serialize_shift(shift))
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        return _error(exc, "invalid_shift_request", 400)
    except POSAccessError as exc:
        return _error(exc, "pos_access_denied", 403)
