from __future__ import annotations

import asyncio
from pathlib import Path

from pykaspi import DeviceIdentity, KaspiClient


AUTH_PHONE = "+77071027599"
# Remote invoice recipient. Use a real personal Kaspi client phone, not necessarily the cashier phone.
CLIENT_PHONE = "+77072818516"
DEVICE_FILE = Path("device.json")


def load_or_create_device() -> DeviceIdentity:
    if DEVICE_FILE.exists():
        return DeviceIdentity.load(DEVICE_FILE)

    device = DeviceIdentity.generate()
    device.save(DEVICE_FILE)
    return device


def normalize_kz_phone(phone: str) -> str:
    digits = "".join(ch for ch in phone if ch.isdigit())
    if len(digits) == 11 and digits.startswith(("7", "8")):
        return digits[1:]
    return digits


def mask_secret(value: str, *, visible: int = 6) -> str:
    if len(value) <= visible * 2:
        return "***"
    return f"{value[:visible]}...{value[-visible:]}"


async def main() -> None:
    device = load_or_create_device()
    auth_phone = normalize_kz_phone(AUTH_PHONE)
    client_phone = normalize_kz_phone(CLIENT_PHONE)

    async with KaspiClient(device=device, debug=True) as client:
        init = await client.auth.init()
        print("init:", init)

        sent = await client.auth.send_phone(init["process_id"], auth_phone)
        print("send_phone:", sent)
        if not sent["success"]:
            print("SMS was not sent. Kaspi error:", sent["body"].get("error") or sent["body"])
            return

        otp = input("SMS code: ")
        session = await client.auth.verify_otp(init["process_id"], otp)

        print("token_sn:", mask_secret(session.token_sn))
        print("vtoken_secret_b64:", mask_secret(session.vtoken_secret_b64))
        print("profile_id:", session.profile_id)
        print("organization_id:", session.organization_id)

        check = await client.session.check(session)
        print("session.check:", check)

        client_info = await client.invoice.client_info(session, client_phone)
        print("invoice.client_info:", client_info)

        invoice = await client.invoice.create(
            session,
            phone_number=client_phone,
            amount=100,
            comment="pykaspi live test",
        )
        print("invoice.create:", invoice)


if __name__ == "__main__":
    asyncio.run(main())
