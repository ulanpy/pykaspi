from __future__ import annotations

from types import TracebackType

import httpx

from .auth import AuthApi
from .config import AppConfig, DEFAULT_APP_CONFIG
from .device import DeviceIdentity
from .history import HistoryApi
from .invoice import InvoiceApi
from .qr import QrApi
from .refund import RefundApi
from .session import SessionApi
from .transport import KaspiTransport


class KaspiClient:
    """Async entry point for the Kaspi Pay POS client.

    Parameters:
        device: Stable virtual Kaspi device identity. Generate once with
            `DeviceIdentity.generate()` and persist it in secure storage.
        app: Mobile app fingerprint used when signing Kaspi private API requests.
        http_client: Optional externally managed `httpx.AsyncClient`.
        timeout: Default HTTP timeout when pykaspi owns the HTTP client.
        debug: Enable sanitized transport debug logging.

    Attributes:
        auth: SMS login, session refresh, and organization context API.
        qr: QR payment creation/status API.
        invoice: Remote invoice API.
        history: Operations history API.
        refund: Refund API.
        session: Session health-check API.
    """

    def __init__(
        self,
        device: DeviceIdentity | None = None,
        *,
        app: AppConfig = DEFAULT_APP_CONFIG,
        http_client: httpx.AsyncClient | None = None,
        timeout: float = 20.0,
        debug: bool = False,
    ) -> None:
        self.device = device or DeviceIdentity.generate()
        self.app = app
        self.transport = KaspiTransport(client=http_client, timeout=timeout, debug=debug)

        self.auth = AuthApi(self.transport, self.device, self.app)
        self.qr = QrApi(self.transport, self.device, self.app)
        self.invoice = InvoiceApi(self.transport, self.device, self.app)
        self.history = HistoryApi(self.transport, self.device, self.app)
        self.refund = RefundApi(self.transport, self.device, self.app)
        self.session = SessionApi(self.transport, self.device, self.app)

    async def aclose(self) -> None:
        """Close the underlying HTTP client if it is owned by this instance."""
        await self.transport.aclose()

    async def __aenter__(self) -> "KaspiClient":
        """Enter an async context manager and return this client."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.aclose()
