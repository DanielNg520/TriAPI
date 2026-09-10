import subprocess
import sys
from pathlib import Path


def make_deepseek_call_fn(task_id: str):
    script = Path(__file__).resolve().parent / "call_deepseek.py"
    invocations = 0

    def call_fn(prompt: str) -> str:
        nonlocal invocations
        this_task_id = task_id if invocations == 0 else f"{task_id}_retry"
        invocations += 1
        result = subprocess.run(
            [
                sys.executable,
                str(script),
                "--no-fallback",
                "--system-file",
                "/dev/null",
                "--task-id",
                this_task_id,
            ],
            input=prompt,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"call_deepseek.py exited with {result.returncode}: {result.stderr}"
            )
        return result.stdout

    return call_fn
