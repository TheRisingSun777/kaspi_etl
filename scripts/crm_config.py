from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

import yaml
from dotenv import load_dotenv


REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / "config" / "crm.yml"


def load_env() -> None:
    # Load .env then .env.local (allow local overrides)
    load_dotenv(REPO_ROOT / ".env")
    load_dotenv(REPO_ROOT / ".env.local", override=True)


def load_crm_config() -> Dict[str, Any]:
    load_env()
    config: Dict[str, Any] = {}
    if CONFIG_PATH.exists():
        with CONFIG_PATH.open("r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
    return config


def get_run_date(default: str) -> str:
    # Allow RUN_DATE override from env
    return os.environ.get("RUN_DATE", default)


