import asyncio
import json

import httpx
import pytest

from pykaspi import DeviceIdentity, KaspiApiError, KaspiClient, KaspiReauthRequiredError, KaspiSession, poll_until_final
from pykaspi import KaspiTerminal
from pykaspi.validation import normalize_phone, validate_amount


@pytest.fixture
def session():
    return KaspiSession(token_sn="TEST", vtoken_secret=b"0" * 32, profile_id=123)


@pytest.mark.asyncio
async def test_create_then_observe_paid_invoice(session):
    statuses = iter(["RemotePaymentCreated", "Processing", "Processed"])
    requests = []

    def handle(request):
        requests.append(request)
        assert request.headers["X-Kb-TokenSn"] == "TEST"
        assert request.headers["X-PI"] == "123"
        assert request.headers["X-Sign"]
        if request.url.path == "/v01/remote/create":
            assert json.loads(request.content) == {
                "PhoneNumber": "7001234567", "Amount": 100.0, "Comment": "test",
            }
            return httpx.Response(200, json={"StatusCode": 0, "Data": {
                "Id": 987, "Status": "RemotePaymentCreated", "Amount": 100,
            }})
        assert request.method == "GET"
        assert request.url.path == "/v02/remote/details"
        assert request.url.params["operationId"] == "987"
        return httpx.Response(200, json={"StatusCode": 0, "Data": {
            "Id": 987, "Status": next(statuses), "Amount": 100,
        }})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        async with KaspiClient(device=DeviceIdentity.generate(), http_client=http) as client:
            invoice = await client.invoice.create(session, "+7 (700) 123-45-67", 100, comment="test")
            result = await client.invoice.wait_for_payment(session, invoice.data.id, interval=0)
    assert result.event == "payment.success"
    assert result.status == "Processed"
    assert result.body.data.id == 987
    assert len(requests) == 4


def test_remote_details_accepts_kaspi_formatted_amount():
    from pykaspi.schemas import InvoiceDetailsData, KaspiResponse

    response = KaspiResponse[InvoiceDetailsData].model_validate({
        "StatusCode": 0,
        "Data": {"Id": 987, "Status": "RemotePaymentCreated", "Amount": "100 ₸"},
    })
    assert response.data is not None
    assert response.data.amount == "100 ₸"


def test_terminal_round_trip_uses_one_json_file(tmp_path):
    original = KaspiTerminal(
        device=DeviceIdentity.generate(),
        session=KaspiSession(token_sn="TOKEN", vtoken_secret=b"0" * 32, profile_id=123),
    )
    path = tmp_path / "terminal.json"
    original.save(path)

    restored = KaspiTerminal.load(path)

    assert restored.device.device_id == original.device.device_id
    assert restored.session.token_sn == "TOKEN"
    assert restored.session.profile_id == 123
    assert path.stat().st_mode & 0o777 == 0o600


@pytest.mark.asyncio
@pytest.mark.parametrize("status,event", [
    ("RemotePaymentCanceled", "payment.failed"),
    ("RemotePaymentRejected", "payment.failed"),
    ("Expired", "payment.expired"),
])
async def test_bank_reported_final_status(session, status, event):
    async def fetch(*args):
        return {"StatusCode": 0, "Data": {"Status": status}}
    assert (await poll_until_final(fetch, session, 1, payment_type="invoice")).event == event


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["RemotePaymentCreated", "NewBankStatus"])
async def test_local_timeout_is_not_expiry_or_failure(session, status):
    async def fetch(*args):
        return {"StatusCode": 0, "Data": {"Status": status}}
    result = await poll_until_final(fetch, session, 1, payment_type="invoice", interval=1, timeout=0.01)
    assert result.event == "payment.timeout"
    assert result.status == status


