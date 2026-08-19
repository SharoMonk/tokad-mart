from dataclasses import dataclass
from typing import Protocol


class PaymentProviderError(Exception):
    """Raised when a payment provider cannot complete an operation."""


@dataclass(frozen=True)
class PaymentIntent:
    provider: str
    provider_reference: str
    amount_minor: int
    currency: str
    checkout_url: str | None = None
    access_code: str | None = None


@dataclass(frozen=True)
class VerifiedPayment:
    provider: str
    provider_reference: str
    amount_minor: int
    currency: str
    succeeded: bool


class PaymentProvider(Protocol):
    name: str

    def initiate_payment(
        self,
        *,
        amount_minor: int,
        currency: str,
        reference: str,
        customer_email: str | None = None,
    ) -> PaymentIntent:
        ...

    def verify_payment(
        self,
        *,
        provider_reference: str,
    ) -> VerifiedPayment:
        ...

    def refund_payment(
        self,
        *,
        provider_reference: str,
        amount_minor: int | None = None,
    ) -> None:
        ...


def validate_verified_payment(
    *,
    expected_amount_minor: int,
    expected_currency: str,
    verified: VerifiedPayment,
) -> None:
    if not verified.succeeded:
        raise PaymentProviderError("provider reports payment was not successful")

    if verified.amount_minor != expected_amount_minor:
        raise PaymentProviderError("provider payment amount does not match sale total")

    if verified.currency.upper() != expected_currency.upper():
        raise PaymentProviderError("provider payment currency does not match sale currency")


__all__ = [
    "PaymentIntent",
    "PaymentProvider",
    "PaymentProviderError",
    "VerifiedPayment",
    "validate_verified_payment",
]
