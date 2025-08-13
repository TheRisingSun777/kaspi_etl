"""
Generate WhatsApp outbox messages for size check (dry-run).

Reads data_crm/processed_sales_20250813.csv and finds rows with missing
customer_height or customer_weight or blank my_size. Renders
templates/whatsapp_size_check.txt per row and writes individual .txt files
under outbox/whatsapp/YYYY-MM-DD/. Also writes a combined CSV
outbox/whatsapp/whatsapp_messages.csv with columns:
orderid, phone, store_name, sku_key, my_size, message_path

No external API calls.
Run:
  ./venv/bin/python scripts/crm_whatsapp_outbox.py
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_CRM = REPO_ROOT / "data_crm"
CSV_INPUT = DATA_CRM / "processed_sales_20250813.csv"
TEMPLATE_PATH = REPO_ROOT / "templates" / "whatsapp_size_check.txt"
OUTBOX_DIR = REPO_ROOT / "outbox" / "whatsapp"


def load_template(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Missing template: {path}")
    return path.read_text(encoding="utf-8")


def choose_first_name(name: str | None) -> str:
    if not name:
        return ""
    parts = str(name).strip().split()
    return parts[0] if parts else ""


def build_message(row: pd.Series, template: str) -> str:
    context: dict[str, str] = {
        "first_name": choose_first_name(row.get("customer_name") if "customer_name" in row else None),
        "product_name": str(row.get("sku_key", "")).replace("_", " "),
        "store_name": str(row.get("store_name", "")),
        "orderid": str(row.get("orderid", "")),
    }
    try:
        return template.format(**context)
    except Exception:
        return template


def main() -> int:
    df = pd.read_csv(CSV_INPUT)
    df.columns = [c.strip().lower() for c in df.columns]

    # Determine missing info rows
    height_missing = df.get("customer_height")
    weight_missing = df.get("customer_weight")
    size_missing = df.get("my_size")

    def is_blank_series(s: pd.Series | None) -> pd.Series:
        if s is None:
            return pd.Series([True] * len(df))
        return s.isna() | (s.astype(str).str.strip() == "")

    need_info_mask = is_blank_series(height_missing) | is_blank_series(weight_missing) | is_blank_series(size_missing)
    candidates = df[need_info_mask].copy()

    template = load_template(TEMPLATE_PATH)

    day_dir = OUTBOX_DIR / datetime.now().strftime("%Y-%m-%d")
    day_dir.mkdir(parents=True, exist_ok=True)

    out_rows = []
    # Read existing outbox CSV for dedupe by (orderid, template)
    out_csv = OUTBOX_DIR / "whatsapp_messages.csv"
    existing_keys = set()
    if out_csv.exists():
        try:
            existing_df = pd.read_csv(out_csv)
            existing_df.columns = [c.strip().lower() for c in existing_df.columns]
            if {"orderid", "template"}.issubset(existing_df.columns):
                existing_keys = set(zip(existing_df["orderid"].astype(str), existing_df["template"].astype(str), strict=False))
        except Exception:
            existing_keys = set()

    template_name = TEMPLATE_PATH.name

    for _, row in candidates.iterrows():
        orderid = str(row.get("orderid", ""))
        phone = str(row.get("phone", "")) if "phone" in row else ""
        sku_key = str(row.get("sku_key", ""))
        my_size = str(row.get("my_size", ""))
        message_text = build_message(row, template)

        # Dedupe by (orderid, template)
        if (orderid, template_name) in existing_keys:
            continue

        filename = f"{orderid or 'no-order'}_{sku_key or 'sku'}_size_check.txt"
        safe_filename = filename.replace("/", "-")
        msg_path = day_dir / safe_filename
        msg_path.write_text(message_text, encoding="utf-8")

        out_rows.append({
            "orderid": orderid,
            "phone": phone,
            "store_name": str(row.get("store_name", "")),
            "sku_key": sku_key,
            "my_size": my_size,
            "message_path": str(msg_path.relative_to(REPO_ROOT)),
        })

    # Append to outbox CSV (create header if not exists)
    OUTBOX_DIR.mkdir(parents=True, exist_ok=True)
    write_header = not out_csv.exists()
    with out_csv.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["orderid", "phone", "store_name", "sku_key", "my_size", "message_path", "template"])
        if write_header:
            writer.writeheader()
        for r in out_rows:
            r["template"] = template_name
            writer.writerow(r)

    print(f"Generated {len(out_rows)} WhatsApp messages in {day_dir}")
    print(f"Outbox CSV updated: {out_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


