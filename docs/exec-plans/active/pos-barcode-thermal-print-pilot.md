# POS hardware pilot — keyboard-wedge scanner and thermal print

The pilot remains **cash-only** and uses the canonical Django `transactional` sale, payment, stock and receipt endpoints. No additional checkout, inventory or customer ledger has been created.

## Barcode / SKU scanning

The POS now has a dedicated barcode / SKU field. USB scanners configured as a **keyboard wedge** type into the focused input, commonly ending with Enter. The handler queries the authorized `pos/catalog/` endpoint and adds exactly one item only when the returned SKU matches the scanned string in full (case-insensitively). It rejects missing, ambiguous and out-of-stock matches. Scanning requires an open cashier shift and is disabled during checkout or while an uncertain checkout awaits retry.

**Important:** The current model stores a unique `Product.sku` but does **not** have a separate EAN/UPC barcode field. For this pilot, the barcode labels must encode the product SKU exactly. A physical UPC/EAN code that differs from the SKU will **not** match; adding a dedicated barcode mapping/index and validation is a later task.

To try without hardware: focus the dedicated input, type a product's exact SKU such as `DEMO-RICE-001`, then press Enter. For a physical reader, configure a carriage-return/Enter suffix and test after opening a shift. A scanner that behaves as a serial device, or that requires a proprietary driver, is not supported by this browser-only pilot.

## Receipt printer

After successful checkout, choose **View last receipt** to fetch the server-authoritative receipt. Choose **Print receipt** to invoke the browser/OS print dialog with the receipt as the only visible print region.

The CSS targets a 72mm print area suitable for typical 80mm roll paper (subject to printer and driver margins). Select the appropriate installed printer and paper width in the OS/browser dialog; the browser cannot silently select a physical printer or cut paper. **58mm, ESC/POS direct printing, cash drawer control, and auto-cut require a separate kiosk/print-bridge integration.**

Printed amount and line details come from the canonical authenticated receipt API, not the mutable browser cart. A new completed sale clears the old displayed receipt so an operator cannot mistake it for the latest sale.

## Acceptance procedure

1. Pull `feat/transactional-concurrency` and install existing dependencies if necessary.
2. In `services/api` run:
   ```bash
   uv run python -m pytest -q --reuse-db transactional/tests/test_pos_scanner_receipt.py
   uv run python -m pytest -q --reuse-db transactional/
   ```
3. In the Next.js root run `npm run build`. Start the Django API and Next.js with the appropriate `TRANSACTIONAL_API_ORIGIN`.
4. Sign in and open a cashier shift. Focus **Barcode / SKU scanner**. Type/scan the exact SKU of a stocked item and send Enter. Confirm that precisely one quantity is added and repeated scans increase quantity only up to available stock.
5. Scan an unknown code: confirm the item is not added. Remove stock / scan an unavailable code: confirm the item is not added.
6. Complete a cash checkout, view the authenticated receipt, and check reference, quantity, totals and payments against the sale. Print to preview (or to the installed 80mm printer). Confirm the POS screen/navigation is not printed.
7. Confirm checkout retries still produce one sale and one stock deduction by running existing idempotency regression tests.

No printer manufacturer/firmware is assumed. Exact margins, text legibility, currency symbol support, paper cut and print dialog configuration must be validated on the actual device before accepting shop hardware.
