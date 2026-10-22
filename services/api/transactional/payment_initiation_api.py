import json
import logging

from django.http import JsonResponse
from rest_framework.authentication import BasicAuthentication, SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated

from .exceptions import (
    InvalidSaleStateError,
    PaymentError,
    PaymentIdempotencyConflictError,
    PaymentNotFoundError,
    SaleNotFoundError,
)
from .models import Payment, Sale
from .outbox_dispatcher import dispatch_outbox_events
from .payment_initiation import (
    PAYMENT_INITIATION_REQUESTED_EVENT,
    request_external_payment_initialization,
)
from .payment_initiation_outbox import make_payment_initiation_outbox_handler
from .payment_providers import PaymentProviderError
from .permissions import IsPOSOperator
from .pos_access import POSAccessError, authorize_pos_scope
from .providers.paystack import PaystackProvider
from .serializers import POSRequestError, parse_paystack_initiation_request

logger = logging.getLogger(__name__)


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
        authorize_pos_scope(
            user=request.user,
            location_code=data.location_code,
            terminal_code=data.terminal_code,
        )
        sale = Sale.objects.get(id=data.sale_id)
    except POSRequestError as exc:
        return JsonResponse(
            {"error": "invalid_request", "message": str(exc)},
            status=400,
        )
    except POSAccessError as exc:
        return JsonResponse(
            {"error": "pos_access_denied", "message": str(exc)},
            status=403,
        )
    except Sale.DoesNotExist:
        return JsonResponse(
            {"error": "sale_not_found", "message": "sale was not found"},
            status=404,
        )

    if sale.location_code != data.location_code:
        return JsonResponse(
            {
                "error": "pos_access_denied",
                "message": "sale does not belong to the requested POS location",
            },
            status=403,
        )

    try:
        provider = PaystackProvider()
        result = request_external_payment_initialization(
            sale_id=data.sale_id,
            customer_email=data.customer_email,
            provider=provider,
            idempotency_key=data.idempotency_key,
        )

        # Opportunistically dispatch after the DB transaction has committed.
        # If this request fails or the process crashes, the durable outbox event
        # remains available for the worker/management command to retry.
        dispatch_outbox_events(
            {
                PAYMENT_INITIATION_REQUESTED_EVENT: make_payment_initiation_outbox_handler(
                    provider
                )
            },
            limit=1,
        )

        payment = Payment.objects.get(id=result.payment_id)
        metadata = payment.provider_metadata or {}
        checkout_url = metadata.get("checkout_url")
        access_code = metadata.get("access_code")
        status_code = 201 if checkout_url or access_code else 202

        return JsonResponse(
            {
                "payment_id": payment.id,
                "sale_id": payment.sale_id,
                "provider": payment.provider,
                "provider_reference": payment.provider_reference,
                "amount_minor": payment.amount_minor,
                "currency": payment.currency,
                "status": payment.status,
                "checkout_url": checkout_url,
                "access_code": access_code,
            },
            status=status_code,
        )

    except PaymentNotFoundError as exc:
        return JsonResponse(
            {"error": "payment_not_found", "message": str(exc)},
            status=404,
        )
    except SaleNotFoundError as exc:
        return JsonResponse(
            {"error": "sale_not_found", "message": str(exc)},
            status=404,
        )
    except PaymentIdempotencyConflictError as exc:
        return JsonResponse(
            {"error": "payment_idempotency_conflict", "message": str(exc)},
            status=409,
        )
    except InvalidSaleStateError as exc:
        return JsonResponse(
            {"error": "invalid_sale_state", "message": str(exc)},
            status=409,
        )
    except PaymentProviderError as exc:
        logger.exception("Unexpected Paystack provider setup failure")
        return JsonResponse(
            {"error": "payment_provider_error", "message": str(exc)},
            status=502,
        )
    except PaymentError as exc:
        return JsonResponse(
            {"error": "payment_error", "message": str(exc)},
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
