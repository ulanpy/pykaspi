from __future__ import annotations

import pytest

from pykaspi import (
    AppConfig,
    AuthInitResult,
    DeviceIdentity,
    KaspiReauthRequiredError,
    KaspiResponse,
    KaspiSession,
    QrCreateData,
    SendPhoneResult,
)
from pykaspi.crypto import EcdhKeyPair, compute_token_sn_mac, secret_from_base64, secret_to_base64
from pykaspi.headers import entrance_cookie, signed_qrpay_headers
from pykaspi.payments import PaymentPollResult, poll_until_final


def test_secret_base64_roundtrip() -> None:
    secret = b"secret-bytes"

    assert secret_from_base64(secret_to_base64(secret)) == secret


def test_session_dict_roundtrip() -> None:
    session = KaspiSession(
        token_sn="TOKEN",
        vtoken_secret=b"secret-bytes",
        ecdh_private_key_b64="ECDH",
        profile_id=123,
        organization_id=456,
        org_name="Test Org",
    )

    restored = KaspiSession.from_dict(session.to_dict())

    assert restored.token_sn == session.token_sn
    assert restored.vtoken_secret == session.vtoken_secret
    assert restored.ecdh_private_key_b64 == session.ecdh_private_key_b64
    assert restored.profile_id == session.profile_id
    assert restored.organization_id == session.organization_id
    assert restored.org_name == session.org_name


def test_reauth_error_is_exported() -> None:
    assert issubclass(KaspiReauthRequiredError, Exception)


def test_pydantic_models_allow_new_kaspi_fields() -> None:
    response = KaspiResponse[QrCreateData].model_validate(
        {
            "StatusCode": 0,
            "Message": "OK",
            "Data": {
                "QrOperationId": 123,
                "QrToken": "token",
                "NewKaspiField": "value",
            },
            "TopLevelNewField": 42,
        }
    )

    assert response.ok
    assert response.data is not None
    assert response.data.qr_operation_id == 123
    assert response.data.NewKaspiField == "value"
    assert response.TopLevelNewField == 42


def test_auth_result_models() -> None:
    init = AuthInitResult(process_id="PID", view="EnterPhoneNumber", body={"raw": True})
    sent = SendPhoneResult(
        status="otp_required",
        success=True,
        process_id=init.process_id,
        description="sent",
        body={"raw": True},
    )

    assert init.process_id == "PID"
    assert sent.success is True
    assert sent.requires_otp is True
    assert sent.process_id == "PID"


def test_send_phone_mobile_confirmation_model() -> None:
    sent = SendPhoneResult(
        status="mobile_confirmation_required",
        success=False,
        process_id="PID",
        view="KPMobileCall",
        challenge_type="kpOrgRegistration",
        operation_type="OrgRegistration",
        auth_methods=[{"type": "pincode", "request": "required"}],
        body={"raw": True},
    )

    assert sent.requires_mobile_confirmation is True
    assert sent.requires_otp is False
    assert sent.auth_methods == [{"type": "pincode", "request": "required"}]


@pytest.mark.asyncio
async def test_poll_until_final_accepts_pydantic_response() -> None:
    session = KaspiSession(token_sn="TOKEN", vtoken_secret=b"0" * 32)

    async def fetch_status(_session: KaspiSession, _payment_id: int | str) -> KaspiResponse[QrCreateData]:
        return KaspiResponse[QrCreateData].model_validate(
            {"StatusCode": 0, "Data": {"Status": "Processed", "QrOperationId": 123}}
        )

    result = await poll_until_final(fetch_status, session, 123, interval=0, timeout=1)

    assert isinstance(result, PaymentPollResult)
    assert result.event == "payment.success"
    assert result.status == "Processed"


def test_ecdh_roundtrip() -> None:
    left = EcdhKeyPair.generate()
    right = EcdhKeyPair.generate()

    assert left.complete(right.x509) == right.complete(left.x509)


def test_ecdh_private_key_roundtrip() -> None:
    left = EcdhKeyPair.generate()
    restored = EcdhKeyPair.from_private_key_b64(left.private_key_b64)
    right = EcdhKeyPair.generate()

    assert restored.complete(right.x509) == right.complete(left.x509)


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
