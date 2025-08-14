#!/usr/bin/env python3

from __future__ import annotations

import datetime as dt
import logging
import os
import random
import re
import shutil
import time
from pathlib import Path
from typing import Dict, Optional

import requests
from dotenv import load_dotenv
from tqdm import tqdm
from urllib.parse import unquote


load_dotenv(".env.local", override=False)
load_dotenv(override=False)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

from settings.paths import DATA_CRM


def _cookie_header_from_json_text(text: str) -> Optional[str]:
    try:
        data = None
        if text.strip().startswith("["):
            data = __import__("json").loads(text)
        elif text.strip().startswith("{"):
            data = [__import__("json").loads(text)]
        else:
            return None
        parts = []
        for item in data:
            name = item.get("name")
            value = item.get("value")
            if name and value:
                parts.append(f"{name}={value}")
        if parts:
            return "; ".join(parts)
    except Exception:
        return None
    return None


def build_cookie() -> str:
    """Try to build Cookie header from Chrome/Brave/Edge/Firefox for mc.shop.kaspi.kz.

    Fallback to env KASPI_MERCHANT_COOKIE (quotes stripped). Else raise a friendly error.
    """
    # 1) Try browser_cookie3
    try:
        import browser_cookie3 as bc

        extractors = [getattr(bc, "chrome", None), getattr(bc, "brave", None), getattr(bc, "edge", None), getattr(bc, "firefox", None)]
        domains = ["mc.shop.kaspi.kz"]
        jar = None
        for extractor in extractors:
            if extractor is None:
                continue
            try:
                jar = extractor(domain_name="mc.shop.kaspi.kz")
                if jar and len(jar) > 0:
                    break
            except Exception:
                continue
        if jar and len(jar) > 0:
            parts = []
            for c in jar:
                if any(d in c.domain for d in domains):
                    parts.append(f"{c.name}={c.value}")
            if parts:
                cookie_header = "; ".join(sorted(set(parts)))
                if cookie_header:
                    return cookie_header
    except Exception:
        pass

    # 2) Try saved cookie jar JSON
    saved_path = DATA_CRM / "state" / "mc_cookies.json"
    if saved_path.exists():
        text = saved_path.read_text(encoding="utf-8").strip()
        if text:
            from_json = _cookie_header_from_json_text(text)
            if from_json:
                return from_json
            return text

    # 3) Env fallback
    raw = (os.getenv("KASPI_MERCHANT_COOKIE") or "").strip().strip('"').strip("'")
    if raw:
        return raw

    raise RuntimeError(
        "No Merchant Cabinet cookies found. Login to mc.shop.kaspi.kz in Chrome, or run `make mc-cookie`, or set KASPI_MERCHANT_COOKIE in .env.local"
    )


def build_headers(cookie: str) -> Dict[str, str]:
    base = os.getenv("KASPI_MERCHANT_API_BASE", "https://mc.shop.kaspi.kz").strip().strip('"').strip("'")
    merchant_id = os.getenv("KASPI_MERCHANT_ID", "").strip().strip('"').strip("'")
    referer = f"{base}/mc/#/orders?status=KASPI_DELIVERY_WAIT_FOR_COURIER&_m={merchant_id}"
    return {
        "User-Agent": os.getenv(
            "MC_USER_AGENT",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36",
        ),
        "Accept": "*/*",
        "Accept-Language": "ru,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Referer": referer,
        "X-Requested-With": "XMLHttpRequest",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Cookie": cookie,
    }


