from __future__ import annotations

from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field


class FlexibleModel(BaseModel):
    """Base model for Kaspi payloads.

    Kaspi's private API can add fields without warning. Unknown fields are
    accepted, preserved in ``model_extra``, and exposed via attribute access
    when the field name is a valid Python attribute.
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    def raw(self) -> dict[str, Any]:
        """Return a JSON-compatible dictionary using Kaspi's original aliases."""
        return self.model_dump(by_alias=True, exclude_none=True)


DataT = TypeVar("DataT")


class KaspiResponse(FlexibleModel, Generic[DataT]):
    """Generic Kaspi API response wrapper.

    Known top-level fields are exposed as snake_case attributes. The parsed
    endpoint payload is available as `data`.
    """

    data: DataT | None = Field(default=None, alias="Data")
    status_code: int | None = Field(default=None, alias="StatusCode")
    message: str | None = Field(default=None, alias="Message")
    error_display_type: str | None = Field(default=None, alias="ErrorDisplayType")
    code: int | str | None = Field(default=None, alias="Code")
    code_subsystem: str | None = Field(default=None, alias="CodeSubsystem")

    @property
    def ok(self) -> bool:
        """Return true when Kaspi `StatusCode` is missing or equals zero."""
        return self.status_code in (None, 0)


class AuthInitResult(FlexibleModel):
    """Result of `client.auth.init()`.

    `process_id` is a temporary Kaspi entrance process id used by
    `send_phone()` and `verify_otp()`.
    """

    process_id: str
    view: str | None = None
    body: dict[str, Any]


class SendPhoneResult(FlexibleModel):
    """Result of `client.auth.send_phone()`."""

    status: Literal["otp_required", "password_required", "mobile_confirmation_required", "unsupported_challenge"]
    success: bool
    process_id: str
    description: str | None = None
    view: str | None = None
    challenge_type: str | None = None
    operation_type: str | None = None
    auth_methods: list[dict[str, Any]] | None = None
    body: dict[str, Any]

    @property
    def requires_otp(self) -> bool:
        """Return true when Kaspi sent an SMS OTP challenge."""
        return self.status == "otp_required"

    @property
    def requires_password(self) -> bool:
        """Return true when Kaspi requests the account login password."""
        return self.status == "password_required"

    @property
    def requires_mobile_confirmation(self) -> bool:
        """Return true when Kaspi requested app/mobile confirmation."""
        return self.status == "mobile_confirmation_required"


class QrPaymentBehaviorOptions(FlexibleModel):
    """Kaspi QR frontend timing/options payload."""

    payment_confirmation_timeout: str | int | None = Field(default=None, alias="paymentConfirmationTimeout")
    payment_status_countdown: str | int | None = Field(default=None, alias="paymentStatusCountdown")
    qr_code_scan_event_polling_interval: str | int | None = Field(
        default=None,
        alias="qrCodeScanEventPollingInterval",
    )
    qr_code_scan_wait_timeout: str | int | None = Field(default=None, alias="qrCodeScanWaitTimeout")
    qr_code_embed_kaspi_logo: str | bool | None = Field(default=None, alias="qrCodeEmbedKaspiLogo")


class QrCreateData(FlexibleModel):
    """Data returned by QR token creation."""

    qr_operation_id: int | None = Field(default=None, alias="QrOperationId")
    ext_tran_id: str | None = Field(default=None, alias="ExtTranId")
    status: str | None = Field(default=None, alias="Status")
    qr_token: str | None = Field(default=None, alias="QrToken")
    expire_date: str | None = Field(default=None, alias="ExpireDate")
    qr_payment_behavior_options: QrPaymentBehaviorOptions | dict[str, Any] | None = Field(
        default=None,
        alias="QrPaymentBehaviorOptions",
    )
    receipt_url: str | None = Field(default=None, alias="ReceiptUrl")
    amount: float | int | str | None = Field(default=None, alias="Amount")


class QrStatusData(FlexibleModel):
    """Data returned by QR status lookup."""

    id: int | None = Field(default=None, alias="Id")
    status: str | None = Field(default=None, alias="Status")
    status_desc: str | None = Field(default=None, alias="StatusDesc")
    order_reg_date: str | None = Field(default=None, alias="OrderRegDate")
    cheque_title: str | None = Field(default=None, alias="ChequeTitle")


class InvoiceClientInfoData(FlexibleModel):
    """Customer lookup result for remote invoice creation."""

    client_name: str | None = Field(default=None, alias="ClientName")
    client_status: str | None = Field(default=None, alias="ClientStatus")


class InvoiceCreateData(FlexibleModel):
    """Data returned by remote invoice creation."""

    id: int | None = Field(default=None, alias="Id")
    qr_operation_id: int | None = Field(default=None, alias="QrOperationId")
    status: str | None = Field(default=None, alias="Status")
    amount: float | int | str | None = Field(default=None, alias="Amount")
    client_mobile: str | None = Field(default=None, alias="ClientMobile")
    receipt_url: str | None = Field(default=None, alias="ReceiptUrl")
    order_number: str | int | None = Field(default=None, alias="OrderNumber")


class InvoiceDetailsData(FlexibleModel):
    """Data returned by remote invoice details lookup."""

    id: int | None = Field(default=None, alias="Id")
    qr_operation_id: int | None = Field(default=None, alias="QrOperationId")
    status: str | None = Field(default=None, alias="Status")
    status_desc: str | None = Field(default=None, alias="StatusDesc")
    amount: float | int | str | None = Field(default=None, alias="Amount")
    client_mobile: str | None = Field(default=None, alias="ClientMobile")
    receipt_url: str | None = Field(default=None, alias="ReceiptUrl")
    order_number: str | int | None = Field(default=None, alias="OrderNumber")


class HistoryOperationsData(FlexibleModel):
    """Operations history payload."""

    formatted_period: str | None = Field(default=None, alias="FormattedPeriod")
    period_with_line_break: str | None = Field(default=None, alias="PeriodWithLineBreak")
    statistics: dict[str, Any] | None = Field(default=None, alias="Statistics")
    daily_sets: list[dict[str, Any]] | None = Field(default=None, alias="DailySets")
    icons: list[Any] | None = Field(default=None, alias="Icons")
    list_history_payment_data: list[dict[str, Any]] | None = Field(default=None, alias="ListHistoryPaymentData")


class OperationDetailsData(FlexibleModel):
    """Single operation details payload."""

    id: int | None = Field(default=None, alias="Id")
    status: str | None = Field(default=None, alias="Status")
    amount: float | int | None = Field(default=None, alias="Amount")


class RefundCreateData(FlexibleModel):
    """Data returned by refund creation."""

    id: int | None = Field(default=None, alias="Id")
    status: str | None = Field(default=None, alias="Status")
    return_amount: float | int | None = Field(default=None, alias="ReturnAmount")
    qr_operation_id: int | None = Field(default=None, alias="QrOperationId")


class SessionCheckResult(FlexibleModel):
    """Result of `client.session.check()`.

    `active` indicates whether Kaspi accepted the current session. `body`
    contains the underlying Kaspi history response used as a lightweight ping.
    """

    active: bool
    body: KaspiResponse[HistoryOperationsData | dict[str, Any]]
