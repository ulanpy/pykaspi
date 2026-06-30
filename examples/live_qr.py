from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

from pykaspi import DeviceIdentity, KaspiClient, KaspiReauthRequiredError, KaspiSession


AUTH_PHONE = os.environ.get("PYKASPI_AUTH_PHONE", "+77001234567")
AMOUNT = 100
DEVICE_FILE = Path("device.json")
SESSION_FILE = Path("session.json")


def normalize_kz_phone(phone: str) -> str:
    digits = "".join(ch for ch in phone if ch.isdigit())
    if len(digits) == 11 and digits.startswith(("7", "8")):
        return digits[1:]
    return digits


def load_or_create_device() -> DeviceIdentity:
    if DEVICE_FILE.exists():
        return DeviceIdentity.load(DEVICE_FILE)

    device = DeviceIdentity.generate()
    device.save(DEVICE_FILE)
    return device


def save_session(session: KaspiSession) -> None:
    SESSION_FILE.write_text(
        json.dumps(
            {
                "token_sn": session.token_sn,
                "vtoken_secret_b64": session.vtoken_secret_b64,
                "ecdh_private_key_b64": session.ecdh_private_key_b64,
                "profile_id": session.profile_id,
                "organization_id": session.organization_id,
                "phone_number": session.phone_number,
                "org_name": session.org_name,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def load_session() -> KaspiSession | None:
    if not SESSION_FILE.exists():
        return None

    data: dict[str, Any] = json.loads(SESSION_FILE.read_text())
    return KaspiSession.from_base64(
        token_sn=data["token_sn"],
        vtoken_secret_b64=data["vtoken_secret_b64"],
        ecdh_private_key_b64=data.get("ecdh_private_key_b64"),
        profile_id=data.get("profile_id"),
        organization_id=data.get("organization_id"),
        phone_number=data.get("phone_number"),
        org_name=data.get("org_name"),
    )


async def login_by_sms(client: KaspiClient) -> KaspiSession:
    auth_phone = normalize_kz_phone(AUTH_PHONE)
    init = await client.auth.init()
    print("init:", init)

    sent = await client.auth.send_phone(init["process_id"], auth_phone)
    print("send_phone:", sent)
    if not sent["success"]:
        raise RuntimeError(f"SMS was not sent: {sent['body'].get('error') or sent['body']}")

    otp = input("SMS code: ")
    session = await client.auth.verify_otp(init["process_id"], otp)
    save_session(session)
    return session


async def get_valid_session(client: KaspiClient) -> KaspiSession:
    session = load_session()
    if session is None:
        print("No session.json found, logging in by SMS.")
        return await login_by_sms(client)

    try:
        check = await client.session.check(session)
        print("session.check:", check)
        if check.active:
            return session
    except Exception as exc:
        print("session.check failed, trying refresh:", exc)

    try:
        print("Trying SignInLite refresh.")
        refreshed = await client.auth.refresh(session)
        save_session(refreshed)
        return refreshed
    except KaspiReauthRequiredError as exc:
        print("Refresh requires SMS re-auth:", exc)

    print("Saved session is inactive, logging in by SMS.")
    return await login_by_sms(client)


async def main() -> None:
    device = load_or_create_device()

    async with KaspiClient(device=device, debug=True) as client:
        session = await get_valid_session(client)

        qr = await client.qr.create(session, amount=AMOUNT)
        print("qr.create:", qr)

        if qr.data and qr.data.qr_operation_id:
            status = await client.qr.status(session, qr.data.qr_operation_id)
            print("qr.status:", status)


if __name__ == "__main__":
    asyncio.run(main())
