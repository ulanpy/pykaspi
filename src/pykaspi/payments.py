from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Literal

from .models import KaspiSession
from .schemas import KaspiResponse


PaymentType = Literal["qr", "invoice"]

QR_FINAL_STATUSES = {
    "Processed": "payment.success",
    "CancelledByUser": "payment.failed",
    "NotConfirmedByUser": "payment.failed",
    "CancelledByExternalSource": "payment.failed",
    "ProcessingFailed": "payment.failed",
    "Rejected": "payment.failed",
    "InsufficientFunds": "payment.failed",
    "InsufficientFundsError": "payment.failed",
    "Error": "payment.failed",
    "IrisSrcBlockCode1": "payment.failed",
    "IrisSrcBlockCode3": "payment.failed",
    "IrisSrcBlockCode9": "payment.failed",
    "IrisDestBlockCode3": "payment.failed",
    "IrisDestBlockCode5": "payment.failed",
    "IrisDestBlockCode7": "payment.failed",
    "IrisDestBlockCode10": "payment.failed",
    "QrTokenDiscarded": "payment.expired",
    "Expired": "payment.expired",
}

INVOICE_FINAL_STATUSES = {
    "Processed": "payment.success",
    "RemotePaymentCanceled": "payment.failed",
    "RemotePaymentRejected": "payment.failed",
    "Expired": "payment.expired",
}

QR_INTERMEDIATE = {"QrTokenCreated", "Wait"}
INVOICE_INTERMEDIATE = {"RemotePaymentCreated"}


def resolve_payment_event(payment_type: PaymentType, status: str) -> str | None:
    """Map a Kaspi payment status to a normalized payment event.

    Returns `None` for intermediate statuses that should continue polling.
    """
    if payment_type == "qr":
        if status in QR_INTERMEDIATE:
            return None
        return QR_FINAL_STATUSES.get(status, "payment.failed")
    if status in INVOICE_INTERMEDIATE:
        return None
    return INVOICE_FINAL_STATUSES.get(status, "payment.failed")


@dataclass(slots=True)
class PaymentPollResult:
    """Result returned by `poll_until_final`."""

    event: str
    status: str
    body: Any


def _extract_status(body: Any) -> str:
    if isinstance(body, KaspiResponse):
        data = body.data
        if data is None:
            return "Unknown"
        if isinstance(data, dict):
            return str(data.get("Status") or "Unknown")
        return str(getattr(data, "status", None) or getattr(data, "Status", None) or "Unknown")
    if isinstance(body, dict):
        return str(((body.get("Data") or {}).get("Status")) or "Unknown")
    return str(getattr(body, "status", None) or "Unknown")


async def poll_until_final(
    fetch_status: Callable[[KaspiSession, int | str], Awaitable[Any]],
    session: KaspiSession,
    payment_id: int | str,
    *,
    payment_type: PaymentType = "qr",
    interval: float = 3.0,
    timeout: float = 180.0,
) -> PaymentPollResult:
    """Poll a payment status function until a final event is observed.

    Args:
        fetch_status: Async function like `client.qr.status` or
            `client.invoice.details`.
        session: Active Kaspi session.
        payment_id: Kaspi operation id.
        payment_type: Either `"qr"` or `"invoice"`.
        interval: Delay between status checks in seconds.
        timeout: Maximum wait time in seconds.
    """
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        body = await fetch_status(session, payment_id)
        status = _extract_status(body)
        event = resolve_payment_event(payment_type, status)
        if event:
            return PaymentPollResult(event=event, status=status, body=body)
        if asyncio.get_running_loop().time() >= deadline:
            return PaymentPollResult(event="payment.expired", status=status, body=body)
        await asyncio.sleep(interval)
