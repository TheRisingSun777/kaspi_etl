"""
Kaspi API client (read-only skeleton) for Phase 1.

Usage:
  from scripts.kaspi_api import KaspiAPI
  api = KaspiAPI(token=os.environ["KASPI_TOKEN"])  # loads base https://kaspi.kz/shop/api/v2
  orders = api.get_orders("2025-08-01", "2025-08-13", state="NEW")

Notes:
- Headers per docs/kaspi_api.md: X-Auth-Token and Accept JSON:API
- Retries with simple exponential backoff on 429/5xx
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import httpx


DEFAULT_BASE = "https://kaspi.kz"
DEFAULT_SHOP_API = "/shop/api/v2"


class KaspiAPI:
    def __init__(
        self,
        token: str,
        base: str = DEFAULT_BASE,
        shop_api: Optional[str] = None,
        timeout_seconds: float = 30.0,
        max_retries: int = 5,
    ) -> None:
        api_path = shop_api or DEFAULT_SHOP_API
        if api_path.startswith("http"):
            base_url = api_path.rstrip("/")
        else:
            base_url = f"{base.rstrip('/')}{api_path}"

        self.base_url = base_url
        self.max_retries = max_retries
        self.client = httpx.Client(
            base_url=base_url,
            timeout=httpx.Timeout(timeout_seconds),
            headers={
                "X-Auth-Token": token,
                "Accept": "application/vnd.api+json;charset=UTF-8",
                "User-Agent": "kaspi-etl/phase1 (+https://github.com/TheRisingSun777/kaspi_etl)",
            },
        )

    def _get(self, path: str, params: Dict[str, Any]) -> httpx.Response:
        last_exc: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.client.get(path, params=params)
                if response.status_code in (429, 500, 502, 503, 504):
                    raise httpx.HTTPStatusError(
                        f"Retryable status {response.status_code}", request=response.request, response=response
                    )
                response.raise_for_status()
                return response
            except Exception as exc:  # retry on any client/server/network error
                last_exc = exc
                # exponential backoff with jitter
                sleep_s = min(2 ** (attempt - 1), 10) + 0.1 * attempt
                time.sleep(sleep_s)
        assert last_exc is not None
        raise last_exc

    @staticmethod
    def _normalize_date(date_str: str, end: bool = False) -> str:
        # Accept YYYY-MM-DD or full ISO. If date only, append T00:00:00Z or T23:59:59Z
        ds = date_str.strip()
        if len(ds) == 10 and ds.count("-") == 2:
            return f"{ds}T23:59:59Z" if end else f"{ds}T00:00:00Z"
        return ds

    def get_orders(
        self,
        date_from: str,
        date_to: str,
        state: Optional[str] = None,
        page_size: int = 100,
        include_user: bool = True,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "filter[orders][creationDate][$ge]": self._normalize_date(date_from, end=False),
            "filter[orders][creationDate][$le]": self._normalize_date(date_to, end=True),
            "page[number]": 1,
            "page[size]": page_size,
        }
        if state:
            params["filter[orders][state]"] = state
        if include_user:
            params["include[orders]"] = "user"

        all_data: List[Dict[str, Any]] = []
        all_included: List[Dict[str, Any]] = []
        total_pages: Optional[int] = None
        fetched_pages = 0

        while True:
            resp = self._get("/orders", params=params)
            payload = resp.json()
            data_chunk = payload.get("data", [])
            all_data.extend(data_chunk)
            included_chunk = payload.get("included", []) or []
            if included_chunk:
                all_included.extend(included_chunk)
            fetched_pages += 1
            meta = payload.get("meta") or {}
            links = payload.get("links") or {}
            if total_pages is None:
                total_pages = int(meta.get("totalPages") or 1)

            # next page?
            if fetched_pages >= total_pages or not links.get("next"):
                break
            params["page[number]"] = int(params.get("page[number]", 1)) + 1

        return {
            "data": all_data,
            "included": all_included,
            "meta": {"totalPages": total_pages or 1, "fetchedPages": fetched_pages},
            "range": {"from": date_from, "to": date_to},
            "state": state,
        }

    def get_products(self, page_size: int = 100) -> Dict[str, Any]:
        params: Dict[str, Any] = {"page[number]": 1, "page[size]": page_size}
        all_data: List[Dict[str, Any]] = []
        total_pages: Optional[int] = None
        fetched_pages = 0
        while True:
            resp = self._get("/products", params=params)
            payload = resp.json()
            all_data.extend(payload.get("data", []))
            fetched_pages += 1
            meta = payload.get("meta") or {}
            links = payload.get("links") or {}
            if total_pages is None:
                total_pages = int(meta.get("totalPages") or 1)
            if fetched_pages >= total_pages or not links.get("next"):
                break
            params["page[number]"] = int(params.get("page[number]", 1)) + 1
        return {"data": all_data, "meta": {"totalPages": total_pages or 1, "fetchedPages": fetched_pages}}

    def close(self) -> None:
        self.client.close()


__all__ = ["KaspiAPI"]


