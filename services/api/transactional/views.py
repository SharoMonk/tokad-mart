import hashlib
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
    PaymentNotFoundError,
    ProductUnavailableError,
    SaleNotFoundError,
)
from .models import Payment, Sale
from .payment_providers import PaymentProviderError, VerifiedPayment
from .payment_refunds import reconcile_payment, request_refund
from .payment_services import initialize_external_payment, process_pos_cash_sale
from .payment_webhooks import PaymentWebhookError, process_payment_webhook
from .permissions import IsPOSOperator
from .pos_access import POSAccessError, authorize_pos_scope
from .providers.paystack import PaystackProvider
from .serializers import (
    POSRequestError,
    parse_paystack_initiation_request,
    parse_payment_mutation_request,
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
        return JsonResponse({"error": "invalid_json", "message": "request body must contain valid JSON"}, status=400)

    try:
        data = parse_pos_cash_sale_request(payload)
        authorize_pos_scope(user=request.user, location_code=data.location_code, terminal_code=data.terminal_code)
    except POSRequestError as exc:
        return JsonResponse({"error": "invalid_request", "message": str(exc)}, status=400)
    except POSAccessError as exc:
        return JsonResponse({"error": "pos_access_denied", "message": str(exc)}, status=403)

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
        return JsonResponse({"error": "product_unavailable", "message": str(exc)}, status=404)
    except SaleNotFoundError as exc:
        return JsonResponse({"error": "sale_not_found", "message": str(exc)}, status=404)
    except InventoryMissingError as exc:
        return JsonResponse({"error": "inventory_unavailable", "message": str(exc)}, status=409)
    except InsufficientStockError as exc:
        return JsonResponse({"error": "insufficient_stock", "message": str(exc)}, status=409)
    except PaymentError as exc:
        return JsonResponse({"error": "payment_error", "message": str(exc)}, status=409)
    except CheckoutError as exc:
        return JsonResponse({"error": "checkout_error", "message": str(exc)}, status=409)
    except Exception:
        logger.exception("Unexpected POS sale failure")
        return JsonResponse({"error": "internal_error", "message": "POS sale could not be completed"}, status=500)

    return JsonResponse({
        "sale_id": result.sale_id,
        "reference": str(result.reference),
        "payment_id": result.payment_id,
        "total_minor": result.total_minor,
        "currency": result.currency,
        "sale_status": result.sale_status,
        "payment_status": result.payment_status,
        "terminal_code": data.terminal_code,
    }, status=201)


@api_view(["POST"])
@authentication_classes([BasicAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated, IsPOSOperator])
def initiate_paystack_payment(request):
    try:
        payload = json.loads(request.body)
        data = parse_paystack_initiation_request(payload)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "invalid_json", "message": "request body must contain valid JSON"}, status=400)
    except POSRequestError as exc:
        return JsonResponse({"error": "invalid_request", "message": str(exc)}, status=400)

    try:
        authorize_pos_scope(user=request.user, location_code=data.location_code, terminal_code=data.terminal_code)
        sale = Sale.objects.get(id=data.sale_id)
    except POSAccessError as exc:
        return JsonResponse({"error": "pos_access_denied", "message": str(exc)}, status=403)
    except Sale.DoesNotExist:
        return JsonResponse({"error": "sale_not_found", "message": "sale was not found"}, status=404)

    if sale.location_code != data.location_code:
        return JsonResponse({"error": "pos_access_denied", "message": "sale does not belong to the requested POS location"}, status=403)

    try:
        result = initialize_external_payment(
            sale_id=data.sale_id,
            customer_email=data.customer_email,
            provider=PaystackProvider(),
            idempotency_key=data.idempotency_key,
        )
    except PaymentProviderError as exc:
        return JsonResponse({"error": "payment_provider_error", "message": str(exc)}, status=502)
    except PaymentError as exc:
        return JsonResponse({"error": "payment_error", "message": str(exc)}, status=409)
    except Exception:
        logger.exception("Unexpected Paystack initiation failure")
        return JsonResponse({"error": "internal_error", "message": "payment could not be initialized"}, status=500)

    return JsonResponse({
        "payment_id": result.payment_id,
        "sale_id": result.sale_id,
        "provider": result.provider,
        "provider_reference": result.provider_reference,
        "amount_minor": result.amount_minor,
        "currency": result.currency,
        "status": result.status,
        "checkout_url": result.checkout_url,
        "access_code": result.access_code,
    }, status=201)


