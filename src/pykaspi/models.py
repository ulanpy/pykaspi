from __future__ import annotations

import base64
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class KaspiSession:
    token_sn: str
    vtoken_secret: bytes
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
        return base64.b64encode(self.vtoken_secret).decode()

    @classmethod
    def from_base64(cls, token_sn: str, vtoken_secret_b64: str, **kwargs: Any) -> "KaspiSession":
        return cls(token_sn=token_sn, vtoken_secret=base64.b64decode(vtoken_secret_b64), **kwargs)


@dataclass(slots=True)
class EntranceSession:
    process_id: str | None = None
    user_token: str | None = None
    phone_number: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


def apply_org_context(session: KaspiSession, data: dict[str, Any]) -> KaspiSession:
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
