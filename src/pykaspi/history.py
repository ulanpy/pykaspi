from __future__ import annotations

from typing import Any

from .config import AppConfig, KASPI_QRPAY_URL
from .device import DeviceIdentity
from .headers import signed_qrpay_headers
from .models import KaspiSession
from .transport import KaspiTransport


class HistoryApi:
    def __init__(self, transport: KaspiTransport, device: DeviceIdentity, app: AppConfig) -> None:
        self.transport = transport
        self.device = device
        self.app = app

    async def operations(
        self,
        session: KaspiSession,
        end_date: str,
        *,
        last_transaction_date: str = "",
        statement_period_code: int = 0,
    ) -> dict[str, Any]:
        url = f"{KASPI_QRPAY_URL}/v02/history/operations"
        return await self.transport.request(
            "POST",
            url,
            headers={**signed_qrpay_headers(url, session, self.device, self.app), "Content-Type": "application/json"},
            json={
                "EndDate": end_date,
                "LastTransactionDate": last_transaction_date,
                "StatementPeriodCode": statement_period_code,
            },
        )

    async def details(
        self,
        session: KaspiSession,
        operation_id: int | str,
        *,
        operation_method: int = 0,
    ) -> dict[str, Any]:
        url = f"{KASPI_QRPAY_URL}/v01/kaspi-qr/operations/details"
        return await self.transport.request(
            "POST",
            url,
            headers={**signed_qrpay_headers(url, session, self.device, self.app), "Content-Type": "application/json"},
            json={"Id": int(operation_id), "OperationMethod": operation_method},
        )
