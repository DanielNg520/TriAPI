import subprocess
import sys
from pathlib import Path


def make_planner_call_fn(task_id: str, system_file: str):
    planner_script = Path(__file__).resolve().parent / "call_planner.py"
    invocation_count = 0

    def call_fn(prompt: str) -> str:
        nonlocal invocation_count
        invocation_count += 1
        current_task_id = task_id if invocation_count == 1 else f"{task_id}_retry"

        result = subprocess.run(
            [
                sys.executable,
                str(planner_script),
                "--system-file",
                system_file,
                "--task-id",
                current_task_id,
            ],
            input=prompt,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"call_planner.py failed with return code {result.returncode}: {result.stderr}"
            )

        return result.stdout

    return call_fn
