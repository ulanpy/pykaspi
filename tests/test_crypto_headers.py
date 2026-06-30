from __future__ import annotations

from pykaspi import AppConfig, DeviceIdentity, KaspiSession
from pykaspi.crypto import EcdhKeyPair, compute_token_sn_mac, secret_from_base64, secret_to_base64
from pykaspi.headers import entrance_cookie, signed_qrpay_headers


def test_secret_base64_roundtrip() -> None:
    secret = b"secret-bytes"

    assert secret_from_base64(secret_to_base64(secret)) == secret


def test_ecdh_roundtrip() -> None:
    left = EcdhKeyPair.generate()
    right = EcdhKeyPair.generate()

    assert left.complete(right.x509) == right.complete(left.x509)


def test_compute_token_sn_mac_shape() -> None:
    mac = compute_token_sn_mac("TOKEN", b"0" * 32)

    assert mac.isdigit()
    assert len(mac) == 6


def test_signed_qrpay_headers_include_signature() -> None:
    device = DeviceIdentity.generate()
    session = KaspiSession(token_sn="TOKEN", vtoken_secret=b"0" * 32, profile_id=123)
    url = "https://qrpay.kaspi.kz/v02/kaspi-qr/status?qrOperationId=1"

    headers = signed_qrpay_headers(url, session, device, app=AppConfig())

    assert headers["X-Kb-TokenSn"] == "TOKEN"
    assert headers["X-PI"] == "123"
    assert headers["X-Sign"]
    assert "url" in headers["X-SH"]


def test_entrance_cookie_contains_device_values() -> None:
    device = DeviceIdentity.generate()
    cookie = entrance_cookie(device, AppConfig(), user_token="USER")

    assert f"deviceId={device.device_id}" in cookie
    assert f"installId={device.install_id}" in cookie
    assert "user_token=USER" in cookie
