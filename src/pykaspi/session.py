from __future__ import annotations

from datetime import date
from .config import AppConfig, KASPI_QRPAY_URL
from .device import DeviceIdentity
from .headers import signed_qrpay_headers
from .models import KaspiSession
from .schemas import HistoryOperationsData, KaspiResponse, SessionCheckResult
from .transport import KaspiTransport
from .wire import json_body


class SessionApi:
    """Session health-check API."""

    def __init__(self, transport: KaspiTransport, device: DeviceIdentity, app: AppConfig) -> None:
        self.transport = transport
        self.device = device
        self.app = app

    async def check(self, session: KaspiSession) -> SessionCheckResult:
        """Check whether Kaspi still accepts the saved session.

        This method does not refresh the session. If `active` is false or the
        request fails, try `client.auth.refresh(session)` and fall back to SMS
        login if refresh raises `KaspiReauthRequiredError`.
        """
        url = f"{KASPI_QRPAY_URL}/v02/history/operations"
        payload = json_body({"EndDate": date.today().isoformat(), "LastTransactionDate": "", "StatementPeriodCode": 0})
        body = await self.transport.request(
            "POST",
            url,
            headers={**signed_qrpay_headers(url, session, self.device, self.app, body=payload), "Content-Type": "application/json"}, content=payload,
        )
        response = KaspiResponse[HistoryOperationsData].model_validate(body)
        return SessionCheckResult(active=response.ok, body=response)
