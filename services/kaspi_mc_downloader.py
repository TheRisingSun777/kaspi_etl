#!/usr/bin/env python3

from __future__ import annotations

import datetime as dt
import logging
import os
import re
import shutil
from pathlib import Path
from typing import Dict, Optional

import requests
from dotenv import load_dotenv
from tqdm import tqdm


load_dotenv(".env.local", override=False)
load_dotenv(override=False)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_CRM = REPO_ROOT / "data_crm"


def get_mc_cookie_header(prefer_browser: bool = True) -> str:
    """Build Cookie header string from browser or env fallback.

    Tries Chrome → Brave → Edge → Firefox via browser_cookie3 for domains:
    - mc.shop.kaspi.kz, kaspi.kz
    Fallback to env KASPI_MERCHANT_COOKIE if present.
    """
    if prefer_browser:
        try:
            import browser_cookie3 as bc

            extractors = [
                getattr(bc, "chrome", None),
                getattr(bc, "brave", None),
                getattr(bc, "edge", None),
                getattr(bc, "firefox", None),
            ]
            domains = ["mc.shop.kaspi.kz", "kaspi.kz"]
            jar = None
            for extractor in extractors:
                if extractor is None:
                    continue
                try:
                    jar = extractor(domain_name="kaspi.kz")  # broad domain filter
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

    env_cookie = (os.getenv("KASPI_MERCHANT_COOKIE") or "").strip()
    if env_cookie:
        return env_cookie

    raise RuntimeError("Login to mc.shop.kaspi.kz in Chrome and rerun (no cookies found)")


def _atomic_write_download(url: str, out_path: Path, headers: Optional[Dict[str, str]], timeout: int) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = out_path.with_suffix(out_path.suffix + ".tmp")
    with requests.get(url, headers=headers, stream=True, timeout=timeout) as r:
        r.raise_for_status()
        # Filename from Content-Disposition if present
        cd = r.headers.get("Content-Disposition") or r.headers.get("content-disposition")
        final_path = out_path
        if cd:
            m = re.search(r'filename\*=UTF-8\''([^']+)'|filename="([^"]+)"', cd)
            if m:
                fname = m.group(1) or m.group(2)
                if fname:
                    final_path = out_path.parent / fname
        total = int(r.headers.get("Content-Length", 0))
        bar = tqdm(total=total if total > 0 else None, unit="B", unit_scale=True, desc=final_path.name)
        with open(tmp_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    if total > 0:
                        bar.update(len(chunk))
        bar.close()
    shutil.move(str(tmp_path), str(final_path))
    return final_path


def http_download(url: str, out_path: str | Path, headers: Optional[Dict[str, str]] = None, timeout: int = 60) -> Path:
    p = Path(out_path)
    return _atomic_write_download(url, p, headers, timeout)


def _date_folder(base: Path, out_dir: Optional[str]) -> Path:
    stamp = dt.date.today().strftime("%Y-%m-%d")
    root = base if out_dir is None else Path(out_dir)
    folder = root / stamp
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def download_waybills(url: str, out_dir: str | Path = "data_crm/inbox/waybills") -> Path:
    folder = _date_folder(Path(out_dir), None)
    cookie = get_mc_cookie_header(prefer_browser=True)
    headers = {"Cookie": cookie, "Accept": "*/*"}
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    target = folder / f"waybill-{ts}.zip"
    final = http_download(url, target, headers=headers, timeout=180)
    logger.info("Downloaded waybills to %s (%d bytes)", final, final.stat().st_size if final.exists() else -1)
    return final


def download_active_orders(url: str, out_dir: str | Path = "data_crm/inbox/orders") -> Path:
    folder = _date_folder(Path(out_dir), None)
    cookie = get_mc_cookie_header(prefer_browser=True)
    headers = {"Cookie": cookie, "Accept": "*/*"}
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    target = folder / f"ActiveOrders_{ts}.xlsx"
    final = http_download(url, target, headers=headers, timeout=180)
    logger.info("Downloaded ActiveOrders to %s (%d bytes)", final, final.stat().st_size if final.exists() else -1)
    return final


