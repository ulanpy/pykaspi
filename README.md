# pykaspi

`pykaspi` is an async Python client for the Kaspi Pay POS private HTTP API.

The project is extracted from `kaspi-pos-automation`, but it is a library, not an HTTP server. Your application owns storage, scheduling, polling, webhooks, and security boundaries.

> This API is unofficial and may change or stop working without notice. Keep device/session credentials private.

## Install

```bash
pip install pykaspi
```

```bash
poetry add pykaspi
```

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

        # Persist session.token_sn, session.vtoken_secret_b64,
        # session.ecdh_private_key_b64, and org fields in secure storage.

        qr = await client.qr.create(session, amount=1000)
        print(qr.data.qr_operation_id)
        print(qr.data.qr_token)


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

## Pydantic Models

Payment methods return flexible Pydantic models:

```python
qr = await client.qr.create(session, amount=1000)

print(qr.ok)
print(qr.status_code)
print(qr.data.qr_operation_id)
print(qr.data.qr_token)
```

Kaspi can add fields without warning, so pykaspi models use `extra="allow"`. Unknown fields are preserved in `model_extra` and can be accessed as attributes when their names are valid Python identifiers:

```python
raw = qr.raw()
extra = qr.data.model_extra
```

Known Kaspi `PascalCase` fields are exposed as Pythonic `snake_case` attributes. For example, `QrOperationId` becomes `qr.data.qr_operation_id`.

## Device Identity

`DeviceIdentity.generate()` does not write files. If you want stable Kaspi device identity, save it explicitly:

```python
device = DeviceIdentity.generate()
device.save("device.json")

device = DeviceIdentity.load("device.json")
```

`device.json` is not enough to call payment methods without SMS. It only stores the virtual mobile device identity and signing key. To skip SMS on later runs, also persist the Kaspi session values returned by `auth.verify_otp()`:

```json
{
  "token_sn": "...",
  "vtoken_secret_b64": "...",
  "ecdh_private_key_b64": "...",
  "profile_id": 12345,
  "organization_id": 67890
}
```

The local examples store this as `session.json`, which is ignored by git. Treat both `device.json` and `session.json` as secrets. `ecdh_private_key_b64` is needed for SignInLite refresh after your process restarts.

## Session Lifecycle

Kaspi does not expose a reliable `expires_at` value for this private session. Treat a session as valid only while `client.session.check(session)` succeeds.

Recommended backend flow:

```python
from pykaspi import KaspiReauthRequiredError


async def ensure_session(client, session, save_session, require_sms_reauth):
    check = await client.session.check(session)
    if check.active:
        return session

    try:
        refreshed = await client.auth.refresh(session)
    except KaspiReauthRequiredError:
        await require_sms_reauth()
        raise

    await save_session(refreshed)
    return refreshed
```

`auth.refresh()` uses Kaspi SignInLite and can often recover an inactive session, but it is not guaranteed forever. If Kaspi rejects refresh, pykaspi raises `KaspiReauthRequiredError`; your app should mark the merchant as requiring SMS re-auth and notify the responsible user.

## Live Examples

Create a remote invoice:

```bash
PYKASPI_AUTH_PHONE="+77001234567" \
PYKASPI_CLIENT_PHONE="+77007654321" \
uv run python examples/live_invoice.py
```

Create a QR payment token:

```bash
PYKASPI_AUTH_PHONE="+77001234567" \
uv run python examples/live_qr.py
```

The example values are placeholders. Use a real Kaspi Pay cashier phone for
`PYKASPI_AUTH_PHONE` and a real Kaspi customer phone for `PYKASPI_CLIENT_PHONE`.

## Development

```bash
uv run pytest
```
