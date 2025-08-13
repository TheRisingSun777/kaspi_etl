#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import zipfile
from pathlib import Path

from crm_config import REPO_ROOT, load_crm_config


def cmd_setup(args: argparse.Namespace) -> int:
    # Placeholder: could copy templates or verify mappings exist
    cfg = load_crm_config()
    print("CRM setup: config loaded with keys:", list(cfg.keys()))
    return 0


def cmd_process_sales(args: argparse.Namespace) -> int:
    import sys
    sys.path.append(str(REPO_ROOT))
    from scripts.crm_process_sales import main as process_main

    return process_main()


def cmd_reports(args: argparse.Namespace) -> int:
    reports = []
    for p in [
        REPO_ROOT / "data_crm" / "missing_skus.csv",
        REPO_ROOT / "data_crm" / "reports" / f"duplicates_{args.run_date}.csv",
        REPO_ROOT / "data_crm" / "reports" / f"oversell_{args.run_date}.csv",
    ]:
        if p.exists():
            reports.append(p)
    for p in reports:
        print("Report:", p)
    return 0


def cmd_snapshot(args: argparse.Namespace) -> int:
    out_dir = REPO_ROOT / "assistant_bundles"
    out_dir.mkdir(parents=True, exist_ok=True)
    bundle = out_dir / f"crm_snapshot_{args.run_date}.zip"
    with zipfile.ZipFile(bundle, 'w', zipfile.ZIP_DEFLATED) as z:
        for rel in [
            "data_crm/processed_sales_latest.csv",
            f"data_crm/processed/processed_sales_{args.run_date}.csv",
            "data_crm/stock_on_hand_updated.csv",
            f"data_crm/stock/stock_on_hand_updated_{args.run_date}.csv",
            f"data_crm/reports/duplicates_{args.run_date}.csv",
            f"data_crm/reports/oversell_{args.run_date}.csv",
            f"data_crm/missing_skus_{args.run_date}.csv",
            "data_crm/missing_skus.csv",
        ]:
            p = REPO_ROOT / rel
            if p.exists():
                z.write(p, arcname=str(p.relative_to(REPO_ROOT)))
    print("Snapshot written:", bundle)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="CRM CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("setup", help="phase1 setup/mapping")
    p1.set_defaults(func=cmd_setup)

    p2 = sub.add_parser("process-sales", help="run sales processing")
    p2.set_defaults(func=cmd_process_sales)

    p3 = sub.add_parser("reports", help="list key reports")
    p3.add_argument("--run-date", default=Path.cwd().name.replace('-', ''), dest="run_date")
    p3.set_defaults(func=cmd_reports)

    p4 = sub.add_parser("snapshot", help="zip outputs")
    p4.add_argument("--run-date", default=Path.cwd().name.replace('-', ''), dest="run_date")
    p4.set_defaults(func=cmd_snapshot)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())


