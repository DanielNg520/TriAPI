"""Git operations available to plan steps: clone, pull, push.

A distinct capability from the file-fix pipeline -- these are direct shell
git commands, not AI-drafted content. Every operation is logged via
tri_logging for a full audit trail, since push affects shared/remote state.

Safety rails (not overridable by a plan):
  - never force-push
  - push never lands directly on the repo's default branch (main/master)
    unless a plan step explicitly names that exact branch -- otherwise a
    new branch is created, so an unattended dispatch run can't clobber the
    primary branch's history or trigger unwanted CI/deploys on it
  - relies on whatever git credential setup already exists on this machine
    (SSH agent / credential helper) -- never handles, stores, or logs
    credentials itself
"""

import subprocess
import time
from pathlib import Path

from scripts.tri_logging import get_logger

log = get_logger("git_ops")

DEFAULT_BRANCHES = {"main", "master"}


def _run(cmd: list[str], cwd: str, timeout: int = 300) -> tuple[bool, str]:
    result = subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL
    )
    output = (result.stdout or "") + (result.stderr or "")
    return result.returncode == 0, output


def clone(url: str, path: str) -> dict:
    log.info("git clone %s -> %s", url, path)
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    ok, output = _run(["git", "clone", url, str(dest)], cwd=str(dest.parent))
    if not ok:
        log.error("git clone failed: %s", output[:500])
    return {"ok": ok, "output": output}


def pull(repo_dir: str) -> dict:
    log.info("git pull in %s", repo_dir)
    ok, output = _run(["git", "pull", "--ff-only"], cwd=repo_dir)
    if not ok:
        log.error("git pull failed: %s", output[:500])
    return {"ok": ok, "output": output}


def push(repo_dir: str, message: str, branch: str | None = None) -> dict:
    ok, current_out = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_dir)
    if not ok:
        return {"ok": False, "output": current_out}
    current_branch = current_out.strip()

    if branch:
        target_branch = branch
        if branch != current_branch:
            ok, out = _run(["git", "checkout", "-B", branch], cwd=repo_dir)
            if not ok:
                return {"ok": False, "output": out}
    elif current_branch in DEFAULT_BRANCHES:
        # Refuse to push straight to main/master unless a plan step
        # explicitly named it -- protects the primary branch from an
        # unattended dispatch run.
        target_branch = f"triapi/{Path(repo_dir).name}-{int(time.time())}"
        log.warning(
            "Refusing to push directly to %s; creating branch %s instead", current_branch, target_branch
        )
        ok, out = _run(["git", "checkout", "-b", target_branch], cwd=repo_dir)
        if not ok:
            return {"ok": False, "output": out}
    else:
        target_branch = current_branch

    ok, out = _run(["git", "add", "-A"], cwd=repo_dir)
    if not ok:
        return {"ok": False, "output": out}

    ok, status_out = _run(["git", "status", "--porcelain"], cwd=repo_dir)
    if status_out.strip():
        ok, out = _run(["git", "commit", "-m", message], cwd=repo_dir)
        if not ok:
            return {"ok": False, "output": out}
    else:
        log.info("Nothing to commit in %s", repo_dir)

    log.info("git push origin %s (from %s)", target_branch, repo_dir)
    ok, out = _run(["git", "push", "-u", "origin", target_branch], cwd=repo_dir)
    if not ok:
        log.error("git push failed: %s", out[:500])
    return {"ok": ok, "output": out, "branch": target_branch}