@pytest.mark.asyncio
async def test_timeout_bounds_hanging_status_request(session):
    async def fetch(*args):
        await asyncio.sleep(10)
    result = await asyncio.wait_for(poll_until_final(fetch, session, 1, timeout=0.01), timeout=1)
    assert result.event == "payment.timeout"
    assert result.body is None


@pytest.mark.asyncio
@pytest.mark.parametrize("body", [
    {"StatusCode": 401, "Message": "Expired session", "Data": {"Status": "Processed"}},
    {"StatusCode": 0, "Data": {}},
    {"StatusCode": 0, "Data": ["Processed"]},
    {},
])
async def test_lookup_error_never_becomes_payment_result(session, body):
    async def fetch(*args):
        return body
    with pytest.raises(KaspiApiError):
        await poll_until_final(fetch, session, 1)


@pytest.mark.asyncio
async def test_network_error_propagates_without_recreating_invoice(session):
    calls = 0
    def handle(request):
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("lost response", request=request)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        async with KaspiClient(http_client=http) as client:
            with pytest.raises(KaspiApiError):
                await client.invoice.create(session, "7001234567", 100)
    assert calls == 1


@pytest.mark.asyncio
async def test_auth_http_error_is_reported():
    async with httpx.AsyncClient(transport=httpx.MockTransport(
        lambda request: httpx.Response(503, json={"Message": "Unavailable"}),
    )) as http:
        async with KaspiClient(http_client=http) as client:
            with pytest.raises(KaspiApiError) as error:
                await client.auth.init()
    assert error.value.status_code == 503


@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf"), 1.001, True, 1e100])
def test_invalid_amount(value):
    with pytest.raises(ValueError):
        validate_amount(value)


@pytest.mark.parametrize("phone", ["7001234567", "+77001234567", "87001234567"])
def test_normalize_phone(phone):
    assert normalize_phone(phone) == "7001234567"


@pytest.mark.parametrize("phone", ["", "123", "7001234567&other=1", "700123456789"])
def test_invalid_phone(phone):
    with pytest.raises(ValueError):
        normalize_phone(phone)


@pytest.mark.asyncio
async def test_old_app_version_is_not_successful_auth_init():
    body = {
        "meta": {"pId": "closed-process"}, "isClosed": True,
        "view": {"code": "KPUniversalEnterPhoneNumber", "onOpenAlarm": {
            "error": {"code": "OldVersionToUpdate", "label": "Update app"},
        }},
    }
    async with httpx.AsyncClient(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json=body),
    )) as http:
        async with KaspiClient(http_client=http) as client:
            with pytest.raises(KaspiApiError, match="OldVersionToUpdate"):
                await client.auth.init()
            assert not client.auth._entrance_sessions


@pytest.mark.asyncio
async def test_password_challenge_uses_server_step_and_continues_to_otp(caplog):
    import logging
    from pykaspi.models import EntranceSession

    seen = []
    def handle(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={
            "meta": {"pId": "pid", "sn": "ViewEnterOtp"},
            "view": {"code": "EnterOtp"}, "data": {"desc": "SMS sent"},
        })

    challenge = {
        "meta": {"pId": "pid", "sn": "ServerPasswordStep"},
        "view": {"code": "KPEnterLoginPassword"},
    }
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        async with KaspiClient(http_client=http, debug=True) as client:
            client.auth._entrance_sessions["pid"] = EntranceSession(process_id="pid", raw=challenge)
            assert client.auth._challenge_result("pid", challenge).requires_password
            with caplog.at_level(logging.DEBUG, logger="pykaspi"):
                result = await client.auth.submit_password("pid", "test-password-not-real")
            assert result.requires_otp
            assert client.auth._entrance_sessions["pid"].raw["view"]["code"] == "EnterOtp"
    assert seen == [{
        "meta": {"pId": "pid", "sn": "ServerPasswordStep"},
        "data": {"password": "test-password-not-real"}, "actType": "Success",
    }]
    assert "test-password-not-real" not in caplog.text