@api_view(["POST"])
@authentication_classes([BasicAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated, IsPOSOperator])
def refund_payment(request):
    try:
        payload = json.loads(request.body)
        data = parse_payment_mutation_request(payload)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "invalid_json", "message": "request body must contain valid JSON"}, status=400)
    except POSRequestError as exc:
        return JsonResponse({"error": "invalid_request", "message": str(exc)}, status=400)

    try:
        payment = Payment.objects.select_related("sale").get(id=data.payment_id)
        authorize_pos_scope(user=request.user, location_code=data.location_code, terminal_code=data.terminal_code)
    except Payment.DoesNotExist:
        return JsonResponse({"error": "payment_not_found", "message": "payment was not found"}, status=404)
    except POSAccessError as exc:
        return JsonResponse({"error": "pos_access_denied", "message": str(exc)}, status=403)

    if payment.sale.location_code != data.location_code:
        return JsonResponse({"error": "pos_access_denied", "message": "payment does not belong to the requested POS location"}, status=403)

    try:
        result = request_refund(
            payment_id=data.payment_id,
            amount_minor=data.amount_minor,
            provider=PaystackProvider(),
            idempotency_key=data.idempotency_key,
        )
    except PaymentProviderError as exc:
        return JsonResponse({"error": "payment_provider_error", "message": str(exc)}, status=502)
    except PaymentError as exc:
        return JsonResponse({"error": "payment_error", "message": str(exc)}, status=409)
    except Exception:
        logger.exception("Unexpected payment refund failure")
        return JsonResponse({"error": "internal_error", "message": "refund could not be completed"}, status=500)

    return JsonResponse({
        "refund_id": result.refund_id,
        "payment_id": result.payment_id,
        "amount_minor": result.amount_minor,
        "currency": result.currency,
        "status": result.status,
        "provider": result.provider,
    }, status=201)


@api_view(["POST"])
@authentication_classes([BasicAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated, IsPOSOperator])
def reconcile_payment_endpoint(request):
    try:
        payload = json.loads(request.body)
        data = parse_payment_mutation_request(payload)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "invalid_json", "message": "request body must contain valid JSON"}, status=400)
    except POSRequestError as exc:
        return JsonResponse({"error": "invalid_request", "message": str(exc)}, status=400)

    try:
        payment = Payment.objects.select_related("sale").get(id=data.payment_id)
        authorize_pos_scope(user=request.user, location_code=data.location_code, terminal_code=data.terminal_code)
    except Payment.DoesNotExist:
        return JsonResponse({"error": "payment_not_found", "message": "payment was not found"}, status=404)
    except POSAccessError as exc:
        return JsonResponse({"error": "pos_access_denied", "message": str(exc)}, status=403)

    if payment.sale.location_code != data.location_code:
        return JsonResponse({"error": "pos_access_denied", "message": "payment does not belong to the requested POS location"}, status=403)

    try:
        result = reconcile_payment(payment_id=data.payment_id, provider=PaystackProvider())
    except PaymentProviderError as exc:
        return JsonResponse({"error": "payment_provider_error", "message": str(exc)}, status=502)
    except PaymentError as exc:
        return JsonResponse({"error": "payment_error", "message": str(exc)}, status=409)
    except Exception:
        logger.exception("Unexpected payment reconciliation failure")
        return JsonResponse({"error": "internal_error", "message": "payment could not be reconciled"}, status=500)

    return JsonResponse({
        "payment_id": result.payment_id,
        "provider": result.provider,
        "provider_reference": result.provider_reference,
        "local_status": result.local_status,
        "provider_status": result.provider_status,
        "amount_minor": result.amount_minor,
        "currency": result.currency,
        "matches": result.matches,
    }, status=200)


@api_view(["POST"])
@authentication_classes([])
@permission_classes([])
def paystack_webhook(request):
    raw_body = request.body
    signature = request.headers.get("x-paystack-signature", "")
    try:
        provider = PaystackProvider()
    except PaymentProviderError as exc:
        return JsonResponse({"error": "payment_provider_error", "message": str(exc)}, status=500)

    if not signature or not provider.verify_webhook_signature(payload=raw_body, signature=signature):
        return JsonResponse({"error": "invalid_signature", "message": "Paystack webhook signature is invalid"}, status=400)

    try:
        payload = json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "invalid_json", "message": "webhook body must contain valid JSON"}, status=400)

    if payload.get("event") != "charge.success":
        return JsonResponse({"status": "ignored", "event": payload.get("event")}, status=200)

    data = payload.get("data")
    if not isinstance(data, dict):
        return JsonResponse({"error": "invalid_webhook", "message": "Paystack webhook data is missing"}, status=400)

    provider_reference = data.get("reference")
    if not provider_reference:
        return JsonResponse({"error": "invalid_webhook", "message": "Paystack webhook reference is missing"}, status=400)

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
        return JsonResponse({"error": "payment_not_found", "message": str(exc)}, status=404)
    except PaymentWebhookError as exc:
        return JsonResponse({"error": "webhook_rejected", "message": str(exc)}, status=400)
    except Exception:
        logger.exception("Unexpected Paystack webhook failure")
        return JsonResponse({"error": "internal_error", "message": "webhook could not be processed"}, status=500)

    return JsonResponse({
        "status": "ok",
        "event_id": result.event_id,
        "payment_id": result.payment_id,
        "payment_status": result.payment_status,
        "sale_id": result.sale_id,
        "sale_status": result.sale_status,
        "already_processed": result.already_processed,
    }, status=200)
