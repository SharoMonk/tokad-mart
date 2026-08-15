import hashlib
import json
import logging

from django.http import JsonResponse

from rest_framework.authentication import BasicAuthentication, SessionAuthentication
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.permissions import IsAuthenticated

from .exceptions import (
    CheckoutError,
    InsufficientStockError,
    InventoryMissingError,
    PaymentError,
    PaymentNotFoundError,
    ProductUnavailableError,
    SaleNotFoundError,
)
from .models import Sale
from .payment_providers import PaymentProviderError, VerifiedPayment
from .payment_services import initialize_external_payment, process_pos_cash_sale
from .payment_webhooks import PaymentWebhookError, process_payment_webhook
from .permissions import IsPOSOperator
from .pos_access import POSAccessError, authorize_pos_scope
from .providers.paystack import PaystackProvider
from .serializers import (
    POSRequestError,
    parse_paystack_initiation_request,
    parse_pos_cash_sale_request,
)

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
        authorize_pos_scope(
            user=request.user,
            location_code=data.location_code,
            terminal_code=data.terminal_code,
        )
    except POSAccessError as exc:
        return JsonResponse(
            {
                "error": "pos_access_denied",
                "message": str(exc),
            },
            status=403,
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
            "terminal_code": data.terminal_code,
        },
        status=201,
    )


@api_view(["POST"])
@authentication_classes([BasicAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated, IsPOSOperator])
def initiate_paystack_payment(request):
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
        data = parse_paystack_initiation_request(payload)
    except POSRequestError as exc:
        return JsonResponse(
            {
                "error": "invalid_request",
                "message": str(exc),
            },
            status=400,
        )

    location_code = payload.get("location_code")
    terminal_code = payload.get("terminal_code")

    if not isinstance(location_code, str) or not location_code.strip():
        return JsonResponse(
            {
                "error": "invalid_request",
                "message": "location_code must be a non-empty string",
            },
            status=400,
        )

    if not isinstance(terminal_code, str) or not terminal_code.strip():
        return JsonResponse(
            {
                "error": "invalid_request",
                "message": "terminal_code must be a non-empty string",
            },
            status=400,
        )

    try:
        authorize_pos_scope(
            user=request.user,
            location_code=location_code.strip(),
            terminal_code=terminal_code.strip(),
        )
    except POSAccessError as exc:
        return JsonResponse(
            {
                "error": "pos_access_denied",
                "message": str(exc),
            },
            status=403,
        )

    try:
        sale = Sale.objects.get(id=data.sale_id)
    except Sale.DoesNotExist:
        return JsonResponse(
            {
                "error": "sale_not_found",
                "message": "sale was not found",
            },
            status=404,
        )

    if sale.location_code != location_code.strip():
        return JsonResponse(
            {
                "error": "pos_access_denied",
                "message": "sale does not belong to the requested POS location",
            },
            status=403,
        )

    try:
        result = initialize_external_payment(
            sale_id=data.sale_id,
            customer_email=data.customer_email,
            provider=PaystackProvider(),
            idempotency_key=data.idempotency_key,
        )
    except PaymentProviderError as exc:
        return JsonResponse(
            {
                "error": "payment_provider_error",
                "message": str(exc),
            },
            status=502,
        )
    except PaymentError as exc:
        return JsonResponse(
            {
                "error": "payment_error",
                "message": str(exc),
            },
            status=409,
        )
    except Exception:
        logger.exception("Unexpected Paystack initiation failure")
        return JsonResponse(
            {
                "error": "internal_error",
                "message": "payment could not be initialized",
            },
            status=500,
        )

    return JsonResponse(
        {
            "payment_id": result.payment_id,
            "sale_id": result.sale_id,
            "provider": result.provider,
            "provider_reference": result.provider_reference,
            "amount_minor": result.amount_minor,
            "currency": result.currency,
            "status": result.status,
            "checkout_url": result.checkout_url,
            "access_code": result.access_code,
        },
        status=201,
    )


@api_view(["POST"])
@authentication_classes([])
@permission_classes([])
def paystack_webhook(request):
    raw_body = request.body
    signature = request.headers.get("x-paystack-signature", "")

    try:
        provider = PaystackProvider()
    except PaymentProviderError as exc:
        return JsonResponse(
            {
                "error": "payment_provider_error",
                "message": str(exc),
            },
            status=500,
        )

    if not signature or not provider.verify_webhook_signature(
        payload=raw_body,
        signature=signature,
    ):
        return JsonResponse(
            {
                "error": "invalid_signature",
                "message": "Paystack webhook signature is invalid",
            },
            status=400,
        )

    try:
        payload = json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse(
            {
                "error": "invalid_json",
                "message": "webhook body must contain valid JSON",
            },
            status=400,
        )

    if payload.get("event") != "charge.success":
        return JsonResponse(
            {
                "status": "ignored",
                "event": payload.get("event"),
            },
            status=200,
        )

    data = payload.get("data")
    if not isinstance(data, dict):
        return JsonResponse(
            {
                "error": "invalid_webhook",
                "message": "Paystack webhook data is missing",
            },
            status=400,
        )

    provider_reference = data.get("reference")
    if not provider_reference:
        return JsonResponse(
            {
                "error": "invalid_webhook",
                "message": "Paystack webhook reference is missing",
            },
            status=400,
        )

    event_id = str(data.get("id") or hashlib.sha256(raw_body).hexdigest())

    try:
        result = process_payment_webhook(
            provider=provider.name,
            event_id=event_id,
            provider_reference=str(provider_reference),
            verified=VerifiedPayment(
                provider=provider.name,
                provider_reference=str(provider_reference),
                amount_minor=int(data.get("amount") or 0),
                currency=str(data.get("currency") or "").upper(),
                succeeded=str(data.get("status")) == "success",
            ),
            payload=payload,
        )
    except PaymentNotFoundError as exc:
        return JsonResponse(
            {
                "error": "payment_not_found",
                "message": str(exc),
            },
            status=404,
        )
    except PaymentWebhookError as exc:
        return JsonResponse(
            {
                "error": "webhook_rejected",
                "message": str(exc),
            },
            status=400,
        )
    except Exception:
        logger.exception("Unexpected Paystack webhook failure")
        return JsonResponse(
            {
                "error": "internal_error",
                "message": "webhook could not be processed",
            },
            status=500,
        )

    return JsonResponse(
        {
            "status": "ok",
            "event_id": result.event_id,
            "payment_id": result.payment_id,
            "payment_status": result.payment_status,
            "sale_id": result.sale_id,
            "sale_status": result.sale_status,
            "already_processed": result.already_processed,
        },
        status=200,
    )
