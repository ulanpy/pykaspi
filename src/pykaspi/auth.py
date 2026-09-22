from __future__ import annotations

import base64
import json
from typing import Any

from .config import AppConfig, KASPI_ENTRANCE_URL, KASPI_MTOKEN_URL
from .crypto import EcdhKeyPair, sign_data_payload
from .device import DeviceIdentity
from .exceptions import KaspiAuthError, KaspiReauthRequiredError
from .headers import (
    build_device_information,
    build_mtoken_headers,
    entrance_cookie,
    entrance_headers_base,
    extract_user_token,
    finish_headers,
    now_iso,
)
from .models import EntranceSession, KaspiSession, apply_org_context
from .schemas import AuthInitResult, SendPhoneResult
from .transport import KaspiTransport
from .validation import normalize_phone


class AuthApi:
    """SMS authentication, session refresh, and organization context API."""

    def __init__(self, transport: KaspiTransport, device: DeviceIdentity, app: AppConfig) -> None:
        self.transport = transport
        self.device = device
        self.app = app
        self._entrance_sessions: dict[str, EntranceSession] = {}
        self._registration_ecdh: EcdhKeyPair | None = None

    async def init(self) -> AuthInitResult:
        """Start Kaspi SMS login and return a `process_id`.

        Call `send_phone(process_id, phone_number)` next. The `phone_number`
        should be a local Kazakhstan mobile number without `+7`/`8`, for
        example `"7001234567"`.
        """
        session = EntranceSession()
        url = f"{KASPI_ENTRANCE_URL}/api/v1/entrance/step"
        headers = {
            **entrance_headers_base(self.app),
            "Referer": (
                f"{KASPI_ENTRANCE_URL}/process/entrance/?auth=2&appBuild={self.app.build}"
                f"&appVersion={self.app.version}&platformVersion={self.app.platform_ver}"
                f"&platformType=IOS&deviceBrand={self.app.brand}&deviceModel={self.app.model}"
                f"&deviceId={self.device.device_id}&installId={self.device.install_id}"
                "&frontCameraAvailable=true&sf=registration&pc=KPEntrance&noPass=0"
            ),
            "Cookie": entrance_cookie(self.device, self.app),
        }
        response, body = await self.transport.request_with_response(
            "POST",
            url,
            headers=headers,
            json={
                "data": {},
                "Data": {
                    "auth": "2",
                    "appBuild": self.app.build,
                    "appVersion": self.app.version,
                    "platformVersion": self.app.platform_ver,
                    "platformType": "IOS",
                    "deviceBrand": self.app.brand,
                    "deviceModel": self.app.model,
                    "deviceId": self.device.device_id,
                    "installId": self.device.install_id,
                    "frontCameraAvailable": "true",
                    "sf": "registration",
                    "pc": "KPEntrance",
                    "noPass": "0",
                },
                "actType": "Success",
            },
        )
        self._check_entrance_error(body)
        session.user_token = extract_user_token(response.headers.get_list("set-cookie"))
        session.process_id = (body.get("meta") or {}).get("pId")
        session.raw = body
        if not session.process_id:
            raise KaspiAuthError("Kaspi did not return processId", body=body)
        self._entrance_sessions[session.process_id] = session
        return AuthInitResult(
            process_id=session.process_id,
            view=(body.get("view") or {}).get("code"),
            body=body,
        )

    async def send_phone(self, process_id: str, phone_number: str) -> SendPhoneResult:
        """Send the cashier phone number and trigger Kaspi SMS OTP.

        Args:
            process_id: Value returned by `init()`.
            phone_number: Local KZ mobile digits without country prefix.

        Returns:
            `SendPhoneResult` with `success`, `description`, and raw body.
        """
        session = self._get_entrance_session(process_id)
        phone_number = normalize_phone(phone_number)
        session.phone_number = phone_number
        url = f"{KASPI_ENTRANCE_URL}/api/v1/entrance/step"
        response, body = await self.transport.request_with_response(
            "POST",
            url,
            headers={
                **entrance_headers_base(self.app),
                "Referer": (
                    f"{KASPI_ENTRANCE_URL}/process/universal-enter-phone-number"
                    f"?pId={process_id}&firstPage=KPUniversalEnterPhoneNumber"
                ),
                "Cookie": entrance_cookie(self.device, self.app, session.user_token),
            },
            json={
                "meta": {"pId": process_id, "sn": "EnterPhoneNumber"},
                "data": {"phoneNumber": phone_number},
                "actType": "Success",
            },
        )
        self._check_entrance_error(body)
        session.user_token = extract_user_token(response.headers.get_list("set-cookie")) or session.user_token
        session.raw = body
        return self._challenge_result(process_id, body)

    @staticmethod
    def _challenge_result(process_id: str, body: dict[str, Any]) -> SendPhoneResult:
        view = (body.get("view") or {}).get("code")
        data = body.get("data") or {}
        operation_type = (data.get("ext") or {}).get("operationType")
        if view == "EnterOtp":
            status = "otp_required"
        elif view == "KPEnterLoginPassword":
            status = "password_required"
        elif view == "KPMobileCall":
            status = "mobile_confirmation_required"
        else:
            status = "unsupported_challenge"
        return SendPhoneResult(
            status=status,
            success=status == "otp_required",
            process_id=process_id,
            description=data.get("desc"),
            view=view,
            challenge_type=data.get("type"),
            operation_type=operation_type,
            auth_methods=data.get("authMethods"),
            body=body,
        )

    async def submit_password(self, process_id: str, password: str) -> SendPhoneResult:
        """Submit the account password and return the next authentication challenge.

        Mirrors the Kaspi entrance web client's password step. Read passwords
        locally; do not persist them. This method does not retry rejected input.
        """
        session = self._get_entrance_session(process_id)
        if (session.raw.get("view") or {}).get("code") != "KPEnterLoginPassword":
            raise KaspiAuthError("The current login process is not requesting a password")
        if not password or not password.strip():
            raise ValueError("Password must not be empty")
        meta = session.raw.get("meta")
        if not isinstance(meta, dict) or not meta.get("sn"):
            raise KaspiAuthError("Password challenge is missing step metadata", body=session.raw)
        response, body = await self.transport.request_with_response(
            "POST", f"{KASPI_ENTRANCE_URL}/api/v1/entrance/step",
            headers={
                **entrance_headers_base(self.app),
                "Referer": f"{KASPI_ENTRANCE_URL}/process/enter-login-password?pId={process_id}",
                "Cookie": entrance_cookie(self.device, self.app, session.user_token),
            },
            json={"meta": {**meta, "pId": process_id}, "data": {"password": password}, "actType": "Success"},
        )
        session.user_token = extract_user_token(response.headers.get_list("set-cookie")) or session.user_token
        self._check_entrance_error(body)
        session.raw = body
        return self._challenge_result(process_id, body)

    async def verify_otp(self, process_id: str, otp: str) -> KaspiSession:
        """Verify SMS OTP and return an authenticated `KaspiSession`.

        Persist the returned session securely. It contains `token_sn`,
        `vtoken_secret`, organization context, and `ecdh_private_key_b64` for
        future SignInLite refresh attempts.
        """
        entrance_session = self._get_entrance_session(process_id)
        otp = otp.strip()
        if not otp or not otp.isascii() or not otp.isdigit():
            raise ValueError("SMS code must contain digits only")
        meta = entrance_session.raw.get("meta") or {}
        url = f"{KASPI_ENTRANCE_URL}/api/v1/entrance/step"
        response, body = await self.transport.request_with_response(
            "POST",
            url,
            headers={
                **entrance_headers_base(self.app),
                "Referer": (
                    f"{KASPI_ENTRANCE_URL}/process/universal-enter-phone-number"
                    f"?pId={process_id}&firstPage=KPUniversalEnterPhoneNumber"
                ),
                "Cookie": entrance_cookie(self.device, self.app, entrance_session.user_token),
            },
            json={
                "meta": {**meta, "pId": process_id, "sn": meta.get("sn") or "ViewEnterOtp"},
                "data": {"userOtp": otp, "inputType": "Manual"},
                "actType": "Success",
            },
        )
        entrance_session.user_token = extract_user_token(response.headers.get_list("set-cookie")) or entrance_session.user_token
        entrance_session.raw = body

        if (body.get("data") or {}).get("type") != "kpDeviceRegistration" and (body.get("view") or {}).get("code") != "KPMobileCall":
            self._check_entrance_error(body)
            view = (body.get("view") or {}).get("code")
            step = (body.get("meta") or {}).get("sn")
            kind = (body.get("data") or {}).get("type")
            raise KaspiAuthError(
                f"Unexpected step after SMS: view={view}, step={step}, type={kind}. "
                "This does not by itself mean the SMS code was incorrect.", body=body,
            )

        try:
            return await self._finish(entrance_session)
        finally:
            self._entrance_sessions.pop(process_id, None)

    async def confirm_mobile(self, process_id: str) -> KaspiSession:
        """Finish login after Kaspi requests mobile/app confirmation.

        Use this when `send_phone()` returns
        `status == "mobile_confirmation_required"`. The user should first
        approve the pending action in the Kaspi/Kaspi Pay app, then call this
        method with the same `process_id`.
        """
        entrance_session = self._get_entrance_session(process_id)
        try:
            return await self._finish(entrance_session)
        finally:
            self._entrance_sessions.pop(process_id, None)

    async def refresh(self, session: KaspiSession, *, organization_id: int | str | None = None) -> KaspiSession:
        """Refresh an existing session through Kaspi SignInLite.

        Args:
            session: Previously saved Kaspi session.
            organization_id: Optional organization override.

        Raises:
            KaspiReauthRequiredError: Kaspi rejected refresh or the stored
                session lacks the ECDH key required to activate a new vtoken.

        Returns:
            A refreshed `KaspiSession`. Save it over the old session.
        """
        url = f"{KASPI_MTOKEN_URL}/v03/auth/sign-in-lite"
        body = await self.transport.request(
            "POST",
            url,
            headers=build_mtoken_headers(url, session.token_sn, session.vtoken_secret, self.device, self.app),
            json={
                "OrganizationId": organization_id or session.organization_id or 0,
                "DeviceInformation": build_device_information(self.device, self.app),
            },
        )

        if body.get("StatusCode") != 0 or not body.get("Data"):
            raise KaspiReauthRequiredError(
                body.get("Message") or body.get("Description") or "SignInLite failed",
                body=body,
            )

        data = body["Data"]
        token_sn = data.get("TokenSn") or data.get("tokenSN") or session.token_sn
        secret = session.vtoken_secret
        server_x509 = data.get("X509") or data.get("x509")
        if server_x509:
            if session.ecdh_private_key_b64:
                secret = EcdhKeyPair.from_private_key_b64(session.ecdh_private_key_b64).complete(server_x509)
            elif self._registration_ecdh:
                secret = self._registration_ecdh.complete(server_x509)
            else:
                raise KaspiReauthRequiredError(
                    "SignInLite returned X509, but the original ECDH private key is not available. "
                    "Re-authenticate by SMS and persist ecdh_private_key_b64.",
                    body=body,
                )

        refreshed = KaspiSession(
            token_sn=token_sn,
            vtoken_secret=secret,
            ecdh_private_key_b64=session.ecdh_private_key_b64,
            phone_number=session.phone_number,
            organization_id=organization_id or session.organization_id,
            raw=body,
        )
        if data.get("OrganizationContext") or data.get("OrganizationContextLite"):
            apply_org_context(refreshed, data.get("OrganizationContext") or data.get("OrganizationContextLite"))
        await self.load_org_context(refreshed, organization_id=organization_id or refreshed.organization_id)
        return refreshed

    async def load_org_context(
        self,
        session: KaspiSession,
        *,
        organization_id: int | str | None = None,
    ) -> KaspiSession:
        """Load organization context and merge it into the session."""
        url = f"{KASPI_MTOKEN_URL}/v08/organizations/org-context-otp"
        body = await self.transport.request(
            "POST",
            url,
            headers=build_mtoken_headers(
                url,
                session.token_sn,
                session.vtoken_secret,
                self.device,
                self.app,
                profile_id=session.profile_id,
                include_profile_in_signature=session.profile_id is not None,
            ),
            json={
                "DeviceInformation": build_device_information(self.device, self.app),
                "OrganizationId": organization_id or session.organization_id or 0,
            },
        )
        if body.get("StatusCode") != 0 or not body.get("Data"):
            raise KaspiReauthRequiredError(
                body.get("Message") or body.get("Description") or "Kaspi did not activate organization context",
                body=body,
            )
        apply_org_context(session, body["Data"])
        if session.profile_id is None or session.organization_id is None:
            raise KaspiAuthError("Kaspi returned organization context without cashier profile or organization", body=body)
        session.raw = {**session.raw, "org_context": body}
        return session

    async def _finish(self, entrance_session: EntranceSession) -> KaspiSession:
        if not entrance_session.process_id:
            raise KaspiAuthError("Cannot finish auth without processId")

        ecdh = EcdhKeyPair.generate()
        self._registration_ecdh = ecdh
        signed_data = {
            "installId": self.device.install_id,
            "time": now_iso(),
            "auth": [{"value": "", "type": "pincode"}],
            "userIdHash": "",
        }
        signed_data_b64 = base64.b64encode(json.dumps(signed_data, separators=(",", ":")).encode()).decode()

        url = f"{KASPI_ENTRANCE_URL}/api/v1/kpentrance/finish"
        body = await self.transport.request(
            "POST",
            url,
            headers=finish_headers(url, self.device, self.app),
            json={
                "signed": {"sign": sign_data_payload(signed_data_b64, self.device), "data": signed_data_b64},
                "guard": {"pinHash": self.device.pin_hash, "x509": ecdh.x509},
                "processId": entrance_session.process_id,
            },
        )

        data = body.get("data") or body.get("Data") or {}
        token_sn = data.get("tokenSN") or data.get("TokenSn")
        if not token_sn:
            raise KaspiAuthError("Finish did not return tokenSN", body=body)

        server_x509 = data.get("x509") or data.get("X509")
        if not server_x509:
            raise KaspiAuthError("Finish did not return vtoken x509", body=body)

        session = KaspiSession(
            token_sn=token_sn,
            vtoken_secret=ecdh.complete(server_x509),
            ecdh_private_key_b64=ecdh.private_key_b64,
            phone_number=entrance_session.phone_number,
            raw={"finish": body},
        )
        await self.load_org_context(session)
        return session

    @staticmethod
    def _check_entrance_error(body: dict[str, Any]) -> None:
        error = (body.get("error") or (body.get("data") or {}).get("error")
                 or ((body.get("view") or {}).get("onOpenAlarm") or {}).get("error") or {})
        if error:
            message = error.get("label") or error.get("desc") or "Kaspi rejected login"
            code = error.get("code")
            raise KaspiAuthError(f"{code}: {message}" if code else message, body=body)
        if body.get("isClosed"):
            raise KaspiAuthError("Kaspi closed the login process", body=body)

    def _get_entrance_session(self, process_id: str) -> EntranceSession:
        try:
            return self._entrance_sessions[process_id]
        except KeyError as exc:
            raise KaspiAuthError("Unknown processId. Call auth.init first.") from exc
