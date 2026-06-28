from __future__ import annotations

import csv
import sys
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[1]
ASSET_CLASSES = ["a股", "港股", "美股", "贵金属", "加密货币"]
REQUIRED_ASSET_PATHS = [
    "README.md",
    "thesis.md",
    "valuation.md",
    "observation_log.md",
    "financials/financials.csv",
    "kline/daily.csv",
    "news/related_news.md",
    "news/related_news.csv",
    "raw/source_index.json",
]


def count_asset_dirs(asset_class: str) -> int:
    root = WORKSPACE / "assets" / asset_class
    if not root.exists():
        return 0
    return sum(1 for path in root.iterdir() if path.is_dir())


def count_csv_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return sum(1 for _ in csv.DictReader(file))


def a_share_asset_dirs() -> list[Path]:
    root = WORKSPACE / "assets" / "a股"
    if not root.exists():
        return []
    return sorted(path for path in root.iterdir() if path.is_dir() and path.name[:6].isdigit())


def missing_required_files() -> list[tuple[Path, str]]:
    missing: list[tuple[Path, str]] = []
    for asset_dir in a_share_asset_dirs():
        for relative in REQUIRED_ASSET_PATHS:
            if not (asset_dir / relative).exists():
                missing.append((asset_dir, relative))
    return missing


def print_report(missing: list[tuple[Path, str]]) -> None:
    print("asset_counts:")
    for asset_class in ASSET_CLASSES:
        print(f"  {asset_class}: {count_asset_dirs(asset_class)}")
    print("portfolio:")
    print(f"  transactions: {count_csv_rows(WORKSPACE / 'portfolio' / 'transactions.csv')}")
    print(f"  positions: {count_csv_rows(WORKSPACE / 'portfolio' / 'positions.csv')}")
    print("news:")
    print(f"  rows: {count_csv_rows(WORKSPACE / 'news' / 'news_index.csv')}")
    print(f"missing_required_files: {len(missing)}")
    for asset_dir, relative in missing[:20]:
        print(f"  - {asset_dir.relative_to(WORKSPACE)} missing {relative}")


def main() -> int:
    missing = missing_required_files()
    print_report(missing)
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
