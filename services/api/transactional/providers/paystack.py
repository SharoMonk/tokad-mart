import hashlib
import hmac
import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from ..payment_providers import PaymentIntent, PaymentProviderError, VerifiedPayment


class PaystackProvider:
    name = "PAYSTACK"

    def __init__(
        self,
        *,
        secret_key: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self.secret_key = secret_key or os.getenv("PAYSTACK_SECRET_KEY", "")
        self.base_url = (
            base_url or os.getenv("PAYSTACK_BASE_URL", "https://api.paystack.co")
        ).rstrip("/")
        self.timeout = timeout or float(os.getenv("PAYSTACK_TIMEOUT_SECONDS", "10"))

        if not self.secret_key:
            raise PaymentProviderError("PAYSTACK_SECRET_KEY is not configured")

    def _request(
        self,
        *,
        method: str,
        path: str,
        payload: dict | None = None,
    ) -> dict:
        body = None
        headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Accept": "application/json",
        }

        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = Request(
            f"{self.base_url}{path}",
            data=body,
            headers=headers,
            method=method,
        )

        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise PaymentProviderError(
                f"Paystack API request failed with HTTP {exc.code}: {detail}"
            ) from exc
        except URLError as exc:
            raise PaymentProviderError("Paystack API request failed") from exc

        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PaymentProviderError("Paystack API returned invalid JSON") from exc

        if not data.get("status"):
            raise PaymentProviderError(
                str(data.get("message") or "Paystack API request failed")
            )

        return data

    def initiate_payment(
        self,
        *,
        amount_minor: int,
        currency: str,
        reference: str,
        customer_email: str | None = None,
    ) -> PaymentIntent:
        if not customer_email:
            raise PaymentProviderError("customer email is required for Paystack")

        response = self._request(
            method="POST",
            path="/transaction/initialize",
            payload={
                "amount": str(amount_minor),
                "currency": currency.upper(),
                "email": customer_email,
                "reference": reference,
            },
        )

        data = response.get("data") or {}
        provider_reference = str(data.get("reference") or reference)
        checkout_url = data.get("authorization_url")
        access_code = data.get("access_code")

        if not checkout_url or not access_code:
            raise PaymentProviderError(
                "Paystack initialization response is missing checkout data"
            )

        return PaymentIntent(
            provider=self.name,
            provider_reference=provider_reference,
            amount_minor=amount_minor,
            currency=currency.upper(),
            checkout_url=checkout_url,
            access_code=access_code,
        )

    def verify_payment(
        self,
        *,
        provider_reference: str,
    ) -> VerifiedPayment:
        response = self._request(
            method="GET",
            path=f"/transaction/verify/{quote(provider_reference, safe='')}",
        )

        data = response.get("data") or {}

        return VerifiedPayment(
            provider=self.name,
            provider_reference=str(data.get("reference") or provider_reference),
            amount_minor=int(data.get("amount") or 0),
            currency=str(data.get("currency") or "").upper(),
            succeeded=str(data.get("status")) == "success",
        )

    def refund_payment(
        self,
        *,
        provider_reference: str,
        amount_minor: int | None = None,
    ) -> None:
        payload = {"transaction": provider_reference}
        if amount_minor is not None:
            payload["amount"] = amount_minor

        self._request(
            method="POST",
            path="/refund",
            payload=payload,
        )

    def verify_webhook_signature(
        self,
        *,
        payload: bytes,
        signature: str,
    ) -> bool:
        digest = hmac.new(
            self.secret_key.encode("utf-8"),
            payload,
            hashlib.sha512,
        ).hexdigest()

        return hmac.compare_digest(digest, signature)
