import json
import logging
import os
import tempfile
from datetime import date
from pathlib import Path

import requests

MIN_REST_DAYS = 20

CACHE_PATH = Path(__file__).resolve().parents[1] / "config" / "china_holidays.json"
ATTEMPT_PATH = Path(__file__).resolve().parents[1] / "logs" / "holiday_refresh_attempt.txt"

logger = logging.getLogger(__name__)


def extract_rest_days(payload: dict, year: int, min_days: int = MIN_REST_DAYS) -> list[str] | None:
    try:
        if payload["year"] != year:
            return None
        papers = payload["papers"]
        if not isinstance(papers, list) or not papers:
            return None
        days = payload["days"]
        if not isinstance(days, list):
            return None

        off_days = []
        for entry in days:
            if not isinstance(entry, dict):
                return None
            date_str = entry["date"]
            if not isinstance(date_str, str):
                return None
            date.fromisoformat(date_str)
            if entry.get("isOffDay") is True:
                off_days.append(date_str)

        if len(off_days) < min_days:
            return None

        off_dates = [date.fromisoformat(d) for d in off_days]
        for d in off_dates:
            if d.year < year - 1 or d.year > year + 1:
                return None
        if sum(1 for d in off_dates if d.year == year) < min_days:
            return None

        return sorted(off_days)
    except (KeyError, TypeError, ValueError):
        return None


def _read_cache_dates(cache_path: Path) -> set[str]:
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        dates = data["dates"]
        if not isinstance(dates, list):
            return set()
        return {d for d in dates if isinstance(d, str)}
    except (OSError, ValueError, KeyError, TypeError):
        return set()


def known_holiday_dates(cfg: dict, cache_path: Path = CACHE_PATH) -> set[str]:
    dates = set()
    deepseek_cfg = cfg.get("deepseek", {})
    static_dates = deepseek_cfg.get("china_holiday_dates", [])
    if isinstance(static_dates, list):
        dates.update(d for d in static_dates if isinstance(d, str))
    dates.update(_read_cache_dates(cache_path))
    return dates


def years_needing_refresh(known: set[str], today: date) -> list[int]:
    needed = []
    for year in (today.year, today.year + 1):
        if year == today.year + 1 and today.month < 11:
            continue
        if not any(d.startswith(f"{year}-") for d in known):
            needed.append(year)
    return needed


def fetch_year(year: int, url_template: str, timeout: float = 10.0) -> dict:
    response = requests.get(url_template.format(year=year), timeout=timeout)
    response.raise_for_status()
    return response.json()


def refresh_if_stale(
    cfg: dict,
    today: date,
    cache_path: Path = CACHE_PATH,
    attempt_path: Path = ATTEMPT_PATH,
    fetch=None,
) -> list[int]:
    try:
        known = known_holiday_dates(cfg, cache_path)
        needed = years_needing_refresh(known, today)
        if not needed:
            return []

        today_iso = today.isoformat()
        if attempt_path.exists() and attempt_path.read_text(encoding="utf-8").strip() == today_iso:
            return []

        attempt_path.parent.mkdir(parents=True, exist_ok=True)
        attempt_path.write_text(today_iso, encoding="utf-8")

        fetcher = fetch if fetch is not None else lambda year: fetch_year(
            year, cfg["deepseek"]["holiday_source_url_template"]
        )

        refreshed = []
        new_dates_by_year = {}
        for year in needed:
            try:
                payload = fetcher(year)
                dates = extract_rest_days(payload, year)
                if dates is None:
                    logger.warning("Holiday refresh for %s failed validation", year)
                    continue
                refreshed.append(year)
                new_dates_by_year[year] = dates
            except Exception:
                logger.warning("Holiday refresh for %s failed", year, exc_info=True)

        if not refreshed:
            return []

        existing_dates = _read_cache_dates(cache_path)
        merged = sorted(existing_dates | {d for dates in new_dates_by_year.values() for d in dates})

        cache_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=cache_path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump({"dates": merged, "updated": today_iso}, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, cache_path)
        except Exception:
            logger.warning("Failed to write holiday cache", exc_info=True)
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            return []

        log_parts = []
        for year in refreshed:
            log_parts.append(f"{year}: {len(new_dates_by_year[year])} days")
        logger.info("Refreshed China holidays for %s", ", ".join(log_parts))

        return refreshed
    except Exception:
        logger.warning("Holiday refresh failed", exc_info=True)
        return []
