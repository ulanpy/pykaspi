from __future__ import annotations

from .config import AppConfig, KASPI_QRPAY_URL
from .device import DeviceIdentity
from .headers import signed_qrpay_headers
from .models import KaspiSession
from .schemas import KaspiResponse, RefundCreateData
from .transport import KaspiTransport
from .wire import json_body


class RefundApi:
    """Refund API for already processed Kaspi QR operations."""

    def __init__(self, transport: KaspiTransport, device: DeviceIdentity, app: AppConfig) -> None:
        self.transport = transport
        self.device = device
        self.app = app

    async def create(
        self,
        session: KaspiSession,
        qr_operation_id: int | str,
        return_amount: int | float,
    ) -> KaspiResponse[RefundCreateData]:
        """Create a refund for a processed QR operation.

        Args:
            session: Active Kaspi session.
            qr_operation_id: Kaspi QR operation id to refund.
            return_amount: Amount to return in KZT.
        """
        url = f"{KASPI_QRPAY_URL}/v01/kaspi-qr/history-pos-return"
        payload = json_body({"ReturnAmount": float(return_amount), "QrOperationId": int(qr_operation_id), "DeviceInterface": "Pos"})
        body = await self.transport.request(
            "POST",
            url,
            headers={**signed_qrpay_headers(url, session, self.device, self.app, body=payload), "Content-Type": "application/json"}, content=payload,
        )
        return KaspiResponse[RefundCreateData].model_validate(body)
