import json
from datetime import date
from pathlib import Path

import pytest

from scripts.holiday_calendar import (
    extract_rest_days,
    known_holiday_dates,
    refresh_if_stale,
    years_needing_refresh,
)


def make_payload(year: int, off_days: int, start_month: int = 1, start_day: int = 1,
                 extra_dates: list[str] | None = None, name_prefix: str = "Holiday") -> dict:
    days = []
    month, day = start_month, start_day
    for i in range(off_days):
        days.append({
            "date": f"{year}-{month:02d}-{day:02d}",
            "name": f"{name_prefix}{i}",
            "isOffDay": True,
        })
        day += 1
        if day > 28:
            day = 1
            month += 1
    for d in (extra_dates or []):
        days.append({"date": d, "name": "extra", "isOffDay": True})
    return {"year": year, "papers": ["paper"], "days": days}


def make_cfg(holiday_dates: list[str] | None = None) -> dict:
    return {
        "deepseek": {
            "china_holiday_dates": holiday_dates or [],
            "holiday_source_url_template": "http://unused/{year}.json",
        }
    }


class TestExtractRestDays:
    def test_valid_payload_returns_only_off_days(self):
        payload = make_payload(2025, 22)
        payload["days"].append({"date": "2025-02-01", "name": "workday", "isOffDay": False})
        result = extract_rest_days(payload, 2025)
        assert result is not None
        assert result == sorted(result)
        assert all(d.startswith("2025-") for d in result)
        assert len(result) == 22

    def test_empty_placeholder_returns_none(self):
        payload = {"year": 2027, "papers": [], "days": []}
        assert extract_rest_days(payload, 2027) is None

    def test_too_few_days_returns_none(self):
        payload = make_payload(2025, 19)
        assert extract_rest_days(payload, 2025) is None

    def test_wrong_year_returns_none(self):
        payload = make_payload(2024, 22)
        assert extract_rest_days(payload, 2025) is None

    def test_neighbouring_year_dates_included(self):
        payload = make_payload(2023, 20, extra_dates=["2022-12-31"])
        result = extract_rest_days(payload, 2023)
        assert result is not None
        assert result[0] == "2022-12-31"
        assert len(result) == 21

    def test_date_two_years_away_returns_none(self):
        payload = make_payload(2023, 20, extra_dates=["2021-12-31"])
        assert extract_rest_days(payload, 2023) is None

    def test_unparseable_date_returns_none(self):
        payload = make_payload(2023, 20, extra_dates=["not-a-date"])
        assert extract_rest_days(payload, 2023) is None

    def test_too_few_in_year_days_returns_none(self):
        payload = make_payload(2023, 19, start_month=12, start_day=1,
                               extra_dates=[f"2022-12-{d:02d}" for d in range(1, 12)])
        assert extract_rest_days(payload, 2023) is None

    def test_malformed_payload_returns_none(self):
        assert extract_rest_days(None, 2025) is None
        assert extract_rest_days({"year": 2025}, 2025) is None
        assert extract_rest_days({"year": 2025, "papers": ["x"]}, 2025) is None
        assert extract_rest_days({"year": 2025, "papers": ["x"], "days": [{"date": "2025-01-01"}]}, 2025) is None


class TestKnownHolidayDates:
    def test_union_with_cache(self, tmp_path):
        cache = tmp_path / "cache.json"
        cache.write_text(json.dumps({"dates": ["2025-01-01", "2025-02-01"]}))
        cfg = make_cfg(["2025-03-01", "2025-01-01"])
        result = known_holiday_dates(cfg, cache)
        assert result == {"2025-01-01", "2025-02-01", "2025-03-01"}

    def test_missing_keys_contribute_nothing(self, tmp_path):
        cfg = {"deepseek": {}}
        result = known_holiday_dates(cfg, tmp_path / "missing.json")
        assert result == set()

    def test_missing_cache_contributes_nothing(self, tmp_path):
        cfg = make_cfg(["2025-01-01"])
        result = known_holiday_dates(cfg, tmp_path / "missing.json")
        assert result == {"2025-01-01"}

    def test_corrupt_cache_contributes_nothing(self, tmp_path):
        cache = tmp_path / "cache.json"
        cache.write_text("{not json")
        cfg = make_cfg(["2025-01-01"])
        result = known_holiday_dates(cfg, cache)
        assert result == {"2025-01-01"}


