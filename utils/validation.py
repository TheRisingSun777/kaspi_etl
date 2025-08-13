from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
from pydantic import BaseModel


class SchemaRule(BaseModel):
    name: str
    required_columns: List[str]
    dtype_hints: Dict[str, str] = {}
    fatal_missing: Optional[List[str]] = None


DEFAULT_RULES: Dict[str, SchemaRule] = {
    "sales": SchemaRule(
        name="sales",
        required_columns=["sku_key"],
        dtype_hints={"qty": "int"},
    ),
    "stock": SchemaRule(
        name="stock",
        required_columns=["sku_key"],
    ),
    "sku_map": SchemaRule(
        name="sku_map",
        required_columns=["sku_id"],
    ),
}


def validate_df(name: str, df: pd.DataFrame, rule: SchemaRule, run_date: str, reports_dir: Path) -> pd.DataFrame:
    """Validate a DataFrame against a schema rule.

    Returns a DataFrame of issues with columns: column, issue, detail.
    Also writes reports_dir/{name}_validation_{RUN_DATE}.csv
    """
    issues: List[Dict[str, str]] = []  # type: ignore[name-defined]
    # Normalize columns
    cols = [str(c).strip().lower() for c in df.columns]
    df.columns = cols

    # Missing required
    fatal_set = set(rule.fatal_missing or rule.required_columns)
    for req in rule.required_columns:
        if req not in df.columns:
            issues.append({"column": req, "issue": "missing_required", "detail": ""})

    # Dtype hints (soft check)
    for col, hint in (rule.dtype_hints or {}).items():
        if col in df.columns:
            if hint in {"int", "integer"}:
                try:
                    pd.to_numeric(df[col], errors="raise")
                except Exception:
                    issues.append({"column": col, "issue": "invalid_numeric", "detail": "expected int"})

    out = pd.DataFrame(issues, columns=["column", "issue", "detail"]) if issues else pd.DataFrame(columns=["column", "issue", "detail"]) 

    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / f"{name}_validation_{run_date}.csv"
    out.to_csv(path, index=False)

    # Fail fast if any fatal missing
    missing_fatal = [i for i in issues if i["issue"] == "missing_required" and i["column"] in fatal_set]
    if missing_fatal:
        missing_cols = ", ".join(i["column"] for i in missing_fatal)
        raise ValueError(f"Validation failed for {name}: missing columns: {missing_cols}")

    return out


