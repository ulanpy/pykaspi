from __future__ import annotations

from dataclasses import dataclass


KASPI_ENTRANCE_URL = "https://entrance-pay.kaspi.kz"
KASPI_MTOKEN_URL = "https://mtoken.kaspi.kz"
KASPI_QRPAY_URL = "https://qrpay.kaspi.kz"


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Kaspi Pay mobile app fingerprint used by the private API."""

    version: str = "4.112.1"
    build: str = "1107"
    platform: str = "iOS"
    platform_ver: str = "18.4"
    locale: str = "ru-RU"
    model: str = "iPhone16,2"
    brand: str = "Apple"
    device_name: str = "iPhone"
    screen_w: str = "430.0"
    screen_h: str = "932.0"
    cf_network: str = "CFNetwork/3826.400.120"
    darwin: str = "Darwin/24.4.0"

    @property
    def native_user_agent(self) -> str:
        return f"Kaspi%20Pay/{self.build} {self.cf_network} {self.darwin}"

    @property
    def browser_user_agent(self) -> str:
        platform_ver = self.platform_ver.replace(".", "_")
        return (
            f"Mozilla/5.0 (iPhone; CPU iPhone OS {platform_ver} like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148"
        )


DEFAULT_APP_CONFIG = AppConfig()
