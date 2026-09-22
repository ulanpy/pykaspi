from __future__ import annotations

from .config import AppConfig, KASPI_QRPAY_URL
from .device import DeviceIdentity
from .headers import signed_qrpay_headers
from .models import KaspiSession
from .schemas import HistoryOperationsData, KaspiResponse, OperationDetailsData
from .transport import KaspiTransport
from .wire import json_body


class HistoryApi:
    """Operations history and operation details API."""

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
    ) -> KaspiResponse[HistoryOperationsData]:
        """Fetch operations history for a period ending at `end_date`.

        Args:
            session: Active Kaspi session.
            end_date: Date string accepted by Kaspi, usually `YYYY-MM-DD`.
            last_transaction_date: Cursor from a previous page, if any.
            statement_period_code: Kaspi period filter code.
        """
        url = f"{KASPI_QRPAY_URL}/v02/history/operations"
        payload = json_body({"EndDate": end_date, "LastTransactionDate": last_transaction_date, "StatementPeriodCode": statement_period_code})
        body = await self.transport.request(
            "POST",
            url,
            headers={**signed_qrpay_headers(url, session, self.device, self.app, body=payload), "Content-Type": "application/json"}, content=payload,
        )
        return KaspiResponse[HistoryOperationsData].model_validate(body)

    async def details(
        self,
        session: KaspiSession,
        operation_id: int | str,
        *,
        operation_method: int = 0,
    ) -> KaspiResponse[OperationDetailsData]:
        """Fetch details for a single operation from history."""
        url = f"{KASPI_QRPAY_URL}/v01/kaspi-qr/operations/details"
        payload = json_body({"Id": int(operation_id), "OperationMethod": operation_method})
        body = await self.transport.request(
            "POST",
            url,
            headers={**signed_qrpay_headers(url, session, self.device, self.app, body=payload), "Content-Type": "application/json"}, content=payload,
        )
        return KaspiResponse[OperationDetailsData].model_validate(body)
