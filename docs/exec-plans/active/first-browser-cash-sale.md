# Sprint 1: first browser cash sale (development only)

This walkthrough seeds **demo** data in the canonical `services/api` Django database, not the legacy `backend` database. Use a disposable development database. The command refuses to run unless `DJANGO_DEBUG=1` and `--confirm-demo` are supplied.

## Preparation

In a terminal, from `services/api`:

```bash
uv sync --extra dev
uv run python manage.py migrate
uv run python manage.py seed_demo_pos --confirm-demo
uv run python manage.py changepassword demo_cashier
uv run python manage.py runserver 127.0.0.1:8000
```

`changepassword` prompts interactively. Never put cashier passwords in shell arguments, documentation, or Git. The seed command creates `demo_cashier` with an unusable password on first run; existing user passwords are not reset.

Expected demo location: `MAIN`; terminal: `MAIN-01`. Demo products: Rice 1kg (₦3,500), Sugar 1kg (₦2,200), Bath Soap (₦850), Powdered Milk (₦1,750). Quantities are seeded once and **never reset** by re-running the command.

In a second terminal, at the repository root:

```bash
npm install
npm run build
npm run dev
```

Open http://localhost:3000 and log in with `demo_cashier` and the password set interactively. Search for `Demo`, `Rice`, or `DEMO-RICE-001`, select an item, and click **Complete cash sale**. Open **View last receipt** and check that the printed amount equals the checkout total. Re-search to verify stock was deducted exactly once.

## Verification

```bash
cd services/api
uv run --extra dev python -m pytest -q transactional/tests/test_seed_demo_pos.py -vv
uv run --extra dev python -m pytest -q transactional/tests/test_pos_read_api.py -vv
uv run --extra dev python -m pytest -q transactional/
```

## Limitations

- Cash-only pilot; receipt uses browser print, not yet a thermal bridge.
- The POS uses HTTP Basic credentials in memory; use only a trusted local development environment. Do not expose this setup to the internet.
- Root `docker-compose.yml` currently targets the legacy `backend` and is not the canonical POS setup.
- Do not populate demo data in a real shop database or treat these prices as real inventory prices.
- If a checkout response is lost, the UI preserves the attempt key. Retry the same cart rather than creating a new sale.
- A cashier shift feature and secure session login are not yet implemented on the canonical backend.
