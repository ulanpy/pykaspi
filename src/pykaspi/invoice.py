from __future__ import annotations

from typing import Any

from .config import AppConfig, KASPI_QRPAY_URL
from .device import DeviceIdentity
from .headers import signed_qrpay_headers
from .models import KaspiSession
from .schemas import InvoiceClientInfoData, InvoiceCreateData, InvoiceDetailsData, KaspiResponse
from .transport import KaspiTransport


class InvoiceApi:
    """Remote invoice API for payments by customer phone number."""

    def __init__(self, transport: KaspiTransport, device: DeviceIdentity, app: AppConfig) -> None:
        self.transport = transport
        self.device = device
        self.app = app

    async def client_info(self, session: KaspiSession, phone_number: str) -> KaspiResponse[InvoiceClientInfoData]:
        """Look up a customer before creating a remote invoice.

        Args:
            session: Active Kaspi session.
            phone_number: Customer phone as local KZ digits without `+7`.
        """
        url = f"{KASPI_QRPAY_URL}/v01/remote/client-info?phoneNumber={phone_number}"
        body = await self.transport.request("GET", url, headers=signed_qrpay_headers(url, session, self.device, self.app))
        return KaspiResponse[InvoiceClientInfoData].model_validate(body)

    async def create(
        self,
        session: KaspiSession,
        phone_number: str,
        amount: int | float,
        *,
        comment: str = "",
    ) -> KaspiResponse[InvoiceCreateData]:
        """Create a remote invoice for a customer phone number.

        Args:
            session: Active Kaspi session.
            phone_number: Customer phone as local KZ digits without `+7`.
            amount: Invoice amount in KZT.
            comment: Optional invoice comment visible in Kaspi.
        """
        url = f"{KASPI_QRPAY_URL}/v01/remote/create"
        body = await self.transport.request(
            "POST",
            url,
            headers={**signed_qrpay_headers(url, session, self.device, self.app), "Content-Type": "application/json"},
            json={"PhoneNumber": phone_number, "Amount": float(amount), "Comment": comment},
        )
        return KaspiResponse[InvoiceCreateData].model_validate(body)

    async def details(self, session: KaspiSession, operation_id: int | str) -> KaspiResponse[InvoiceDetailsData]:
        """Fetch remote invoice details by operation id."""
        url = f"{KASPI_QRPAY_URL}/v02/remote/details?operationId={operation_id}"
        body = await self.transport.request("GET", url, headers=signed_qrpay_headers(url, session, self.device, self.app))
        return KaspiResponse[InvoiceDetailsData].model_validate(body)

    async def cancel(self, session: KaspiSession, operation_id: int | str) -> KaspiResponse[dict[str, Any]]:
        """Cancel an unpaid remote invoice by operation id."""
        url = f"{KASPI_QRPAY_URL}/v01/remote/cancel"
        body = await self.transport.request(
            "POST",
            url,
            headers={**signed_qrpay_headers(url, session, self.device, self.app), "Content-Type": "application/json"},
            json={"qrOperationId": int(operation_id)},
        )
        return KaspiResponse[dict[str, Any]].model_validate(body)

    async def history(self, session: KaspiSession, *, max_result: int = 20) -> KaspiResponse[dict[str, Any]]:
        """Fetch remote invoice history."""
        url = f"{KASPI_QRPAY_URL}/v01/remote/history"
        body = await self.transport.request(
            "POST",
            url,
            headers={**signed_qrpay_headers(url, session, self.device, self.app), "Content-Type": "application/json"},
            json={"MaxResult": max_result},
        )
        return KaspiResponse[dict[str, Any]].model_validate(body)
