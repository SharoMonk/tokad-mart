import json
import logging

from django.http import JsonResponse

from rest_framework.authentication import BasicAuthentication, SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated

from .exceptions import (
    CheckoutError,
    InsufficientStockError,
    InventoryMissingError,
    PaymentError,
    ProductUnavailableError,
    SaleNotFoundError,
)
from .payment_services import process_pos_cash_sale
from .permissions import IsPOSOperator
from .serializers import POSRequestError, parse_pos_cash_sale_request

logger = logging.getLogger(__name__)


def health(_request):
    return JsonResponse({"status": "ok", "service": "transactional"})


@api_view(["POST"])
@authentication_classes([BasicAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated, IsPOSOperator])
def pos_cash_sale(request):
    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse(
            {
                "error": "invalid_json",
                "message": "request body must contain valid JSON",
            },
            status=400,
        )

    try:
        data = parse_pos_cash_sale_request(payload)
    except POSRequestError as exc:
        return JsonResponse(
            {
                "error": "invalid_request",
                "message": str(exc),
            },
            status=400,
        )

    try:
        result = process_pos_cash_sale(
            lines=data.lines,
            location_code=data.location_code,
            currency=data.currency,
            amount_minor=data.amount_minor,
            sale_idempotency_key=data.sale_idempotency_key,
            payment_idempotency_key=data.payment_idempotency_key,
            provider_reference=data.provider_reference,
        )

    except ProductUnavailableError as exc:
        return JsonResponse(
            {
                "error": "product_unavailable",
                "message": str(exc),
            },
            status=404,
        )

    except SaleNotFoundError as exc:
        return JsonResponse(
            {
                "error": "sale_not_found",
                "message": str(exc),
            },
            status=404,
        )

    except InventoryMissingError as exc:
        return JsonResponse(
            {
                "error": "inventory_unavailable",
                "message": str(exc),
            },
            status=409,
        )

    except InsufficientStockError as exc:
        return JsonResponse(
            {
                "error": "insufficient_stock",
                "message": str(exc),
            },
            status=409,
        )

    except PaymentError as exc:
        return JsonResponse(
            {
                "error": "payment_error",
                "message": str(exc),
            },
            status=409,
        )

    except CheckoutError as exc:
        return JsonResponse(
            {
                "error": "checkout_error",
                "message": str(exc),
            },
            status=409,
        )

    except Exception:
        logger.exception("Unexpected POS sale failure")

        return JsonResponse(
            {
                "error": "internal_error",
                "message": "POS sale could not be completed",
            },
            status=500,
        )

    return JsonResponse(
        {
            "sale_id": result.sale_id,
            "reference": str(result.reference),
            "payment_id": result.payment_id,
            "total_minor": result.total_minor,
            "currency": result.currency,
            "sale_status": result.sale_status,
            "payment_status": result.payment_status,
        },
        status=201,
    )
