from __future__ import annotations

from typing import Any

from .config import AppConfig, KASPI_QRPAY_URL
from .device import DeviceIdentity
from .headers import signed_qrpay_headers
from .models import KaspiSession
from .schemas import InvoiceClientInfoData, InvoiceCreateData, InvoiceDetailsData, KaspiResponse
from .transport import KaspiTransport
from .payments import PaymentPollResult, poll_until_final
from .validation import normalize_phone, validate_amount
from .wire import json_body


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
        phone_number = normalize_phone(phone_number)
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
        phone_number = normalize_phone(phone_number)
        amount = validate_amount(amount)
        url = f"{KASPI_QRPAY_URL}/v01/remote/create"
        payload = json_body({"PhoneNumber": phone_number, "Amount": float(amount), "Comment": comment})
        body = await self.transport.request(
            "POST",
            url,
            headers={**signed_qrpay_headers(url, session, self.device, self.app, body=payload), "Content-Type": "application/json"},
            content=payload,
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
        payload = json_body({"qrOperationId": int(operation_id)})
        body = await self.transport.request(
            "POST",
            url,
            headers={**signed_qrpay_headers(url, session, self.device, self.app, body=payload), "Content-Type": "application/json"}, content=payload,
        )
        return KaspiResponse[dict[str, Any]].model_validate(body)

    async def wait_for_payment(
        self, session: KaspiSession, operation_id: int | str, *,
        interval: float = 3.0, timeout: float = 180.0,
    ) -> PaymentPollResult:
        """Wait for a bank-reported final status; timeout leaves payment unresolved.

        Only `payment.success` / `Processed` confirms payment. Persist the
        operation id before waiting; call again to resume after a timeout.
        API/network errors propagate and never trigger invoice recreation.
        """
        return await poll_until_final(
            self.details, session, operation_id, payment_type="invoice",
            interval=interval, timeout=timeout,
        )

    async def history(self, session: KaspiSession, *, max_result: int = 20) -> KaspiResponse[dict[str, Any]]:
        """Fetch remote invoice history."""
        url = f"{KASPI_QRPAY_URL}/v01/remote/history"
        payload = json_body({"MaxResult": max_result})
        body = await self.transport.request(
            "POST",
            url,
            headers={**signed_qrpay_headers(url, session, self.device, self.app, body=payload), "Content-Type": "application/json"}, content=payload,
        )
        return KaspiResponse[dict[str, Any]].model_validate(body)
