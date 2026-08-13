# Tokad Mart Transactional Model Contract

Status: implementation contract

## Purpose

Define the minimum domain model and invariants for the transactional sales engine before application code is introduced.

## Core aggregates

- Product — sellable catalog item and pricing identity.
- InventoryItem — stock state for a product at a location.
- Customer — optional buyer identity attached to a sale.
- Sale — authoritative commercial transaction.
- SaleLine — immutable snapshot of the product, quantity, and effective unit price at sale time.
- Payment — attempt and resulting payment state associated with a sale.
- InventoryMovement — auditable stock delta caused by a business event.
- IdempotencyRecord — durable key/result used to make retryable commands safe.
- AuditEvent — append-oriented record of security- or business-significant changes.

## Money

Money must not be represented with binary floating point. Use integer minor units or an exact decimal representation with an explicit currency.

Every monetary value must have an associated currency. Sale totals, line totals, discounts, taxes, payments, and refunds must use the same explicit arithmetic rules.

## Sale lifecycle

The initial lifecycle is:

`DRAFT -> PENDING_PAYMENT -> COMPLETED`

Failure/cancellation paths must be explicit rather than inferred from missing data. A completed sale is immutable; corrections occur through compensating business operations such as refunds or adjustments.

## Transaction boundary

Checkout is one business command. The implementation must define which writes are committed atomically and which external effects are retried asynchronously.

At minimum, the atomic database boundary must protect:

1. sale creation/finalization;
2. sale-line persistence;
3. inventory reservation/decrement;
4. payment state transition when the payment result is already authoritative;
5. idempotency result persistence.

External payment providers and printing must not be assumed to participate in the database transaction.

## Idempotency

Every externally retryable command must have a stable idempotency key. Replaying the same key with the same semantic request must return the original result without duplicating the business effect.

A reused key with a materially different request must be rejected.

## Inventory

Inventory changes are represented as movements, not silent field mutations. Current stock may be derived or maintained as a projection, but the movement history remains auditable.

The implementation must define the concurrency strategy used when two checkouts compete for the same stock.

## Payment

Payment is a state machine. The system must distinguish at least:

- pending
- authorized/successful
- failed
- cancelled
- refunded

Provider callbacks are untrusted until authenticated/verified and must be idempotent.

## Receipts

A receipt is a representation of a completed transaction, not an independent source of truth. Receipt totals must reconcile exactly with the sale totals.

## Audit

Business events that change money, stock, payment state, or sale state must leave an auditable record containing actor/system identity, timestamp, entity reference, action, and enough metadata to explain the transition without storing secrets.
