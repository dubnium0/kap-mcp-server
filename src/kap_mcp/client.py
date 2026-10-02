from __future__ import annotations

import asyncio
from typing import Any

import httpx

from .errors import KapError, UPSTREAM_CHANGED, UPSTREAM_UNAVAILABLE


class KapHttpClient:
    """Shared polite async client for KAP's reverse-engineered web API."""

    def __init__(
        self,
        base_url: str = "https://kap.org.tr/tr/api",
        *,
        connect_timeout: float = 10.0,
        read_timeout: float = 30.0,
        retries: int = 2,
        min_interval: float = 0.1,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        timeout = httpx.Timeout(read_timeout, connect=connect_timeout)
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            follow_redirects=True,
            transport=transport,
            headers={
                "Accept": "application/json, application/pdf, application/octet-stream;q=0.9, */*;q=0.8",
                "Accept-Language": "tr-TR,tr;q=0.9",
                "User-Agent": "kap-mcp/0.1 (+https://kap.org.tr)",
            },
        )
        self._retries = retries
        self._min_interval = min_interval
        self._rate_lock = asyncio.Lock()
        self._last_request = 0.0

    async def __aenter__(self) -> KapHttpClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        for attempt in range(self._retries + 1):
            try:
                async with self._rate_lock:
                    loop = asyncio.get_running_loop()
                    delay = self._min_interval - (loop.time() - self._last_request)
                    if delay > 0:
                        await asyncio.sleep(delay)
                    response = await self._client.request(method, path, **kwargs)
                    self._last_request = loop.time()
                if response.status_code in {429, 502, 503, 504} and attempt < self._retries:
                    await asyncio.sleep(0.4 * (2**attempt))
                    continue
                if response.status_code >= 500:
                    raise KapError(
                        UPSTREAM_UNAVAILABLE,
                        f"KAP geçici olarak kullanılamıyor (HTTP {response.status_code}).",
                        True,
                        {"path": path, "status": response.status_code},
                    )
                if response.status_code >= 400:
                    raise KapError(
                        UPSTREAM_CHANGED,
                        f"KAP isteği reddetti (HTTP {response.status_code}).",
                        False,
                        {"path": path, "status": response.status_code},
                    )
                return response
            except httpx.RequestError as exc:
                if attempt < self._retries:
                    await asyncio.sleep(0.4 * (2**attempt))
                    continue
                raise KapError(
                    UPSTREAM_UNAVAILABLE,
                    "KAP ağına erişilemedi.",
                    True,
                    {"path": path, "cause": type(exc).__name__},
                ) from exc
        raise AssertionError("unreachable")

    async def get_json(self, path: str) -> Any:
        response = await self._request("GET", path)
        try:
            return response.json()
        except ValueError as exc:
            raise KapError(UPSTREAM_CHANGED, "KAP JSON yerine beklenmeyen içerik döndürdü.", context={"path": path}) from exc

    async def post_json(self, path: str, payload: dict[str, Any]) -> Any:
        response = await self._request("POST", path, json=payload)
        try:
            return response.json()
        except ValueError as exc:
            raise KapError(UPSTREAM_CHANGED, "KAP JSON yerine beklenmeyen içerik döndürdü.", context={"path": path}) from exc

    async def get_bytes(self, path: str) -> tuple[bytes, str | None, str]:
        response = await self._request("GET", path)
        return response.content, response.headers.get("content-type"), str(response.url)
