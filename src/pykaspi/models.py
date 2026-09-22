from __future__ import annotations

import base64
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class KaspiSession:
    """Authenticated Kaspi Pay session returned after SMS login or refresh.

    Persist this object in your own secure storage together with
    `DeviceIdentity`. `token_sn`, `vtoken_secret`, and `ecdh_private_key_b64`
    are sensitive credentials. If `auth.refresh()` raises
    `KaspiReauthRequiredError`, the user must repeat SMS login.
    """

    token_sn: str
    vtoken_secret: bytes
    ecdh_private_key_b64: str | None = None
    profile_id: int | str | None = None
    phone_number: str | None = None
    org_name: str | None = None
    user_id: str | int | None = None
    organization_id: int | str | None = None
    organization_idn: str | None = None
    organization_kbe: str | None = None
    emp_id: int | str | None = None
    access_level_type: int | str | None = None
    is_cashier: bool | None = None
    payer_type: str | None = None
    category_name: str | None = None
    possible_payment_methods: Any = None
    show_fake_card: bool | None = None
    organizations: list[dict[str, Any]] | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def vtoken_secret_b64(self) -> str:
        """Return the raw vtoken secret encoded as base64 for storage."""
        return base64.b64encode(self.vtoken_secret).decode()

    @classmethod
    def from_base64(cls, token_sn: str, vtoken_secret_b64: str, **kwargs: Any) -> "KaspiSession":
        """Restore a session from a stored token and base64 vtoken secret."""
        return cls(token_sn=token_sn, vtoken_secret=base64.b64decode(vtoken_secret_b64), **kwargs)

    def to_dict(self) -> dict[str, Any]:
        """Serialize this session to a storage-agnostic dictionary.

        The returned mapping is JSON-compatible and can be stored in files,
        JSONB columns, Redis, Vault, or split into ORM columns. Treat the
        result as sensitive credentials.
        """
        return {
            "token_sn": self.token_sn,
            "vtoken_secret_b64": self.vtoken_secret_b64,
            "ecdh_private_key_b64": self.ecdh_private_key_b64,
            "profile_id": self.profile_id,
            "phone_number": self.phone_number,
            "org_name": self.org_name,
            "user_id": self.user_id,
            "organization_id": self.organization_id,
            "organization_idn": self.organization_idn,
            "organization_kbe": self.organization_kbe,
            "emp_id": self.emp_id,
            "access_level_type": self.access_level_type,
            "is_cashier": self.is_cashier,
            "payer_type": self.payer_type,
            "category_name": self.category_name,
            "possible_payment_methods": self.possible_payment_methods,
            "show_fake_card": self.show_fake_card,
            "organizations": self.organizations,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "KaspiSession":
        """Restore a session from `to_dict()` output or an equivalent mapping."""
        return cls.from_base64(
            token_sn=data["token_sn"],
            vtoken_secret_b64=data["vtoken_secret_b64"],
            ecdh_private_key_b64=data.get("ecdh_private_key_b64"),
            profile_id=data.get("profile_id"),
            phone_number=data.get("phone_number"),
            org_name=data.get("org_name"),
            user_id=data.get("user_id"),
            organization_id=data.get("organization_id"),
            organization_idn=data.get("organization_idn"),
            organization_kbe=data.get("organization_kbe"),
            emp_id=data.get("emp_id"),
            access_level_type=data.get("access_level_type"),
            is_cashier=data.get("is_cashier"),
            payer_type=data.get("payer_type"),
            category_name=data.get("category_name"),
            possible_payment_methods=data.get("possible_payment_methods"),
            show_fake_card=data.get("show_fake_card"),
            organizations=data.get("organizations"),
        )


@dataclass(slots=True)
class EntranceSession:
    """Temporary state for the SMS entrance flow.

    Users normally do not need to instantiate this directly. It is held in
    memory by `AuthApi` between `init()`, `send_phone()`, and `verify_otp()`.
    """

    process_id: str | None = None
    user_token: str | None = None
    phone_number: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


def apply_org_context(session: KaspiSession, data: dict[str, Any]) -> KaspiSession:
    """Apply Kaspi organization context payload to an existing session."""
    current = data.get("Current") or {}
    session.profile_id = current.get("ProfileId") or session.profile_id
    session.org_name = current.get("OrganizationName") or session.org_name
    session.organization_id = current.get("OrganizationId") or session.organization_id
    session.organization_idn = current.get("OrganizationIdn") or session.organization_idn
    session.organization_kbe = current.get("OrganizationKbe") or session.organization_kbe
    session.emp_id = current.get("EmpId") or session.emp_id
    session.access_level_type = current.get("AccessLevelType", session.access_level_type)
    session.is_cashier = current.get("IsCashier", session.is_cashier)
    session.payer_type = current.get("PayerType") or session.payer_type
    session.category_name = current.get("CategoryName") or session.category_name
    session.possible_payment_methods = current.get("PossiblePaymentMethods") or session.possible_payment_methods
    session.show_fake_card = current.get("ShowFakeCard", session.show_fake_card)
    session.user_id = data.get("UserId") or session.user_id
    session.phone_number = data.get("PhoneNumber") or session.phone_number
    session.organizations = data.get("Organizations") or session.organizations
    return session
