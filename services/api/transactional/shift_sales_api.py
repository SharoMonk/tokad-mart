"""Shift-required cash checkout; writes to existing Sale/Payment/InventoryMovement tables."""
import json
import logging

from django.db import transaction
from django.http import JsonResponse
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated

from .exceptions import CheckoutError, InsufficientStockError, InventoryMissingError, PaymentError, ProductUnavailableError
from .models import CashierShift, Sale
from .payment_services import process_pos_cash_sale
from .permissions import IsPOSOperator
from .pos_access import POSAccessError, authorize_pos_scope
from .serializers import POSRequestError, parse_pos_cash_sale_request

logger = logging.getLogger(__name__)


@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsPOSOperator])
def shift_cash_sale(request):
    try:
        payload = json.loads(request.body)
        data = parse_pos_cash_sale_request(payload)
        shift_id = payload.get("shift_id")
        if type(shift_id) is not int or shift_id < 1:
            raise POSRequestError("shift_id must be a positive integer")
        scope = authorize_pos_scope(
            user=request.user,
            location_code=data.location_code,
            terminal_code=data.terminal_code,
        )
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({"error": "invalid_json"}, status=400)
    except POSRequestError as exc:
        return JsonResponse({"error": "invalid_request", "message": str(exc)}, status=400)
    except POSAccessError as exc:
        return JsonResponse({"error": "pos_access_denied", "message": str(exc)}, status=403)

    try:
        with transaction.atomic():
            shift = CashierShift.objects.select_for_update().get(pk=shift_id)
            if (
                shift.status != CashierShift.Status.OPEN
                or shift.operator_id != scope.operator.pk
                or shift.location_id != scope.location.pk
                or shift.terminal_id != scope.terminal.pk
            ):
                return JsonResponse({"error": "shift_not_active"}, status=409)
            result = process_pos_cash_sale(
                lines=data.lines,
                location_code=data.location_code,
                currency=data.currency,
                amount_minor=data.amount_minor,
                sale_idempotency_key=data.sale_idempotency_key,
                payment_idempotency_key=data.payment_idempotency_key,
                provider_reference=data.provider_reference,
            )
            sale = Sale.objects.select_for_update().get(pk=result.sale_id)
            if sale.shift_id is None:
                sale.shift = shift
                sale.save(update_fields=["shift"])
            elif sale.shift_id != shift.pk:
                raise CheckoutError("sale is already assigned to a different shift")
    except CashierShift.DoesNotExist:
        return JsonResponse({"error": "shift_not_found"}, status=404)
    except (InventoryMissingError, InsufficientStockError, PaymentError, CheckoutError) as exc:
        return JsonResponse({"error": "checkout_conflict", "message": str(exc)}, status=409)
    except ProductUnavailableError as exc:
        return JsonResponse({"error": "product_unavailable", "message": str(exc)}, status=404)
    except Exception:
        logger.exception("Shift cash checkout failed")
        return JsonResponse({"error": "internal_error"}, status=500)

    return JsonResponse({
        "sale_id": result.sale_id,
        "reference": str(result.reference),
        "payment_id": result.payment_id,
        "total_minor": result.total_minor,
        "currency": result.currency,
        "sale_status": result.sale_status,
        "payment_status": result.payment_status,
        "shift_id": shift.pk,
        "terminal_code": data.terminal_code,
    }, status=201)
