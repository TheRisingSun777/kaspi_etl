"""
Configuration loader for the backend package.

Reads `docs/protocol/CONFIG.yaml`, normalises environment variables, and exposes
typed accessors for downstream modules (e.g., database session factory).
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional, Sequence, Union, Any

import os

import yaml

ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = ROOT_DIR / "docs/protocol/CONFIG.yaml"


def _expand_env(value: Any) -> Any:
    """Recursively expand environment variables inside CONFIG values."""
    if isinstance(value, str):
        return os.path.expandvars(value)
    if isinstance(value, list):
        return [_expand_env(item) for item in value]
    if isinstance(value, dict):
        return {key: _expand_env(val) for key, val in value.items()}
    return value


@dataclass(frozen=True)
class AppSettings:
    timezone: str
    outbox_dir: str
    backups_dir: str


@dataclass(frozen=True)
class DBSettings:
    driver: str
    uri: str


@dataclass(frozen=True)
class KaspiAccountConfig:
    name: str
    account_id: str
    auth: str


@dataclass(frozen=True)
class KaspiSettings:
    accounts: Sequence[KaspiAccountConfig]
    poll_interval_min: int


@dataclass(frozen=True)
class WhatsAppSettings:
    provider: str
    from_number: str
    webhook_secret: str


@dataclass(frozen=True)
class PolicySettings:
    L_days: int
    R_days: int
    B_days: int
    z_service: float
    tv_floor: float
    vat_pct: float
    platform_pct: float
    delivery_blend_city: float
    delivery_blend_country: float


@dataclass(frozen=True)
class PathsSettings:
    xlsx_sku_map: str
    xlsx_sales: str
    xlsx_demand: str
    xlsx_delivery_bands: str
    xlsx_catalog: str


@dataclass(frozen=True)
class FeatureFlags:
    enable_flow_A_orders_whatsapp: bool
    enable_flow_B_inventory_oos: bool


@dataclass(frozen=True)
class AppConfig:
    app: AppSettings
    db: DBSettings
    kaspi: KaspiSettings
    whatsapp: WhatsAppSettings
    policy: PolicySettings
    paths: PathsSettings
    feature_flags: FeatureFlags


@lru_cache(maxsize=1)
def load_config(path: Optional[Union[str, Path]] = None) -> AppConfig:
    """
    Load the configuration file and convert it into typed objects.

    Parameters
    ----------
    path: Optional path override; defaults to docs/protocol/CONFIG.yaml.
    """
    cfg_path = Path(path) if path else DEFAULT_CONFIG_PATH
    if not cfg_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {cfg_path}")

    with cfg_path.open("r", encoding="utf-8") as fh:
        raw_data: Dict[str, Any] = yaml.safe_load(fh) or {}

    expanded = _expand_env(raw_data)

    app_cfg = AppSettings(**expanded["app"])
    db_cfg = DBSettings(**expanded["db"])
    kaspi_accounts = [
        KaspiAccountConfig(**acct) for acct in expanded["kaspi"].get("accounts", [])
    ]
    kaspi_cfg = KaspiSettings(
        accounts=kaspi_accounts, poll_interval_min=expanded["kaspi"]["poll_interval_min"]
    )
    whatsapp_cfg = WhatsAppSettings(**expanded["whatsapp"])
    policy_cfg = PolicySettings(**expanded["policy"])
    paths_cfg = PathsSettings(**expanded["paths"])
    feature_flags_cfg = FeatureFlags(**expanded["feature_flags"])

    return AppConfig(
        app=app_cfg,
        db=db_cfg,
        kaspi=kaspi_cfg,
        whatsapp=whatsapp_cfg,
        policy=policy_cfg,
        paths=paths_cfg,
        feature_flags=feature_flags_cfg,
    )


__all__ = [
    "AppConfig",
    "AppSettings",
    "DBSettings",
    "FeatureFlags",
    "KaspiSettings",
    "KaspiAccountConfig",
    "PathsSettings",
    "PolicySettings",
    "WhatsAppSettings",
    "load_config",
]
