"""Build US macro event calendar for XAUUSD Test 1."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

ET = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")
CACHE_PATH = Path(__file__).resolve().parent / "calendar_cache.json"

# FOMC statement release: 14:00 ET on decision day (last day of meeting).
FOMC_DECISIONS: dict[int, list[str]] = {
    2018: ["2018-01-31", "2018-03-21", "2018-05-02", "2018-06-13", "2018-08-01",
           "2018-09-26", "2018-11-08", "2018-12-19"],
    2019: ["2019-01-30", "2019-03-20", "2019-05-01", "2019-06-19", "2019-07-31",
           "2019-09-18", "2019-10-30", "2019-12-11"],
    2020: ["2020-01-29", "2020-03-03", "2020-03-15", "2020-03-19", "2020-03-23",
           "2020-03-31", "2020-04-29", "2020-06-10", "2020-07-29", "2020-09-16",
           "2020-11-05", "2020-12-16"],
    2021: ["2021-01-27", "2021-03-17", "2021-04-28", "2021-06-16", "2021-07-28",
           "2021-09-22", "2021-11-03", "2021-12-15"],
    2022: ["2022-01-26", "2022-03-16", "2022-05-04", "2022-06-15", "2022-07-27",
           "2022-09-21", "2022-11-02", "2022-12-14"],
    2023: ["2023-02-01", "2023-03-22", "2023-05-03", "2023-06-14", "2023-07-26",
           "2023-09-20", "2023-11-01", "2023-12-13"],
    2024: ["2024-01-31", "2024-03-20", "2024-05-01", "2024-06-12", "2024-07-31",
           "2024-09-18", "2024-11-07", "2024-12-18"],
    2025: ["2025-01-29", "2025-03-19", "2025-05-07", "2025-06-18", "2025-07-30",
           "2025-09-17", "2025-10-29", "2025-12-10"],
}

# BLS CPI release dates (8:30 AM ET). Sourced from BLS published schedules.
CPI_RELEASES: dict[int, list[str]] = {
    2018: ["2018-01-12", "2018-02-14", "2018-03-13", "2018-04-11", "2018-05-10",
           "2018-06-12", "2018-07-12", "2018-08-10", "2018-09-13", "2018-10-11",
           "2018-11-14", "2018-12-12"],
    2019: ["2019-01-11", "2019-02-13", "2019-03-12", "2019-04-10", "2019-05-10",
           "2019-06-12", "2019-07-11", "2019-08-13", "2019-09-12", "2019-10-10",
           "2019-11-13", "2019-12-11"],
    2020: ["2020-01-14", "2020-02-13", "2020-03-11", "2020-04-10", "2020-05-12",
           "2020-06-10", "2020-07-14", "2020-08-12", "2020-09-11", "2020-10-13",
           "2020-11-12", "2020-12-10"],
    2021: ["2021-01-13", "2021-02-10", "2021-03-10", "2021-04-13", "2021-05-12",
           "2021-06-10", "2021-07-13", "2021-08-11", "2021-09-14", "2021-10-13",
           "2021-11-10", "2021-12-10"],
    2022: ["2022-01-12", "2022-02-10", "2022-03-10", "2022-04-12", "2022-05-11",
           "2022-06-10", "2022-07-13", "2022-08-10", "2022-09-13", "2022-10-13",
           "2022-11-10", "2022-12-13"],
    2023: ["2023-01-12", "2023-02-14", "2023-03-14", "2023-04-12", "2023-05-10",
           "2023-06-13", "2023-07-12", "2023-08-10", "2023-09-13", "2023-10-12",
           "2023-11-14", "2023-12-12"],
    2024: ["2024-01-11", "2024-02-13", "2024-03-12", "2024-04-10", "2024-05-15",
           "2024-06-12", "2024-07-11", "2024-08-14", "2024-09-11", "2024-10-10",
           "2024-11-13", "2024-12-11"],
    2025: ["2025-01-15", "2025-02-12", "2025-03-12", "2025-04-10", "2025-05-13",
           "2025-06-11", "2025-07-15", "2025-08-12", "2025-09-11", "2025-10-15",
           "2025-11-13", "2025-12-18"],
}


@dataclass(frozen=True)
class MacroEvent:
    name: str
    ts_utc: datetime

    @property
    def date(self) -> date:
        return self.ts_utc.date()


def _et_to_utc(day: str, hour: int, minute: int) -> datetime:
    local = datetime.strptime(day, "%Y-%m-%d").replace(
        hour=hour, minute=minute, second=0, tzinfo=ET
    )
    return local.astimezone(UTC)


def nfp_events(year_start: int = 2018, year_end: int = 2025) -> list[MacroEvent]:
    """Employment Situation: first Friday of month, 08:30 ET."""
    events: list[MacroEvent] = []
    for year in range(year_start, year_end + 1):
        for month in range(1, 13):
            d = date(year, month, 1)
            while d.weekday() != 4:
                d += timedelta(days=1)
            events.append(MacroEvent("NFP", _et_to_utc(d.isoformat(), 8, 30)))
    return events


def cpi_events(year_start: int = 2018, year_end: int = 2025) -> list[MacroEvent]:
    events: list[MacroEvent] = []
    for year in range(year_start, year_end + 1):
        for day in CPI_RELEASES.get(year, []):
            events.append(MacroEvent("CPI", _et_to_utc(day, 8, 30)))
    return events


def fomc_events(year_start: int = 2018, year_end: int = 2025) -> list[MacroEvent]:
    events: list[MacroEvent] = []
    for year in range(year_start, year_end + 1):
        for day in FOMC_DECISIONS.get(year, []):
            events.append(MacroEvent("FOMC", _et_to_utc(day, 14, 0)))
    return events


def scrape_cpi_from_ff(year: int, month: int) -> list[str]:
    """Fallback: scrape ForexFactory for CPI US release dates."""
    months = ["jan", "feb", "mar", "apr", "may", "jun",
              "jul", "aug", "sep", "oct", "nov", "dec"]
    url = f"https://www.forexfactory.com/calendar?month={months[month - 1]}.{year}"
    headers = {"User-Agent": "Mozilla/5.0 (compatible; xau-research/1.0)"}
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    dates: list[str] = []
    for row in soup.select("tr.calendar__row"):
        title_el = row.select_one(".calendar__event-title")
        if not title_el or "CPI" not in title_el.get_text():
            continue
        country = row.select_one(".calendar__currency")
        if country and "USD" not in country.get_text():
            continue
        day_el = row.get("data-day")
        if day_el:
            dates.append(day_el)
    return dates


def build_calendar(year_start: int = 2018, year_end: int = 2025) -> list[MacroEvent]:
    events = cpi_events(year_start, year_end) + nfp_events(year_start, year_end) + fomc_events(year_start, year_end)
    events.sort(key=lambda e: e.ts_utc)
    return events


def save_cache(events: list[MacroEvent], path: Path = CACHE_PATH) -> None:
    payload = [{"name": e.name, "ts_utc": e.ts_utc.isoformat()} for e in events]
    path.write_text(json.dumps(payload, indent=2))


def load_calendar(year_start: int = 2018, year_end: int = 2025) -> list[MacroEvent]:
    if CACHE_PATH.exists():
        raw = json.loads(CACHE_PATH.read_text())
        return [MacroEvent(r["name"], datetime.fromisoformat(r["ts_utc"])) for r in raw]
    events = build_calendar(year_start, year_end)
    save_cache(events)
    return events


if __name__ == "__main__":
    ev = build_calendar()
    print(f"events: {len(ev)}")
    for e in ev[:5]:
        print(e.name, e.ts_utc)
