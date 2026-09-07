"""Streams a fresh `claude -p` call's output line by line for `triapi tui`
-- no session continuity, one subprocess per submitted prompt.
"""

import subprocess
from typing import Iterator


def stream_claude_output(prompt: str) -> Iterator[str]:
    """Run `claude -p <prompt>` as a subprocess via
    subprocess.Popen(["claude", "-p", prompt], stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT, text=True), and yield its combined
    stdout+stderr one line at a time as it's produced (not buffered
    until the process exits) -- iterate `proc.stdout` directly. Strip
    only the trailing newline from each yielded line (str.rstrip("\\n")).
    Stop yielding once the process's stdout closes (EOF); then wait()
    on the process to reap it. Do not raise if the process exits
    non-zero -- just stop yielding, the caller doesn't need the exit code.
    """
    proc = subprocess.Popen(
        ["claude", "-p", prompt],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    for line in proc.stdout:
        yield line.rstrip("\n")
    proc.wait()
