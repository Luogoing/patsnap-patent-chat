from __future__ import annotations

from typing import Any

import httpx

from .config import Settings


class PatsnapConfigError(RuntimeError):
    pass


class PatsnapAPIError(RuntimeError):
    pass


class PatsnapClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.base_url = settings.patsnap_base_url.rstrip("/")

    def _headers(self) -> dict[str, str]:
        if not self.settings.patsnap_api_key:
            raise PatsnapConfigError("缺少 PATSNAP_API_KEY，请先创建本地 .env.local。")
        return {
            "Authorization": f"Bearer {self.settings.patsnap_api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def count(self, query_text: str) -> dict[str, Any]:
        payload = {
            "query_text": query_text,
            "collapse_by": "PBD",
            "collapse_type": "DOCDB",
            "collapse_order": "LATEST",
        }
        return await self._post(self.settings.patsnap_count_path, payload)

    async def search(self, query_text: str, limit: int = 10, offset: int = 0) -> dict[str, Any]:
        payload = {
            "query_text": query_text,
            "limit": max(1, min(limit, 50)),
            "offset": max(0, offset),
            "stemming": True,
            "sort": [{"field": "SCORE", "order": "DESC"}],
        }
        return await self._post(self.settings.patsnap_search_path, payload)

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}/{path.lstrip('/')}"
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, headers=self._headers(), json=payload)
        if response.status_code >= 400:
            raise PatsnapAPIError(f"Patsnap API HTTP {response.status_code}: {response.text[:300]}")
        data = response.json()
        if isinstance(data, dict) and data.get("status") is False and data.get("error_code") not in (0, "0", None):
            raise PatsnapAPIError(f"Patsnap API error {data.get('error_code')}: {data.get('error_msg')}")
        return data
