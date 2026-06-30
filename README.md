# pykaspi

`pykaspi` is an async Python client for the Kaspi Pay POS private HTTP API.

The project is extracted from `kaspi-pos-automation`, but it is a library, not an HTTP server. Your application owns storage, scheduling, polling, webhooks, and security boundaries.

> This API is unofficial and may change or stop working without notice. Keep device/session credentials private.

## Install

```bash
uv add pykaspi
```

For local development:

```bash
uv sync
```

## Quick Start

```python
import asyncio

from pykaspi import DeviceIdentity, KaspiClient, KaspiSession


async def main() -> None:
    device = DeviceIdentity.generate()

    async with KaspiClient(device=device) as client:
        init = await client.auth.init()
        # Kaspi entrance expects local KZ mobile digits, without +7/8 prefix.
        await client.auth.send_phone(init["process_id"], "7001234567")

        otp = input("SMS code: ")
        session = await client.auth.verify_otp(init["process_id"], otp)

        # Persist these values in your own secure storage.
        print("token_sn:", session.token_sn)
        print("vtoken_secret_b64:", session.vtoken_secret_b64)

        qr = await client.qr.create(session, amount=1000)
        print(qr)


asyncio.run(main())
```

Restore a saved session:

```python
from pykaspi import KaspiSession

session = KaspiSession.from_base64(
    token_sn="...",
    vtoken_secret_b64="...",
    profile_id=12345,
)
```

## API Surface

- `client.auth.init()`
- `client.auth.send_phone(process_id, phone_number)`
- `client.auth.verify_otp(process_id, otp)`
- `client.auth.refresh(session)`
- `client.qr.create(session, amount)`
- `client.qr.status(session, qr_operation_id)`
- `client.invoice.client_info(session, phone_number)`
- `client.invoice.create(session, phone_number, amount, comment="")`
- `client.invoice.details(session, operation_id)`
- `client.invoice.cancel(session, operation_id)`
- `client.invoice.history(session)`
- `client.history.operations(session, end_date)`
- `client.history.details(session, operation_id)`
- `client.refund.create(session, qr_operation_id, return_amount)`
- `client.session.check(session)`

## Device Identity

`DeviceIdentity.generate()` does not write files. If you want stable Kaspi device identity, save it explicitly:

```python
device = DeviceIdentity.generate()
device.save("device.json")

device = DeviceIdentity.load("device.json")
```

## Development

```bash
uv run pytest
```
