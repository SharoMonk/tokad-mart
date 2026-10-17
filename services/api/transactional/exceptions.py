class TransactionalError(Exception):
    """Base exception for expected transactional-domain failures."""


class CheckoutError(TransactionalError):
    """Raised when a checkout cannot satisfy a domain invariant."""


class ProductUnavailableError(CheckoutError):
    """Raised when a requested product is missing or inactive."""


class InventoryMissingError(CheckoutError):
    """Raised when required inventory records do not exist."""


class InsufficientStockError(CheckoutError):
    """Raised when inventory cannot satisfy the requested quantity."""


class PaymentError(TransactionalError):
    """Raised when a payment operation violates a domain invariant."""


class SaleNotFoundError(PaymentError):
    """Raised when the referenced sale does not exist."""


class PaymentNotFoundError(PaymentError):
    """Raised when the referenced payment does not exist."""


class InvalidSaleStateError(PaymentError):
    """Raised when a sale cannot accept or complete a payment."""


class PaymentAmountMismatchError(PaymentError):
    """Raised when a payment amount does not match the sale."""


class PaymentCurrencyMismatchError(PaymentError):
    """Raised when payment and sale currencies differ."""


class PaymentIdempotencyConflictError(PaymentError):
    """Raised when a payment idempotency key is reused differently."""


class ProviderReferenceConflictError(PaymentError):
    """Raised when a provider reference is already used by another payment."""


class SaleLinesMissingError(PaymentError):
    """Raised when a pending sale cannot be finalized because it has no lines."""
