from __future__ import annotations

from .config import AppConfig, KASPI_QRPAY_URL
from .device import DeviceIdentity
from .headers import signed_qrpay_headers
from .models import KaspiSession
from .schemas import KaspiResponse, QrCreateData, QrStatusData
from .transport import KaspiTransport
from .wire import json_body


class QrApi:
    """Kaspi QR payment API."""

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
    ) -> KaspiResponse[QrCreateData]:
        """Create a Kaspi QR payment token.

        Args:
            session: Active Kaspi session.
            amount: Payment amount in KZT.
            latitude: POS latitude sent to Kaspi.
            longitude: POS longitude sent to Kaspi.

        Returns:
            `KaspiResponse[QrCreateData]` with `data.qr_operation_id`,
            `data.qr_token`, `data.expire_date`, and other Kaspi fields.
        """
        url = f"{KASPI_QRPAY_URL}/v01/qr-token/create"
        payload = json_body({"PaymentAmount": float(amount), "DeviceInterface": "Pos", "Latitude": latitude, "Longitude": longitude})
        body = await self.transport.request(
            "POST",
            url,
            headers={**signed_qrpay_headers(url, session, self.device, self.app, body=payload), "Content-Type": "application/json"}, content=payload,
        )
        data = body.get("Data")
        if isinstance(data, dict) and isinstance(data.get("QrToken"), str):
            data["QrToken"] = data["QrToken"].replace("https://qr.kaspi.kz/", "https://pay.kaspi.kz/pay/")
        return KaspiResponse[QrCreateData].model_validate(body)

    async def status(self, session: KaspiSession, qr_operation_id: int | str) -> KaspiResponse[QrStatusData]:
        """Fetch QR payment status by Kaspi QR operation id."""
        url = f"{KASPI_QRPAY_URL}/v02/kaspi-qr/status?qrOperationId={qr_operation_id}"
        body = await self.transport.request(
            "GET",
            url,
            headers=signed_qrpay_headers(url, session, self.device, self.app),
        )
        return KaspiResponse[QrStatusData].model_validate(body)