@pytest.mark.asyncio
async def test_wrong_password_is_not_retried():
    from pykaspi.models import EntranceSession

    calls = []
    def handle(request):
        calls.append(request.url.path)
        return httpx.Response(200, json={
            "actType": "Alarm", "error": {"code": "WrongPassword", "label": "Wrong password"},
        })
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        async with KaspiClient(http_client=http) as client:
            client.auth._entrance_sessions["pid"] = EntranceSession(process_id="pid", raw={
                "meta": {"pId": "pid", "sn": "ServerPasswordStep"},
                "view": {"code": "KPEnterLoginPassword"},
            })
            with pytest.raises(KaspiApiError, match="WrongPassword"):
                await client.auth.submit_password("pid", "wrong")
    assert len(calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("reply,match", [
    ({"actType": "Alarm", "error": {"code": "InvalidOtp", "label": "Wrong code"}}, "InvalidOtp"),
    ({"type": "View", "view": {"code": "ExtraVerification"},
      "meta": {"sn": "ExtraStep"}, "data": {"type": "additionalCheck"}}, "view=ExtraVerification"),
])
async def test_otp_preserves_server_step_and_reports_actual_response(reply, match):
    from pykaspi.models import EntranceSession
    requests = []
    def handle(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json=reply)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        async with KaspiClient(http_client=http) as client:
            client.auth._entrance_sessions["pid"] = EntranceSession(process_id="pid", raw={
                "meta": {"pId": "pid", "sn": "OtpAfterPassword", "revision": 2},
                "view": {"code": "EnterOtp"},
            })
            with pytest.raises(KaspiApiError, match=match) as error:
                await client.auth.verify_otp("pid", " 123456 ")
            assert error.value.body == reply
    assert requests == [{
        "meta": {"pId": "pid", "sn": "OtpAfterPassword", "revision": 2},
        "data": {"userOtp": "123456", "inputType": "Manual"}, "actType": "Success",
    }]


@pytest.mark.asyncio
async def test_otp_registration_still_finishes(monkeypatch, session):
    from pykaspi.models import EntranceSession
    from unittest.mock import AsyncMock
    async with httpx.AsyncClient(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json={
            "view": {"code": "KPMobileCall"}, "data": {"type": "kpDeviceRegistration"},
        }),
    )) as http:
        async with KaspiClient(http_client=http) as client:
            entrance = EntranceSession(process_id="pid", raw={"meta": {"sn": "ViewEnterOtp"}})
            client.auth._entrance_sessions["pid"] = entrance
            finish = AsyncMock(return_value=session)
            monkeypatch.setattr(client.auth, "_finish", finish)
            assert await client.auth.verify_otp("pid", "123456") is session
            finish.assert_awaited_once_with(entrance)
            assert "pid" not in client.auth._entrance_sessions


@pytest.mark.asyncio
async def test_org_context_rejection_is_not_saved_as_empty_cashier_session():
    def handle(request):
        return httpx.Response(200, json={
            "StatusCode": -101001,
            "Message": "A different device was used to sign in",
        })
    session = KaspiSession(token_sn="TOKEN", vtoken_secret=b"0" * 32)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        async with KaspiClient(http_client=http) as client:
            with pytest.raises(KaspiReauthRequiredError, match="different device") as error:
                await client.auth.load_org_context(session)
    assert error.value.body["StatusCode"] == -101001
    assert session.profile_id is None
    assert "org_context" not in session.raw


@pytest.mark.asyncio
async def test_org_context_requires_cashier_profile_and_organization():
    def handle(request):
        return httpx.Response(200, json={"StatusCode": 0, "Data": {"Current": {}}})
    session = KaspiSession(token_sn="TOKEN", vtoken_secret=b"0" * 32)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        async with KaspiClient(http_client=http) as client:
            with pytest.raises(KaspiApiError, match="without cashier profile"):
                await client.auth.load_org_context(session)
