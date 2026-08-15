from dataclasses import dataclass

from .services import CheckoutLine


class POSRequestError(ValueError):
    """Raised when a POS request is structurally invalid."""


@dataclass(frozen=True)
class POSCashSaleRequest:
    lines: list[CheckoutLine]
    location_code: str
    terminal_code: str
    currency: str
    amount_minor: int
    sale_idempotency_key: str
    payment_idempotency_key: str
    provider_reference: str


@dataclass(frozen=True)
class PaystackInitiationRequest:
    sale_id: int
    customer_email: str
    idempotency_key: str
    location_code: str
    terminal_code: str


@dataclass(frozen=True)
class PaymentMutationRequest:
    payment_id: int
    idempotency_key: str
    amount_minor: int | None
    location_code: str
    terminal_code: str


def _required_string(data: dict, field: str) -> str:
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        raise POSRequestError(f"{field} must be a non-empty string")
    return value.strip()


def parse_paystack_initiation_request(data: object) -> PaystackInitiationRequest:
    if not isinstance(data, dict):
        raise POSRequestError("request body must be a JSON object")

    try:
        sale_id = int(data["sale_id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise POSRequestError("sale_id must be an integer") from exc

    if sale_id <= 0:
        raise POSRequestError("sale_id must be positive")

    customer_email = _required_string(data, "customer_email")
    idempotency_key = _required_string(data, "idempotency_key")
    location_code = _required_string(data, "location_code")
    terminal_code = _required_string(data, "terminal_code")

    return PaystackInitiationRequest(
        sale_id=sale_id,
        customer_email=customer_email,
        idempotency_key=idempotency_key,
        location_code=location_code,
        terminal_code=terminal_code,
    )


def parse_payment_mutation_request(data: object) -> PaymentMutationRequest:
    if not isinstance(data, dict):
        raise POSRequestError("request body must be a JSON object")

    try:
        payment_id = int(data["payment_id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise POSRequestError("payment_id must be an integer") from exc

    if payment_id <= 0:
        raise POSRequestError("payment_id must be positive")

    amount = data.get("amount_minor")
    if amount is None:
        amount_minor = None
    else:
        try:
            amount_minor = int(amount)
        except (TypeError, ValueError) as exc:
            raise POSRequestError("amount_minor must be an integer") from exc
        if amount_minor <= 0:
            raise POSRequestError("amount_minor must be positive")

    return PaymentMutationRequest(
        payment_id=payment_id,
        idempotency_key=_required_string(data, "idempotency_key"),
        amount_minor=amount_minor,
        location_code=_required_string(data, "location_code"),
        terminal_code=_required_string(data, "terminal_code"),
    )


def parse_pos_cash_sale_request(data: object) -> POSCashSaleRequest:
    if not isinstance(data, dict):
        raise POSRequestError("request body must be a JSON object")

    required = (
        "lines",
        "location_code",
        "terminal_code",
        "currency",
        "amount_minor",
        "sale_idempotency_key",
        "payment_idempotency_key",
        "provider_reference",
    )

    missing = [field for field in required if field not in data]
    if missing:
        raise POSRequestError(
            f"missing required fields: {', '.join(missing)}"
        )

    lines_data = data["lines"]
    if not isinstance(lines_data, list) or not lines_data:
        raise POSRequestError("lines must be a non-empty list")

    lines: list[CheckoutLine] = []

    for index, item in enumerate(lines_data):
        if not isinstance(item, dict):
            raise POSRequestError(f"line {index} must be an object")

        if "product_id" not in item:
            raise POSRequestError(f"line {index} is missing product_id")

        if "quantity" not in item:
            raise POSRequestError(f"line {index} is missing quantity")

        try:
            product_id = int(item["product_id"])
            quantity = int(item["quantity"])
        except (TypeError, ValueError) as exc:
            raise POSRequestError(
                f"line {index} product_id and quantity must be integers"
            ) from exc

        if product_id <= 0:
            raise POSRequestError(f"line {index} product_id must be positive")

        if quantity <= 0:
            raise POSRequestError(f"line {index} quantity must be positive")

        lines.append(
            CheckoutLine(
                product_id=product_id,
                quantity=quantity,
            )
        )

    location_code = _required_string(data, "location_code")
    terminal_code = _required_string(data, "terminal_code")
    currency = _required_string(data, "currency").upper()

    try:
        amount_minor = int(data["amount_minor"])
    except (TypeError, ValueError) as exc:
        raise POSRequestError("amount_minor must be an integer") from exc

    if amount_minor <= 0:
        raise POSRequestError("amount_minor must be positive")

    return POSCashSaleRequest(
        lines=lines,
        location_code=location_code,
        terminal_code=terminal_code,
        currency=currency,
        amount_minor=amount_minor,
        sale_idempotency_key=_required_string(data, "sale_idempotency_key"),
        payment_idempotency_key=_required_string(data, "payment_idempotency_key"),
        provider_reference=_required_string(data, "provider_reference"),
    )
