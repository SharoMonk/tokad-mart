# Physical barcode mapping milestone

The existing keyboard-wedge scanner now uses a dedicated exact-match endpoint rather than searching product names or interpreting barcodes as SKUs only.

## Canonical data model

- `Product.sku` remains the stable internal SKU and is unchanged.
- `ProductBarcode(code, product)` stores manufacturer or store-generated barcode strings, supporting multiple different codes for a single product, with global uniqueness per code. `code` is a string: **leading zeros are preserved**.
- `0013_product_barcode.py` adds only this mapping table. Existing sales, prices, inventory and payments are unchanged.
- `GET /api/transactional/pos/barcode/?location_code=MAIN&terminal_code=MAIN-01&code=0012345678905` checks session authentication, assigned cashier location and terminal, and exact barcode / SKU. An ambiguous collision between another product's SKU and the physical barcode returns HTTP 409 instead of selling the wrong item.
- The POS scanner input uses this endpoint and adds only exact matches, one item per Enter. Physical scanners must be configured to act as USB keyboard-wedge devices with an Enter suffix.

## Set up in development

```bash
git pull --ff-only origin feat/transactional-concurrency
cd services/api
uv run python manage.py migrate
uv run python manage.py makemigrations --check --dry-run

# Replace the example code with the actual scanned code on your product.
uv run python manage.py bind_product_barcode --sku DEMO-RICE-001 --barcode 0012345678905

uv run python -m pytest -q --reuse-db --create-db \
  transactional/tests/test_pos_barcode_lookup.py \
  transactional/tests/test_bind_product_barcode.py \
  transactional/tests/test_pos_scanner_receipt.py
uv run python -m pytest -q --reuse-db transactional/
```

From the Next.js root run `npm run build` and restart both servers as necessary.

In the browser log in, open a shift, focus **Barcode / SKU scanner**, type the exact barcode assigned above, and press Enter. Verify the intended item, price, quantity and available stock. Complete a test cash sale and check the authoritative receipt.

## Boundaries

EAN/UPC checksum validation, packaging-level multipliers, variable-weight labels, label printing and bulk CSV imports are **not implemented**. Bind only verified barcodes for correctly identified products. This first mapping command is server-side and requires staff access to the host; a supervisor-controlled bulk catalog UI can be added next.

The mapping API never changes stock or prices; checkout continues through the existing shift-authorized transactional endpoint. Hardware and frontend builds have not been executed by GitHub editing tools.
