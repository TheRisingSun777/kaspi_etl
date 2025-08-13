#!/usr/bin/env python3

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception


# Load environment (.env.local preferred, then .env)
load_dotenv(".env.local", override=False)
load_dotenv(override=False)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def _get_env(name: str, default: Optional[str] = None) -> str:
    val = os.getenv(name)
    return val if val is not None else (default or "")


@dataclass
class WABAApiError(Exception):
    message: str
    status_code: int
    error_code: Optional[int] = None
    error_subcode: Optional[int] = None
    error_title: Optional[str] = None
    response_text: Optional[str] = None

    def __str__(self) -> str:  # pragma: no cover
        parts = [f"HTTP {self.status_code}", self.message]
        if self.error_code is not None:
            parts.append(f"code={self.error_code}")
        if self.error_subcode is not None:
            parts.append(f"subcode={self.error_subcode}")
        if self.error_title:
            parts.append(f"title={self.error_title}")
        return "; ".join(parts)


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, httpx.TimeoutException):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        sc = exc.response.status_code
        return sc == 429 or 500 <= sc < 600
    if isinstance(exc, WABAApiError):
        if exc.status_code == 429:
            return True
        # Graph API code 4 is 'Application request limit reached'
        if exc.error_code in {4}:
            return True
        return 500 <= exc.status_code < 600
    return False


class WABAClient:
    def __init__(self, api_base: str, token: str, phone_number_id: str) -> None:
        self.api_base = api_base.rstrip("/")
        self.token = token
        self.phone_number_id = phone_number_id

    @classmethod
    def from_env(cls) -> "WABAClient":
        api_base = _get_env("WA_API_BASE", "https://graph.facebook.com/v19.0")
        token = _get_env("WA_TOKEN")
        phone_number_id = _get_env("WA_PHONE_NUMBER_ID")
        return cls(api_base=api_base, token=token, phone_number_id=phone_number_id)

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
        }

    @retry(retry=retry_if_exception(_is_retryable), wait=wait_exponential(multiplier=1, min=1, max=30), stop=stop_after_attempt(5), reraise=True)
    def _request_json(self, method: str, path: str, *, json_body: Optional[dict] = None, files: Any = None, data: Any = None, timeout: float = 60.0) -> Dict[str, Any]:
        if not self.token:
            raise WABAApiError("Missing WA_TOKEN in environment", status_code=401)
        url = f"{self.api_base}{path}"
        logger.info("WABA %s %s", method, path)
        try:
            with httpx.Client(timeout=httpx.Timeout(timeout)) as client:
                resp = client.request(method, url, headers=self._headers(), json=json_body, files=files, data=data)
                if 200 <= resp.status_code < 300:
                    try:
                        return resp.json()
                    except Exception:
                        return {"ok": True, "status_code": resp.status_code, "text": resp.text}
                else:
                    try:
                        err = resp.json().get("error", {})
                    except Exception:
                        err = {}
                    raise WABAApiError(
                        message=str(err.get("message", "WABA error")),
                        status_code=resp.status_code,
                        error_code=err.get("code"),
                        error_subcode=err.get("error_subcode"),
                        error_title=(err.get("error_user_title") or err.get("type")),
                        response_text=resp.text,
                    )
        except httpx.HTTPStatusError as exc:  # pragma: no cover
            raise WABAApiError(message=str(exc), status_code=exc.response.status_code, response_text=exc.response.text)

    # Public API --------------------------------------------------------------
    def send_template(self, to: str, name: str, lang: str = "ru", components: Optional[list] = None) -> Dict[str, Any]:
        body: Dict[str, Any] = {
            "messaging_product": "whatsapp",
            "to": str(to),
            "type": "template",
            "template": {
                "name": name,
                "language": {"code": lang},
            },
        }
        if components:
            body["template"]["components"] = components
        return self._request_json("POST", f"/{self.phone_number_id}/messages", json_body=body)

    def upload_media(self, path: str | Path, mime: str = "application/pdf") -> str:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(str(p))
        files = {"file": (p.name, p.open("rb"), mime)}
        data = {"messaging_product": "whatsapp"}
        resp = self._request_json("POST", f"/{self.phone_number_id}/media", files=files, data=data)
        media_id = resp.get("id")
        if not media_id:
            raise WABAApiError("No media id in response", status_code=500, response_text=json.dumps(resp))
        return media_id

    def send_document(self, to: str, media_id: Optional[str] = None, link: Optional[str] = None, filename: Optional[str] = None, caption: Optional[str] = None) -> Dict[str, Any]:
        doc: Dict[str, Any] = {}
        if media_id:
            doc["id"] = media_id
        elif link:
            doc["link"] = link
        else:
            raise ValueError("send_document requires media_id or link")
        if filename:
            doc["filename"] = filename
        if caption:
            doc["caption"] = caption
        body = {
            "messaging_product": "whatsapp",
            "to": str(to),
            "type": "document",
            "document": doc,
        }
        return self._request_json("POST", f"/{self.phone_number_id}/messages", json_body=body)

    def send_text(self, to: str, text: str) -> Dict[str, Any]:
        body = {
            "messaging_product": "whatsapp",
            "to": str(to),
            "type": "text",
            "text": {"body": str(text), "preview_url": False},
        }
        return self._request_json("POST", f"/{self.phone_number_id}/messages", json_body=body)


# Convenience module-level helpers -------------------------------------------
_default_client: Optional[WABAClient] = None


def _get_client() -> WABAClient:
    global _default_client
    if _default_client is None:
        _default_client = WABAClient.from_env()
    return _default_client


def send_template(to: str, name: str, lang: str = "ru", components: Optional[list] = None) -> Dict[str, Any]:
    return _get_client().send_template(to=to, name=name, lang=lang, components=components)


def upload_media(path: str | Path, mime: str = "application/pdf") -> str:
    return _get_client().upload_media(path=path, mime=mime)


def send_document(to: str, media_id: Optional[str] = None, link: Optional[str] = None, filename: Optional[str] = None, caption: Optional[str] = None) -> Dict[str, Any]:
    return _get_client().send_document(to=to, media_id=media_id, link=link, filename=filename, caption=caption)


def send_text(to: str, text: str) -> Dict[str, Any]:
    return _get_client().send_text(to=to, text=text)


# Error helpers ---------------------------------------------------------------
def is_session_window_error(exc: Exception) -> bool:
    if isinstance(exc, WABAApiError):
        # Common session window errors: HTTP 400 with code 470; sometimes subcodes like 2018065
        if exc.error_code in {470}:
            return True
        if exc.error_subcode in {2018065, 2018007}:
            return True
    return False


