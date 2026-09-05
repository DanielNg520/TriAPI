import yaml
from pathlib import Path
import json
from datetime import datetime, timezone


def calculate_cost(
    input_tokens: int,
    output_tokens: int,
    config_path: str | None = None,
) -> float:
    if config_path is None:
        config_path = Path(__file__).resolve().parents[2] / "config" / "tiers.yaml"

    pricing = yaml.safe_load(Path(config_path).read_text())["deepseek_reference_pricing"]

    cache_miss_rate = pricing["cache_miss_per_mtok_usd"]
    output_rate = pricing.get("output_per_mtok_usd")
    if output_rate is None:
        output_rate = cache_miss_rate

    return (input_tokens / 1_000_000 * cache_miss_rate) + (
        output_tokens / 1_000_000 * output_rate
    )


def log_cost(
    task_id: str,
    input_tokens: int,
    output_tokens: int,
    log_path: str | None = None,
) -> dict:
    if log_path is None:
        log_path = Path(__file__).resolve().parents[1] / "logs" / "cost_log.jsonl"

    record = {
        "task_id": task_id,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

    return record


def read_cost_summary(
    log_path: str | None = None,
    config_path: str | None = None,
) -> dict:
    path = (
        Path(log_path)
        if log_path is not None
        else Path(__file__).resolve().parents[1] / "logs" / "cost_log.jsonl"
    )

    if not path.exists():
        return {
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_cost_usd": 0.0,
            "entry_count": 0,
        }

    total_input_tokens = 0
    total_output_tokens = 0
    entry_count = 0

    with path.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            entry = json.loads(line)
            total_input_tokens += entry["input_tokens"]
            total_output_tokens += entry["output_tokens"]
            entry_count += 1

    if entry_count == 0:
        return {
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_cost_usd": 0.0,
            "entry_count": 0,
        }

    total_cost_usd = calculate_cost(
        total_input_tokens,
        total_output_tokens,
        config_path=config_path,
    )

    return {
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "total_cost_usd": total_cost_usd,
        "entry_count": entry_count,
    }
