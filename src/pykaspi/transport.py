from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import httpx

from .exceptions import KaspiApiError


SENSITIVE_HEADERS = {"authorization", "cookie", "x-kb-tokensn", "x-kb-tokensnmac", "x-sign"}


class KaspiTransport:
    def __init__(
        self,
        *,
        client: httpx.AsyncClient | None = None,
        timeout: float = 20.0,
        debug: bool = False,
        logger: logging.Logger | None = None,
    ) -> None:
        self._own_client = client is None
        self.client = client or httpx.AsyncClient(timeout=timeout)
        self.debug = debug
        self.logger = logger or logging.getLogger("pykaspi")

    async def aclose(self) -> None:
        if self._own_client:
            await self.client.aclose()

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        json: Any = None,
        params: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        response, body = await self.request_with_response(method, url, headers=headers, json=json, params=params)
        if response.is_error:
            message = body.get("Message") or body.get("message") or response.reason_phrase
            raise KaspiApiError(message, status_code=response.status_code, body=body)

        return body

    async def request_with_response(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        json: Any = None,
        params: Mapping[str, Any] | None = None,
    ) -> tuple[httpx.Response, dict[str, Any]]:
        if self.debug:
            self.logger.debug("Kaspi request %s %s headers=%s", method, url, self._sanitize(headers or {}))
        try:
            response = await self.client.request(method, url, headers=headers, json=json, params=params)
        except httpx.HTTPError as exc:
            raise KaspiApiError(str(exc)) from exc

        try:
            body = response.json()
        except ValueError:
            body = {"raw": response.text}

        if self.debug:
            self.logger.debug("Kaspi response %s %s body=%s", response.status_code, response.reason_phrase, body)

        return response, body

    def _sanitize(self, headers: Mapping[str, str]) -> dict[str, str]:
        return {
            key: "***" if key.lower() in SENSITIVE_HEADERS else value
            for key, value in headers.items()
        }
