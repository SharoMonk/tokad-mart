# Tokad Mart Local Print Bridge

The POS/backend deliberately separates transaction completion from physical printing.

The future bridge should run on a shop-network workstation or server and expose a narrowly scoped local API such as:

- `POST /print/receipt`
- `POST /print/test`
- `GET /health`

It should accept only authenticated/locally trusted receipt payloads, render ESC/POS for configured thermal printers, queue failed jobs, and support retries/reprints.

It must **never create, modify, or cancel sales**. A failed printer must not roll back a committed sale.

Recommended implementation choices for the bridge:
- Python
- FastAPI
- python-escpos
- local SQLite queue
- mDNS/Avahi discovery where useful

The backend should eventually send a committed receipt job to this bridge through an authenticated LAN connection.
