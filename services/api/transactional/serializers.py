from dataclasses import dataclass

from .models import Payment
from .services import CheckoutLine


class POSRequestError(ValueError):
    """Raised when a POS request is structurally invalid."""


@dataclass(frozen=True)
class POSCashSaleRequest:
    lines: list[CheckoutLine]
    location_code: str
    currency: str
    amount_minor: int
    sale_idempotency_key: str
    payment_idempotency_key: str
    provider_reference: str


def parse_pos_cash_sale_request(data: object) -> POSCashSaleRequest:
    if not isinstance(data, dict):
        raise POSRequestError("request body must be a JSON object")

    required = (
        "lines",
        "location_code",
        "currency",
        "amount_minor",
        "sale_idempotency_key",
        "payment_idempotency_key",
        "provider_reference",
    )

    missing = [
        field
        for field in required
        if field not in data
    ]

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
            raise POSRequestError(
                f"line {index} must be an object"
            )

        if "product_id" not in item:
            raise POSRequestError(
                f"line {index} is missing product_id"
            )

        if "quantity" not in item:
            raise POSRequestError(
                f"line {index} is missing quantity"
            )

        try:
            product_id = int(item["product_id"])
            quantity = int(item["quantity"])
        except (TypeError, ValueError):
            raise POSRequestError(
                f"line {index} product_id and quantity must be integers"
            )

        if product_id <= 0:
            raise POSRequestError(
                f"line {index} product_id must be positive"
            )

        if quantity <= 0:
            raise POSRequestError(
                f"line {index} quantity must be positive"
            )

        lines.append(
            CheckoutLine(
                product_id=product_id,
                quantity=quantity,
            )
        )

    location_code = data["location_code"]
    currency = data["currency"]

    if not isinstance(location_code, str) or not location_code.strip():
        raise POSRequestError("location_code must be a non-empty string")

    if not isinstance(currency, str) or not currency.strip():
        raise POSRequestError("currency must be a non-empty string")

    currency = currency.upper()

    try:
        amount_minor = int(data["amount_minor"])
    except (TypeError, ValueError):
        raise POSRequestError("amount_minor must be an integer")

    if amount_minor <= 0:
        raise POSRequestError("amount_minor must be positive")

    string_fields = (
        "sale_idempotency_key",
        "payment_idempotency_key",
        "provider_reference",
    )

    values: dict[str, str] = {}

    for field in string_fields:
        value = data[field]

        if not isinstance(value, str) or not value.strip():
            raise POSRequestError(
                f"{field} must be a non-empty string"
            )

        values[field] = value.strip()

    return POSCashSaleRequest(
        lines=lines,
        location_code=location_code.strip(),
        currency=currency,
        amount_minor=amount_minor,
        sale_idempotency_key=values["sale_idempotency_key"],
        payment_idempotency_key=values["payment_idempotency_key"],
        provider_reference=values["provider_reference"],
    )