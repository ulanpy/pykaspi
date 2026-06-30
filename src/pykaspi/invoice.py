from __future__ import annotations

from typing import Any

from .config import AppConfig, KASPI_QRPAY_URL
from .device import DeviceIdentity
from .headers import signed_qrpay_headers
from .models import KaspiSession
from .transport import KaspiTransport


class InvoiceApi:
    def __init__(self, transport: KaspiTransport, device: DeviceIdentity, app: AppConfig) -> None:
        self.transport = transport
        self.device = device
        self.app = app

    async def client_info(self, session: KaspiSession, phone_number: str) -> dict[str, Any]:
        url = f"{KASPI_QRPAY_URL}/v01/remote/client-info?phoneNumber={phone_number}"
        return await self.transport.request("GET", url, headers=signed_qrpay_headers(url, session, self.device, self.app))

    async def create(self, session: KaspiSession, phone_number: str, amount: int | float, *, comment: str = "") -> dict[str, Any]:
        url = f"{KASPI_QRPAY_URL}/v01/remote/create"
        return await self.transport.request(
            "POST",
            url,
            headers={**signed_qrpay_headers(url, session, self.device, self.app), "Content-Type": "application/json"},
            json={"PhoneNumber": phone_number, "Amount": float(amount), "Comment": comment},
        )

    async def details(self, session: KaspiSession, operation_id: int | str) -> dict[str, Any]:
        url = f"{KASPI_QRPAY_URL}/v02/remote/details?operationId={operation_id}"
        return await self.transport.request("GET", url, headers=signed_qrpay_headers(url, session, self.device, self.app))

    async def cancel(self, session: KaspiSession, operation_id: int | str) -> dict[str, Any]:
        url = f"{KASPI_QRPAY_URL}/v01/remote/cancel"
        return await self.transport.request(
            "POST",
            url,
            headers={**signed_qrpay_headers(url, session, self.device, self.app), "Content-Type": "application/json"},
            json={"qrOperationId": int(operation_id)},
        )

    async def history(self, session: KaspiSession, *, max_result: int = 20) -> dict[str, Any]:
        url = f"{KASPI_QRPAY_URL}/v01/remote/history"
        return await self.transport.request(
            "POST",
            url,
            headers={**signed_qrpay_headers(url, session, self.device, self.app), "Content-Type": "application/json"},
            json={"MaxResult": max_result},
        )