def _atomic_write_stream(response: requests.Response, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = out_path.with_suffix(out_path.suffix + ".tmp")
    # Filename from Content-Disposition if present
    cd = response.headers.get("Content-Disposition") or response.headers.get("content-disposition") or ""
    final_path = out_path
    if cd:
        m = re.search(r"filename\*=UTF-8''([^;]+)", cd, flags=re.IGNORECASE)
        if not m:
            m = re.search(r"filename=\"?([^\";]+)\"?", cd)
        if m:
            fname = unquote(m.group(1)).strip()
            if fname:
                final_path = out_path.parent / Path(fname).name
    total = int(response.headers.get("Content-Length", 0) or 0)
    bar = tqdm(total=total if total > 0 else None, unit="B", unit_scale=True, desc=final_path.name)
    with open(tmp_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
                bar.update(len(chunk))
    bar.close()
    shutil.move(str(tmp_path), str(final_path))
    return final_path


def http_download(url: str, out_path: str | Path, timeout: int = 120) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    p = Path(out_path)
    sess = requests.Session()
    headers = build_headers(build_cookie())
    last_exc: Optional[Exception] = None
    for attempt in range(1, 8):
        logger.info("download attempt %d GET %s", attempt, url)
        try:
            r = sess.get(url, headers=headers, timeout=timeout, stream=True, allow_redirects=True)
            if r.status_code == 200:
                return _atomic_write_stream(r, p)
            if r.status_code in (401, 403):
                logger.error("attempt %d: auth error %d; abort", attempt, r.status_code)
                raise RuntimeError("Auth error (401/403). Refresh your login (make mc-cookie) or update KASPI_MERCHANT_COOKIE.")
            if r.status_code == 429:
                ra = r.headers.get("Retry-After") or "4"
                try:
                    ra_int = int(float(ra))
                except Exception:
                    ra_int = 4
                sleep_s = min(60, ra_int) + random.uniform(1, 3) + attempt
                logger.warning("attempt %d: 429 too many requests, retry-after=%ss, backoff=%.1fs", attempt, ra_int, sleep_s)
                time.sleep(sleep_s)
                continue
            # other errors
            wait = min(30, (2 ** attempt) + random.uniform(0, 1))
            logger.info("attempt %d: status %d, retry in %.1fs", attempt, r.status_code, wait)
            time.sleep(wait)
        except Exception as e:
            last_exc = e
            wait = min(30, (2 ** attempt) + random.uniform(0, 1))
            logger.info("attempt %d: error %s, retry in %.1fs", attempt, e.__class__.__name__, wait)
            time.sleep(wait)

    # Fallback to Playwright headless download
    try:
        logger.info("playwright-fallback: %s", url)
        return browser_download(url, p)
    except Exception as e:
        if last_exc:
            raise last_exc
        raise e


def browser_download(url: str, out_path: str | Path) -> Path:
    from playwright.sync_api import sync_playwright
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Load cookies from browser_cookie3
    cookies = []
    try:
        import browser_cookie3 as bc

        jar = None
        for extractor in [getattr(bc, "chrome", None), getattr(bc, "brave", None), getattr(bc, "edge", None), getattr(bc, "firefox", None)]:
            if extractor is None:
                continue
            try:
                jar = extractor(domain_name="mc.shop.kaspi.kz")
                if jar and len(jar) > 0:
                    break
            except Exception:
                continue
        if jar:
            for c in jar:
                if "mc.shop.kaspi.kz" in c.domain:
                    cookies.append({
                        "name": c.name,
                        "value": c.value,
                        "domain": c.domain,
                        "path": c.path,
                    })
    except Exception:
        pass

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(accept_downloads=True)
        if cookies:
            try:
                ctx.add_cookies(cookies)  # type: ignore[arg-type]
            except Exception:
                pass
        page = ctx.new_page()
        referer = os.getenv("KASPI_MERCHANT_API_BASE", "https://mc.shop.kaspi.kz").strip().strip('"').strip("'") + "/mc/#/orders"
        page.goto(referer, wait_until="load")
        with page.expect_download() as dl_info:
            page.goto(str(url))
        dl = dl_info.value
        dl.save_as(str(out_path))
        ctx.close()
        browser.close()
    return out_path


def _date_folder(base: Path, out_dir: Optional[str]) -> Path:
    stamp = dt.date.today().strftime("%Y-%m-%d")
    root = base if out_dir is None else Path(out_dir)
    folder = root / stamp
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def download_waybills(url: str, out_dir: str | Path = "data_crm/inbox/waybills") -> Path:
    folder = _date_folder(Path(out_dir), None)
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    target = folder / f"waybill-{ts}.zip"
    final = http_download(url, target, timeout=180)
    logger.info("Downloaded waybills to %s (%d bytes)", final, final.stat().st_size if final.exists() else -1)
    return final


def download_active_orders(url: str, out_dir: str | Path = "data_crm/inbox/orders") -> Path:
    folder = _date_folder(Path(out_dir), None)
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    target = folder / f"ActiveOrders_{ts}.xlsx"
    final = http_download(url, target, timeout=180)
    logger.info("Downloaded ActiveOrders to %s (%d bytes)", final, final.stat().st_size if final.exists() else -1)
    return final


