import json

import pytest
import yaml

from scripts.cost import calculate_cost, check_budget, log_cost, read_cost_summary


def test_calculate_cost_basic(tmp_path):
    config_path = tmp_path / "pricing.yaml"
    config_path.write_text(yaml.safe_dump({
        "deepseek_reference_pricing": {
            "cache_miss_per_mtok_usd": 0.14,
            "output_per_mtok_usd": 0.28,
        }
    }))

    assert calculate_cost(1_000_000, 1_000_000, config_path=str(config_path)) == pytest.approx(0.14 + 0.28)


def test_calculate_cost_output_rate_null_fallback(tmp_path):
    config_path = tmp_path / "pricing.yaml"
    config_path.write_text(yaml.safe_dump({
        "deepseek_reference_pricing": {
            "cache_miss_per_mtok_usd": 0.14,
            "output_per_mtok_usd": None,
        }
    }))

    assert calculate_cost(1_000_000, 1_000_000, config_path=str(config_path)) == pytest.approx(0.14 + 0.14)


def test_calculate_cost_missing_config(tmp_path):
    with pytest.raises(FileNotFoundError):
        calculate_cost(1, 1, config_path=str(tmp_path / "nope.yaml"))


def test_log_cost_creates_file_and_appends(tmp_path):
    log_path = tmp_path / "sub" / "cost_log.jsonl"

    log_cost("task-a", 10, 20, log_path=str(log_path))

    assert log_path.exists()
    lines = log_path.read_text().splitlines()
    assert len(lines) == 1

    entry = json.loads(lines[0])
    assert entry["task_id"] == "task-a"
    assert entry["input_tokens"] == 10
    assert entry["output_tokens"] == 20
    assert isinstance(entry["timestamp"], str)

    log_cost("task-b", 30, 40, log_path=str(log_path))
    lines = log_path.read_text().splitlines()
    assert len(lines) == 2


def test_read_cost_summary_missing_and_empty(tmp_path):
    missing = read_cost_summary(log_path=str(tmp_path / "nope.jsonl"))
    assert missing["total_input_tokens"] == 0
    assert missing["total_output_tokens"] == 0
    assert missing["entry_count"] == 0
    assert missing["total_cost_usd"] == 0

    empty_log = tmp_path / "empty.jsonl"
    empty_log.write_text("")

    empty = read_cost_summary(log_path=str(empty_log))
    assert empty["total_input_tokens"] == 0
    assert empty["total_output_tokens"] == 0
    assert empty["entry_count"] == 0
    assert empty["total_cost_usd"] == 0


def test_read_cost_summary_multiple_entries(tmp_path):
    pricing_yaml = tmp_path / "pricing.yaml"
    pricing_yaml.write_text(yaml.safe_dump({
        "deepseek_reference_pricing": {
            "cache_miss_per_mtok_usd": 0.14,
            "output_per_mtok_usd": 0.28,
        }
    }))

    log_path = tmp_path / "cost_log.jsonl"
    log_path.write_text("\n".join([
        json.dumps({
            "task_id": "task-1",
            "input_tokens": 100,
            "output_tokens": 50,
            "timestamp": "2024-01-01T00:00:00",
        }),
        json.dumps({
            "task_id": "task-2",
            "input_tokens": 200,
            "output_tokens": 50,
            "timestamp": "2024-01-01T00:00:00",
        }),
    ]))

    summary = read_cost_summary(log_path=str(log_path), config_path=str(pricing_yaml))

    assert summary["total_input_tokens"] == 300
    assert summary["total_output_tokens"] == 100
    assert summary["entry_count"] == 2
    assert summary["total_cost_usd"] == pytest.approx(
        calculate_cost(300, 100, config_path=str(pricing_yaml))
    )


def _write_pricing_yaml(path, cache_miss=0.14, output=0.14):
    path.write_text(yaml.safe_dump({
        "deepseek_reference_pricing": {
            "cache_miss_per_mtok_usd": cache_miss,
            "output_per_mtok_usd": output,
        }
    }))


def test_check_budget_under_limit(tmp_path):
    config = tmp_path / "pricing.yaml"
    _write_pricing_yaml(config)
    log = tmp_path / "cost.jsonl"
    log_cost("t", 100, 100, log_path=str(log))

    result = check_budget(5.0, log_path=str(log), config_path=str(config))

    assert result["under_limit"] is True
    assert result["total_cost_usd"] > 0
    assert result["remaining_usd"] == pytest.approx(5.0 - result["total_cost_usd"])


def test_check_budget_over_limit(tmp_path):
    config = tmp_path / "pricing.yaml"
    _write_pricing_yaml(config)
    log = tmp_path / "cost.jsonl"
    log_cost("t", 1_000_000, 1_000_000, log_path=str(log))

    result = check_budget(0.0001, log_path=str(log), config_path=str(config))

    assert result["under_limit"] is False
    assert result["remaining_usd"] < 0


def test_check_budget_exact_limit(tmp_path):
    config = tmp_path / "pricing.yaml"
    _write_pricing_yaml(config)
    log = tmp_path / "cost.jsonl"
    log_cost("t", 1_000_000, 1_000_000, log_path=str(log))

    limit = calculate_cost(1_000_000, 1_000_000, config_path=str(config))
    result = check_budget(limit, log_path=str(log), config_path=str(config))

    assert result["under_limit"] is True
    assert result["remaining_usd"] == pytest.approx(0.0)


def test_check_budget_missing_and_empty_log(tmp_path):
    result = check_budget(5.0, log_path=str(tmp_path / "nope.jsonl"))

    assert result["under_limit"] is True
    assert result["total_cost_usd"] == 0.0
    assert result["remaining_usd"] == pytest.approx(5.0)
