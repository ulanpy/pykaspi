from __future__ import annotations

from typing import Any

from .config import AppConfig, KASPI_QRPAY_URL
from .device import DeviceIdentity
from .headers import signed_qrpay_headers
from .models import KaspiSession
from .transport import KaspiTransport


class QrApi:
    def __init__(self, transport: KaspiTransport, device: DeviceIdentity, app: AppConfig) -> None:
        self.transport = transport
        self.device = device
        self.app = app

    async def create(
        self,
        session: KaspiSession,
        amount: int | float,
        *,
        latitude: float = 43.204643483375889,
        longitude: float = 76.891962364115912,
    ) -> dict[str, Any]:
        url = f"{KASPI_QRPAY_URL}/v01/qr-token/create"
        body = await self.transport.request(
            "POST",
            url,
            headers={**signed_qrpay_headers(url, session, self.device, self.app), "Content-Type": "application/json"},
            json={
                "PaymentAmount": float(amount),
                "DeviceInterface": "Pos",
                "Latitude": latitude,
                "Longitude": longitude,
            },
        )
        data = body.get("Data")
        if isinstance(data, dict) and isinstance(data.get("QrToken"), str):
            data["QrToken"] = data["QrToken"].replace("https://qr.kaspi.kz/", "https://pay.kaspi.kz/pay/")
        return body

    async def status(self, session: KaspiSession, qr_operation_id: int | str) -> dict[str, Any]:
        url = f"{KASPI_QRPAY_URL}/v02/kaspi-qr/status?qrOperationId={qr_operation_id}"
        return await self.transport.request(
            "GET",
            url,
            headers=signed_qrpay_headers(url, session, self.device, self.app),
        )