class TestYearsNeedingRefresh:
    def test_january_current_year_needed(self):
        known = {"2024-01-01"}
        assert years_needing_refresh(known, date(2025, 1, 15)) == [2025]

    def test_january_current_year_covered(self):
        known = {"2025-01-01"}
        assert years_needing_refresh(known, date(2025, 1, 15)) == []

    def test_november_next_year_included(self):
        known = {"2025-01-01"}
        assert years_needing_refresh(known, date(2025, 11, 15)) == [2026]

    def test_november_both_covered(self):
        known = {"2025-01-01", "2026-01-01"}
        assert years_needing_refresh(known, date(2025, 11, 15)) == []


class TestRefreshIfStale:
    def test_nothing_needed_no_fetch_no_files(self, tmp_path):
        cfg = make_cfg(["2025-01-01"])
        cache = tmp_path / "cache.json"
        attempt = tmp_path / "attempt.json"
        today = date(2025, 1, 15)
        calls = []
        result = refresh_if_stale(cfg, today, cache, attempt, fetch=lambda y: calls.append(y) or {})
        assert result == []
        assert calls == []
        assert not cache.exists()
        assert not attempt.exists()

    def test_successful_refresh_writes_cache_and_returns_years(self, tmp_path):
        cfg = make_cfg(["2024-01-01"])
        cache = tmp_path / "cache.json"
        attempt = tmp_path / "attempt.json"
        today = date(2025, 1, 15)
        calls = []

        def fake_fetch(year):
            calls.append(year)
            return make_payload(year, 21)

        result = refresh_if_stale(cfg, today, cache, attempt, fetch=fake_fetch)
        assert result == [2025]
        assert calls == [2025]
        assert cache.exists()
        data = json.loads(cache.read_text())
        assert data["updated"] == "2025-01-15"
        assert all(d.startswith("2025-") for d in data["dates"])
        assert len(data["dates"]) == 21
        assert attempt.read_text() == "2025-01-15"

    def test_second_call_same_day_no_fetch(self, tmp_path):
        cfg = make_cfg(["2024-01-01"])
        cache = tmp_path / "cache.json"
        attempt = tmp_path / "attempt.json"
        today = date(2025, 1, 15)
        calls = []

        def fake_fetch(year):
            calls.append(year)
            return make_payload(year, 21)

        assert refresh_if_stale(cfg, today, cache, attempt, fetch=fake_fetch) == [2025]
        calls.clear()
        assert refresh_if_stale(cfg, today, cache, attempt, fetch=fake_fetch) == []
        assert calls == []

    def test_raising_fetch_returns_empty_and_attempt_exists(self, tmp_path):
        cfg = make_cfg(["2024-01-01"])
        cache = tmp_path / "cache.json"
        attempt = tmp_path / "attempt.json"
        today = date(2025, 1, 15)

        def raising_fetch(year):
            raise RuntimeError("boom")

        result = refresh_if_stale(cfg, today, cache, attempt, fetch=raising_fetch)
        assert result == []
        assert not cache.exists()
        assert attempt.read_text() == "2025-01-15"

    def test_placeholder_payload_no_cache_write(self, tmp_path):
        cfg = make_cfg(["2024-01-01"])
        cache = tmp_path / "cache.json"
        attempt = tmp_path / "attempt.json"
        today = date(2025, 1, 15)

        def placeholder_fetch(year):
            return {"year": year, "papers": [], "days": []}

        result = refresh_if_stale(cfg, today, cache, attempt, fetch=placeholder_fetch)
        assert result == []
        assert not cache.exists()
        assert attempt.read_text() == "2025-01-15"

    def test_existing_cache_dates_preserved(self, tmp_path):
        cfg = make_cfg(["2024-01-01"])
        cache = tmp_path / "cache.json"
        cache.write_text(json.dumps({"dates": ["2024-05-01"], "updated": "2024-01-01"}))
        attempt = tmp_path / "attempt.json"
        today = date(2025, 1, 15)

        def fake_fetch(year):
            return make_payload(year, 21)

        result = refresh_if_stale(cfg, today, cache, attempt, fetch=fake_fetch)
        assert result == [2025]
        data = json.loads(cache.read_text())
        assert "2024-05-01" in data["dates"]
        assert len([d for d in data["dates"] if d.startswith("2025-")]) == 21

    def test_november_two_years_needed(self, tmp_path):
        cfg = make_cfg(["2024-01-01"])
        cache = tmp_path / "cache.json"
        attempt = tmp_path / "attempt.json"
        today = date(2025, 11, 15)
        calls = []

        def fake_fetch(year):
            calls.append(year)
            if year == 2025:
                return make_payload(year, 21)
            return {"year": year, "papers": [], "days": []}

        result = refresh_if_stale(cfg, today, cache, attempt, fetch=fake_fetch)
        assert result == [2025]
        assert calls == [2025, 2026]
        data = json.loads(cache.read_text())
        assert all(d.startswith("2025-") for d in data["dates"])
