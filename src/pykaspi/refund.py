from __future__ import annotations

from typing import Any

from .config import AppConfig, KASPI_QRPAY_URL
from .device import DeviceIdentity
from .headers import signed_qrpay_headers
from .models import KaspiSession
from .transport import KaspiTransport


class RefundApi:
    def __init__(self, transport: KaspiTransport, device: DeviceIdentity, app: AppConfig) -> None:
        self.transport = transport
        self.device = device
        self.app = app

    async def create(
        self,
        session: KaspiSession,
        qr_operation_id: int | str,
        return_amount: int | float,
    ) -> dict[str, Any]:
        url = f"{KASPI_QRPAY_URL}/v01/kaspi-qr/history-pos-return"
        return await self.transport.request(
            "POST",
            url,
            headers={**signed_qrpay_headers(url, session, self.device, self.app), "Content-Type": "application/json"},
            json={
                "ReturnAmount": float(return_amount),
                "QrOperationId": int(qr_operation_id),
                "DeviceInterface": "Pos",
            },
        )
