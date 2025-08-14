# src/services/http_client.py
from __future__ import annotations
import asyncio, os
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential_jitter, retry_if_exception_type

READ_T = float(os.getenv("HTTP_READ_TIMEOUT", "30"))
CONN_T = float(os.getenv("HTTP_CONNECT_TIMEOUT", "5"))
WRITE_T = float(os.getenv("HTTP_WRITE_TIMEOUT", "10"))
POOL_T = float(os.getenv("HTTP_POOL_TIMEOUT", "5"))

TIMEOUT = httpx.Timeout(connect=CONN_T, read=READ_T, write=WRITE_T, pool=POOL_T)
LIMITS = httpx.Limits(max_connections=30, max_keepalive_connections=10, keepalive_expiry=30)

DEFAULT_HEADERS = {
    "User-Agent": os.getenv("HTTP_USER_AGENT", "Mozilla/5.0 (KaspiETL)"),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": os.getenv("HTTP_ACCEPT_LANGUAGE", "ru,en;q=0.9"),
}

def _cookie_dict(raw_cookie: str | None):
    if not raw_cookie: return None
    out = {}
    for part in raw_cookie.split(";"):
        part = part.strip()
        if "=" in part:
            k, v = part.split("=", 1)
            out[k] = v
    return out or None

def async_client(headers: dict | None = None, cookie: str | None = None) -> httpx.AsyncClient:
    h = {**DEFAULT_HEADERS, **(headers or {})}
    return httpx.AsyncClient(
        timeout=TIMEOUT,
        limits=LIMITS,
        headers=h,
        cookies=_cookie_dict(cookie),
        follow_redirects=True,
        http2=False,  # flip to True only if server supports it reliably
    )

Retryable = (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteError, httpx.RemoteProtocolError, httpx.PoolTimeout)

def _as_timeout(seconds: float):
    # AnyIO/asyncio safety: cap total op time so Ctrl-C isn't the only escape hatch
    return asyncio.timeout(seconds)  # Python 3.11+

def _raise_for_status(r: httpx.Response):
    r.raise_for_status()
    return r

def _retry():
    return retry(
        reraise=True,
        retry=retry_if_exception_type(Retryable),
        stop=stop_after_attempt(int(os.getenv("HTTP_RETRY_ATTEMPTS", "5"))),
        wait=wait_exponential_jitter(initial=1, max=8),
    )

@_retry()
async def get_json(client: httpx.AsyncClient, url: str, **kw):
    async with _as_timeout(float(os.getenv("HTTP_TOTAL_TIMEOUT", "60"))):
        r = await client.get(url, **kw)
        _raise_for_status(r)
        return r.json()

@_retry()
async def get_bytes(client: httpx.AsyncClient, url: str, **kw) -> bytes:
    async with _as_timeout(float(os.getenv("HTTP_TOTAL_TIMEOUT", "120"))):
        r = await client.get(url, **kw)
        _raise_for_status(r)
        return r.content