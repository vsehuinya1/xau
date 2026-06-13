"""Download XAUUSD M1 bars from histdata.com."""

from __future__ import annotations

import argparse
import time
import zipfile
from pathlib import Path

from histdata import download_hist_data as dl
from histdata.api import Platform as P, TimeFrame as TF

DATA_DIR = Path(__file__).resolve().parent


def download_year(year: int, retries: int = 5) -> Path:
    zip_path = DATA_DIR / f"DAT_ASCII_XAUUSD_M1_{year}.zip"
    csv_path = DATA_DIR / f"DAT_ASCII_XAUUSD_M1_{year}.csv"
    if csv_path.exists():
        print(f"skip {year} (csv exists)")
        return csv_path

    for attempt in range(1, retries + 1):
        try:
            print(f"downloading {year} (attempt {attempt})")
            dl(year=str(year), month=None, pair="xauusd",
               platform=P.GENERIC_ASCII, time_frame=TF.ONE_MINUTE)
            if zip_path.exists():
                with zipfile.ZipFile(zip_path) as zf:
                    zf.extractall(DATA_DIR)
                print(f"extracted {csv_path.name}")
                return csv_path
        except Exception as exc:
            print(f"error {year}: {exc}")
            time.sleep(5 * attempt)
    raise RuntimeError(f"failed to download {year}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=2018)
    parser.add_argument("--end", type=int, default=2025)
    args = parser.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for year in range(args.start, args.end + 1):
        download_year(year)
    print("done")


if __name__ == "__main__":
    main()
