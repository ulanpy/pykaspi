from __future__ import annotations

import uuid
from datetime import datetime, timezone
from http.cookies import SimpleCookie
from typing import Any

from .config import AppConfig, KASPI_ENTRANCE_URL
from .crypto import compute_token_sn_mac, compute_x_sign, compute_xsu
from .device import DeviceIdentity
from .models import KaspiSession


def generate_uuid() -> str:
    return str(uuid.uuid4()).upper()


def now_iso() -> str:
    now = datetime.now().astimezone()
    milliseconds = now.microsecond // 1000
    offset = now.strftime("%z")
    return now.strftime(f"%Y-%m-%dT%H:%M:%S.{milliseconds:03d}") + offset


def entrance_cookie(device: DeviceIdentity, app: AppConfig, user_token: str | None = None) -> str:
    values = {
        "deviceId": device.device_id,
        "installId": device.install_id,
        "is_mobile_app": "true",
        "locale": app.locale,
        "ma_bld": app.build,
        "ma_platform_type": app.platform,
        "ma_platform_ver": app.platform_ver,
        "ma_ver": app.version,
        "pk": device.pk,
        "pkTag": device.pk_tag,
        "xs": "R:0|E:0|RH:0|N:0",
    }
    if user_token:
        values["user_token"] = user_token
    return "; ".join(f"{key}={value}" for key, value in values.items())


def extract_user_token(set_cookie_headers: list[str] | tuple[str, ...]) -> str | None:
    for raw in set_cookie_headers:
        cookie = SimpleCookie()
        cookie.load(raw)
        if "user_token" in cookie:
            return cookie["user_token"].value
    return None


def entrance_headers_base(app: AppConfig) -> dict[str, str]:
    return {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Accept-Language": "ru",
        "Accept-Encoding": "gzip, deflate, br",
        "Origin": KASPI_ENTRANCE_URL,
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
        "User-Agent": app.browser_user_agent,
    }


def signed_qrpay_headers(
    url: str, session: KaspiSession, device: DeviceIdentity, app: AppConfig, *, body: str | None = None,
) -> dict[str, str]:
    xsh = (
        "url,X-Install-ID,X-PI,X-App-Bld,X-Platform-Ver,X-Locale,X-App-Ver,"
        "X-Device-ID,X-SV,X-Time,X-Platform-Type,X-Call,X-Kb-TokenSnMac,X-Kb-TokenSn"
    )
    headers = {
        "X-Kb-TokenSn": session.token_sn,
        "X-Kb-TokenSnMac": compute_token_sn_mac(session.token_sn, session.vtoken_secret),
        "X-PI": str(session.profile_id) if session.profile_id is not None else "",
        "X-Install-ID": device.install_id,
        "X-Device-ID": device.device_id,
        "X-App-Ver": app.version,
        "X-App-Bld": app.build,
        "X-Platform-Type": app.platform,
        "X-Platform-Ver": app.platform_ver,
        "X-Locale": app.locale,
        "X-Time": now_iso(),
        "X-Request-ID": generate_uuid(),
        "X-Call": "notConnected",
        "X-SV": "2",
        "X-SH": xsh,
        "User-Agent": app.native_user_agent,
        "Accept": "*/*",
        "Accept-Language": "ru",
        "Accept-Encoding": "gzip, deflate, br",
    }
    headers["X-Sign"] = compute_x_sign(url, headers, xsh, device, body)
    return headers


def build_device_information(device: DeviceIdentity, app: AppConfig) -> dict[str, Any]:
    return {
        "SdkVersion": "AOTP service",
        "DeviceId": device.device_id,
        "ApplicationId": "kz.kaspi.business",
        "ScreenWidth": app.screen_w,
        "Model": app.model,
        "ScreenHeight": app.screen_h,
        "DeviceName": app.device_name,
        "VersionName": app.version,
        "BuildRelease": f"{app.platform} {app.platform_ver}",
        "Brand": app.brand,
        "Board": app.platform_ver,
        "Platform": app.platform,
        "Product": "Kaspi Pay",
        "frontCameraAvailable": True,
        "VersionCode": app.build,
        "InstallId": device.install_id,
    }


def build_mtoken_headers(
    url: str,
    token_sn: str,
    secret: bytes,
    device: DeviceIdentity,
    app: AppConfig,
    *,
    profile_id: int | str | None = None,
    include_profile_in_signature: bool = False,
) -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "Accept": "*/*",
        "Accept-Language": "ru",
        "Accept-Encoding": "gzip, deflate, br",
        "User-Agent": app.native_user_agent,
        "X-Kb-TokenSn": token_sn,
        "X-Kb-TokenSnMac": compute_token_sn_mac(token_sn, secret),
        "X-Install-ID": device.install_id,
        "X-App-Ver": app.version,
        "X-App-Bld": app.build,
        "X-Locale": app.locale,
        "X-Call": "notConnected",
        "X-Time": now_iso(),
        "X-S": "R:0|E:0|RH:0|N:0",
        "X-SV": "2",
        "X-Kb-Client-Ip": "192.168.1.96",
        "X-PkTag": device.pk_tag,
        "X-SU": compute_xsu(url),
        "X-Request-ID": generate_uuid(),
    }
    if profile_id is not None:
        headers["X-PI"] = str(profile_id)
    if include_profile_in_signature and profile_id is not None:
        headers["X-SH"] = (
            "url,X-Kb-Client-Ip,X-App-Bld,X-S,X-Kb-TokenSn,X-Time,X-App-Ver,"
            "X-Kb-TokenSnMac,X-Call,X-PI,X-Install-ID,X-Locale,X-SV"
        )
    else:
        headers["X-SH"] = (
            "url,X-Kb-Client-Ip,X-Time,X-App-Ver,X-SV,X-Locale,X-App-Bld,"
            "X-Install-ID,X-Kb-TokenSn,X-S,X-Kb-TokenSnMac,X-Call"
        )
    headers["X-Sign"] = compute_x_sign(url, headers, headers["X-SH"], device)
    return headers


def finish_headers(url: str, device: DeviceIdentity, app: AppConfig) -> dict[str, str]:
    xsh = "url,X-Time-Zone,X-Request-ID,X-Net-Type,X-Emulator,X-Call,X-Platform-Type,X-Locale,X-Time,X-SV"
    headers = {
        "Content-Type": "application/json",
        "Accept": "*/*",
        "Accept-Language": "ru",
        "Accept-Encoding": "gzip, deflate, br",
        "User-Agent": app.native_user_agent,
        "X-Time": now_iso(),
        "X-Call": "notConnected",
        "X-Platform-Type": app.platform,
        "X-PkTag": device.pk_tag,
        "X-SU": compute_xsu(url),
        "X-Net-Type": "WIFI/ETHERNET",
        "X-Emulator": "0",
        "X-Locale": app.locale,
        "X-SV": "2",
        "X-Request-ID": generate_uuid(),
        "X-Time-Zone": "GMT+05:00",
        "X-SH": xsh,
    }
    headers["X-Sign"] = compute_x_sign(url, headers, xsh, device)
    return headers
