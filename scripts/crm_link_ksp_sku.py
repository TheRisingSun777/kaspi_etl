"""
Link sales rows to a deterministic final KSP SKU ID per (store_name, sku_key).

Inputs:
- data_crm/processed_sales_20250813.csv
- data_crm/mappings/ksp_sku_map_updated.xlsx
- data_crm/state/ksp_sku_usage.csv (optional; updated by this script)

Outputs:
- data_crm/processed_sales_linked.csv (adds column ksp_sku_id_final)
- data_crm/reports/ksp_link_conflicts.csv (rows where candidates were not found)

Selection rules for a given (store_name, sku_key):
1) If a single candidate exists -> choose it.
2) If multiple candidates exist -> choose the last-used one from state; else the lowest numeric ksp_sku_id; if non-numeric, the lowest lexicographically.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_CRM = REPO_ROOT / "data_crm"
REPORTS_DIR = DATA_CRM / "reports"
STATE_DIR = DATA_CRM / "state"

SALES_INPUT = DATA_CRM / "processed_sales_20250813.csv"
KSP_MAP_XLSX = DATA_CRM / "mappings" / "ksp_sku_map_updated.xlsx"
LINKED_OUTPUT = DATA_CRM / "processed_sales_linked.csv"
CONFLICTS_CSV = REPORTS_DIR / "ksp_link_conflicts.csv"
USAGE_STATE_CSV = STATE_DIR / "ksp_sku_usage.csv"


def _lower_columns_inplace(df: pd.DataFrame) -> None:
    df.columns = [str(c).strip().lower() for c in df.columns]


def _choose_first_existing(df: pd.DataFrame, candidates: Iterable[str]) -> str | None:
    for name in candidates:
        if name in df.columns:
            return name
    return None


def load_sales() -> pd.DataFrame:
    if not SALES_INPUT.exists():
        raise FileNotFoundError(f"Missing sales CSV: {SALES_INPUT}")
    df = pd.read_csv(SALES_INPUT, dtype=str)
    _lower_columns_inplace(df)
    return df


def load_ksp_map() -> pd.DataFrame:
    if not KSP_MAP_XLSX.exists():
        raise FileNotFoundError(f"Missing KSP map: {KSP_MAP_XLSX}")
    df = pd.read_excel(KSP_MAP_XLSX, engine="openpyxl")
    _lower_columns_inplace(df)
    # Heuristic: keep only relevant columns if present
    keep_cols = [c for c in ["store_name", "sku_key", "ksp_sku_id"] if c in df.columns]
    if not keep_cols:
        # Try alternative names
        store_col = _choose_first_existing(df, ["store", "merchant", "shop"])
        sku_col = _choose_first_existing(df, ["sku_key", "sku", "model", "product_key"]) or "sku_key"
        ksp_col = _choose_first_existing(df, ["ksp_sku_id", "sku_id_ksp", "ksp_sku"]) or "ksp_sku_id"
        cols = [c for c in [store_col, sku_col, ksp_col] if c]
    else:
        cols = keep_cols
    df = df[cols].copy()
    # Normalize column names to canonical
    rename_map: dict[str, str] = {}
    for c in df.columns:
        if c in {"store", "merchant", "shop"}:
            rename_map[c] = "store_name"
        if c in {"sku", "model", "product_key"}:
            rename_map[c] = "sku_key"
        if c in {"sku_id_ksp", "ksp_sku"}:
            rename_map[c] = "ksp_sku_id"
    if rename_map:
        df.rename(columns=rename_map, inplace=True)
    # Ensure required columns exist
    for col in ["sku_key", "ksp_sku_id"]:
        if col not in df.columns:
            df[col] = pd.NA
    if "store_name" not in df.columns:
        df["store_name"] = pd.NA
    # Clean
    df["store_name"] = df["store_name"].astype(str).str.strip()
    df["sku_key"] = df["sku_key"].astype(str).str.strip()
    df["ksp_sku_id"] = df["ksp_sku_id"].astype(str).str.strip()
    # Drop rows without ksp_sku_id
    df = df[df["ksp_sku_id"].astype(str).str.strip() != ""].copy()
    return df


def load_usage_state() -> pd.DataFrame:
    if not USAGE_STATE_CSV.exists():
        USAGE_STATE_CSV.parent.mkdir(parents=True, exist_ok=True)
        return pd.DataFrame(columns=["store_name", "sku_key", "ksp_sku_id", "last_used_iso", "usage_count"])
    df = pd.read_csv(USAGE_STATE_CSV, dtype=str)
    _lower_columns_inplace(df)
    if "usage_count" in df.columns:
        try:
            df["usage_count"] = pd.to_numeric(df["usage_count"], errors="coerce").fillna(0).astype(int)
        except Exception:
            df["usage_count"] = 0
    else:
        df["usage_count"] = 0
    for col in ["store_name", "sku_key", "ksp_sku_id", "last_used_iso"]:
        if col not in df.columns:
            df[col] = ""
    return df[["store_name", "sku_key", "ksp_sku_id", "last_used_iso", "usage_count"]]


def save_usage_state(df: pd.DataFrame) -> None:
    USAGE_STATE_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(USAGE_STATE_CSV, index=False)


def build_candidates_map(ksp_map: pd.DataFrame) -> dict[tuple[str, str], list[str]]:
    candidates: dict[tuple[str, str], list[str]] = {}
    # Two levels: with store, and without store (fallback)
    for _, row in ksp_map.iterrows():
        store = str(row.get("store_name", "")).strip()
        sku_key = str(row.get("sku_key", "")).strip()
        ksp_id = str(row.get("ksp_sku_id", "")).strip()
        if not sku_key or not ksp_id:
            continue
        # With store
        key_with_store = (store, sku_key)
        candidates.setdefault(key_with_store, [])
        if ksp_id not in candidates[key_with_store]:
            candidates[key_with_store].append(ksp_id)
        # Fallback key_without_store
        key_without_store = ("", sku_key)
        candidates.setdefault(key_without_store, [])
        if ksp_id not in candidates[key_without_store]:
            candidates[key_without_store].append(ksp_id)
    return candidates


def choose_candidate(store: str, sku_key: str, options: Sequence[str], usage_state: pd.DataFrame) -> tuple[str | None, str]:
    if not options:
        return None, "no_candidates"
    if len(options) == 1:
        return options[0], "single_candidate"

    # Try last-used from state
    mask = (
        (usage_state["store_name"].astype(str) == str(store))
        & (usage_state["sku_key"].astype(str) == str(sku_key))
        & (usage_state["ksp_sku_id"].astype(str).isin(list(options)))
    )
    subset = usage_state.loc[mask].copy()
    if not subset.empty and "last_used_iso" in subset.columns:
        # Parse datetimes (fallback to epoch for invalid)
        def parse_dt(s: str) -> float:
            try:
                return pd.Timestamp(s).timestamp()
            except Exception:
                return 0.0

        subset["_ts"] = subset["last_used_iso"].astype(str).map(parse_dt)
        best_row = subset.sort_values("_ts", ascending=False).iloc[0]
        return str(best_row["ksp_sku_id"]), "last_used"

    # Choose lowest numeric id else lexicographic
    series = pd.Series(list(options))
    as_num = pd.to_numeric(series, errors="coerce")
    if as_num.notna().any():
        # Use numeric only for those parsed; if all NaN, fallback to lexicographic
        best_idx = as_num.idxmin()
    else:
        best_idx = series.sort_values().index[0]
    return str(series.loc[best_idx]), "lowest_id"


def update_usage_state(usage_state: pd.DataFrame, store: str, sku_key: str, ksp_id: str) -> pd.DataFrame:
    now_iso = datetime.now(UTC).isoformat(timespec="seconds")
    key_mask = (
        (usage_state["store_name"].astype(str) == str(store))
        & (usage_state["sku_key"].astype(str) == str(sku_key))
        & (usage_state["ksp_sku_id"].astype(str) == str(ksp_id))
    )
    if key_mask.any():
        usage_state.loc[key_mask, "last_used_iso"] = now_iso
        usage_state.loc[key_mask, "usage_count"] = (
            pd.to_numeric(usage_state.loc[key_mask, "usage_count"], errors="coerce").fillna(0).astype(int) + 1
        )
    else:
        usage_state = pd.concat(
            [
                usage_state,
                pd.DataFrame(
                    [{
                        "store_name": str(store),
                        "sku_key": str(sku_key),
                        "ksp_sku_id": str(ksp_id),
                        "last_used_iso": now_iso,
                        "usage_count": 1,
                    }]
                ),
            ],
            ignore_index=True,
        )
    return usage_state


def main() -> int:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    STATE_DIR.mkdir(parents=True, exist_ok=True)

    sales_df = load_sales()
    ksp_map_df = load_ksp_map()
    usage_state = load_usage_state()

    candidates_map = build_candidates_map(ksp_map_df)

    # Determine result column
    sales_df["ksp_sku_id_final"] = ""

    conflicts: list[dict[str, str]] = []

    # Identify store/sku columns in sales
    store_col = _choose_first_existing(sales_df, ["store_name", "store", "merchant"]) or "store_name"
    sku_col = _choose_first_existing(sales_df, ["sku_key"]) or "sku_key"

    for idx, row in sales_df.iterrows():
        store = str(row.get(store_col, "")).strip()
        sku_key = str(row.get(sku_col, "")).strip()

        options = candidates_map.get((store, sku_key))
        if not options:
            options = candidates_map.get(("", sku_key), [])

        chosen, reason = choose_candidate(store, sku_key, options, usage_state)
        if chosen is None:
            conflicts.append(
                {
                    "orderid": str(row.get("orderid", "")),
                    "store_name": store,
                    "sku_key": sku_key,
                    "my_size": str(row.get("my_size", "")),
                    "candidates": ";".join(options) if options else "",
                    "reason": reason,
                }
            )
            continue

        sales_df.at[idx, "ksp_sku_id_final"] = chosen
        usage_state = update_usage_state(usage_state, store, sku_key, chosen)

    # Save outputs
    LINKED_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    sales_df.to_csv(LINKED_OUTPUT, index=False)

    conflicts_df = pd.DataFrame(conflicts, columns=["orderid", "store_name", "sku_key", "my_size", "candidates", "reason"]) if conflicts else pd.DataFrame(columns=["orderid", "store_name", "sku_key", "my_size", "candidates", "reason"])
    conflicts_df.to_csv(CONFLICTS_CSV, index=False)

    save_usage_state(usage_state)

    print(f"Linked sales written: {LINKED_OUTPUT}")
    print(f"Conflicts report written: {CONFLICTS_CSV} (rows: {len(conflicts_df)})")
    print(f"Usage state updated: {USAGE_STATE_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


