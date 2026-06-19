"""Download arbitrary histdata.com M1 FX pairs (for cross-asset tests)."""

from __future__ import annotations

import argparse
import os
import time
import zipfile
from pathlib import Path

from histdata import download_hist_data as dl
from histdata.api import Platform as P, TimeFrame as TF

DATA_DIR = Path(__file__).resolve().parent


def download_pair_year(pair: str, year: int, retries: int = 5) -> Path | None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    up = pair.upper()
    zip_path = DATA_DIR / f"DAT_ASCII_{up}_M1_{year}.zip"
    csv_path = DATA_DIR / f"DAT_ASCII_{up}_M1_{year}.csv"
    if csv_path.exists():
        print(f"skip {pair} {year} (csv exists)")
        return csv_path

    for attempt in range(1, retries + 1):
        try:
            print(f"downloading {pair} {year} (attempt {attempt})")
            cwd = Path.cwd()
            try:
                os.chdir(DATA_DIR)
                dl(year=str(year), month=None, pair=pair.lower(),
                   platform=P.GENERIC_ASCII, time_frame=TF.ONE_MINUTE)
            finally:
                os.chdir(cwd)
            if zip_path.exists():
                with zipfile.ZipFile(zip_path) as zf:
                    zf.extractall(DATA_DIR)
                print(f"extracted {csv_path.name}")
                return csv_path
        except Exception as exc:
            print(f"error {pair} {year}: {exc}")
            time.sleep(5 * attempt)
    print(f"FAILED {pair} {year}")
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", nargs="+", required=True,
                        help="e.g. eurusd usdjpy gbpusd")
    parser.add_argument("--start", type=int, default=2018)
    parser.add_argument("--end", type=int, default=2025)
    args = parser.parse_args()

    for pair in args.pairs:
        for year in range(args.start, args.end + 1):
            download_pair_year(pair, year)
    print("done")


if __name__ == "__main__":
    main()
