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
    for SSH remotes (SSH agent) -- never handles, stores, or logs
    credentials itself. HTTPS remotes needing interactive auth are NOT
    supported: every invocation explicitly disables credential helpers and
    askpass, so an HTTPS remote lacking a working non-interactive credential
    setup fails fast with a clear error rather than hanging.
  - github.com HTTPS URLs are automatically rewritten to SSH (both for a
    fresh clone URL and for an existing origin remote before pull/push),
    since SSH is the only auth path confirmed working in this environment
    -- always use it rather than relying on whoever writes the plan to
    remember to say "git@github.com:..." instead of "https://github.com/...".
"""

import os
import re
import subprocess
import time
from pathlib import Path

from scripts.tri_logging import get_logger

log = get_logger("git_ops")

DEFAULT_BRANCHES = {"main", "master"}

_GITHUB_HTTPS_RE = re.compile(r"^https://github\.com/([^/]+)/([^/]+?)(\.git)?/?$")


def _to_ssh_url(url: str) -> str | None:
    """Returns the SSH form of a github.com HTTPS URL, or None if `url`
    isn't a github.com HTTPS URL (left untouched -- other hosts/forms may
    not follow the same convention or may not have SSH set up)."""
    m = _GITHUB_HTTPS_RE.match(url.strip())
    if not m:
        return None
    owner, repo, _ = m.groups()
    return f"git@github.com:{owner}/{repo}.git"

# Belt-and-suspenders against hanging on a credential prompt of any kind:
# GIT_TERMINAL_PROMPT=0 stops git's own terminal prompt, but a *configured*
# credential helper (e.g. a GUI askpass like ksshaskpass) can still hang
# trying to show a dialog that never returns in a headless/background
# context -- observed exactly this: a push hung 300s+ with that env var set
# and stdin closed. -c credential.helper= and -c core.askpass= strip both
# for this invocation only, so auth failure is immediate and clear instead.
_GIT_ENV = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
_NO_PROMPT_ARGS = ["-c", "credential.helper=", "-c", "core.askpass="]


def _run(cmd: list[str], cwd: str, timeout: int = 300) -> tuple[bool, str]:
    full_cmd = [cmd[0], *_NO_PROMPT_ARGS, *cmd[1:]]
    try:
        result = subprocess.run(
            full_cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout,
            stdin=subprocess.DEVNULL, env=_GIT_ENV,
        )
    except subprocess.TimeoutExpired:
        log.error("git command timed out after %ds: %s", timeout, " ".join(cmd))
        return False, f"command timed out after {timeout}s: {' '.join(cmd)}"
    output = (result.stdout or "") + (result.stderr or "")
    return result.returncode == 0, output


def _ensure_ssh_remote(repo_dir: str) -> None:
    ok, current_url = _run(["git", "remote", "get-url", "origin"], cwd=repo_dir)
    if not ok:
        return
    ssh_url = _to_ssh_url(current_url.strip())
    if ssh_url:
        log.info("Rewriting origin to SSH in %s: %s -> %s", repo_dir, current_url.strip(), ssh_url)
        _run(["git", "remote", "set-url", "origin", ssh_url], cwd=repo_dir)


def clone(url: str, path: str) -> dict:
    ssh_url = _to_ssh_url(url)
    if ssh_url:
        log.info("Rewriting clone URL to SSH: %s -> %s", url, ssh_url)
        url = ssh_url
    log.info("git clone %s -> %s", url, path)
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    ok, output = _run(["git", "clone", url, str(dest)], cwd=str(dest.parent))
    if not ok:
        log.error("git clone failed: %s", output[:500])
    return {"ok": ok, "output": output}


def pull(repo_dir: str) -> dict:
    _ensure_ssh_remote(repo_dir)
    log.info("git pull in %s", repo_dir)
    ok, output = _run(["git", "pull", "--ff-only"], cwd=repo_dir)
    if not ok:
        log.error("git pull failed: %s", output[:500])
    return {"ok": ok, "output": output}


def push(repo_dir: str, message: str, branch: str | None = None) -> dict:
    _ensure_ssh_remote(repo_dir)
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
