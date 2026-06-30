from __future__ import annotations

from datetime import date
from typing import Any

from .config import AppConfig, KASPI_QRPAY_URL
from .device import DeviceIdentity
from .headers import signed_qrpay_headers
from .models import KaspiSession
from .transport import KaspiTransport


class SessionApi:
    def __init__(self, transport: KaspiTransport, device: DeviceIdentity, app: AppConfig) -> None:
        self.transport = transport
        self.device = device
        self.app = app

    async def check(self, session: KaspiSession) -> dict[str, Any]:
        url = f"{KASPI_QRPAY_URL}/v02/history/operations"
        body = await self.transport.request(
            "POST",
            url,
            headers={**signed_qrpay_headers(url, session, self.device, self.app), "Content-Type": "application/json"},
            json={
                "EndDate": date.today().isoformat(),
                "LastTransactionDate": "",
                "StatementPeriodCode": 0,
            },
        )
        active = body.get("StatusCode") in (None, 0)
        return {"active": active, "body": body}
