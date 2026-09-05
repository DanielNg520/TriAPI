"""Git-item-specific dispatch helpers extracted from scripts/dispatcher.py.

Pure move of `_dispatch_git_item` (and its `_resolve_path` helper that was
fixed in Phase 9.1 for relative `path` resolution against `project_dir`) out
of dispatcher.py so dispatcher.py stays under this repo's file-size ceiling.
No behavior change: function bodies, signatures, and docstrings are preserved
verbatim.
"""

import os

from scripts import git_ops

_GIT_CLONE_SCHEMA = {
    "type": "object",
    "required": ["git"],
    "properties": {
        "git": {
            "type": "object",
            "required": ["action", "path", "repo_url"],
            "properties": {
                "action": {"const": "clone"},
                "path": {"type": "string"},
                "repo_url": {"type": "string"},
                "branch": {"type": "string"},
            },
        }
    },
}

_GIT_PULL_SCHEMA = {
    "type": "object",
    "required": ["git"],
    "properties": {
        "git": {
            "type": "object",
            "required": ["action", "path"],
            "properties": {
                "action": {"const": "pull"},
                "path": {"type": "string"},
                "branch": {"type": "string"},
            },
        }
    },
}

_GIT_PUSH_SCHEMA = {
    "type": "object",
    "required": ["git"],
    "properties": {
        "git": {
            "type": "object",
            "required": ["action", "path", "branch"],
            "properties": {
                "action": {"const": "push"},
                "path": {"type": "string"},
                "branch": {"type": "string"},
                "remote": {"type": "string"},
                "set_upstream": {"type": "boolean"},
            },
        }
    },
}


def _resolve_path(project_dir: str, path: str) -> str:
    """Resolve a git-item `path` (relative or absolute) against `project_dir`.

    Phase 9.1 fix: previously `_dispatch_git_item` joined the raw `path`
    string directly to `project_dir` regardless of whether it was already
    absolute, which produced paths like
    '/work/repo//existing/abs/path' for items that supplied an absolute
    repo path. Use os.path.isabs() to pass through absolute paths
    unchanged and only relativize against project_dir when truly relative,
    so absolute paths supplied by the planner stay absolute.
    """
    if os.path.isabs(path):
        return path
    return os.path.join(project_dir, path)


def _dispatch_git_item(item: dict, project_dir: str) -> dict:
    """Run a git-ops item (clone/pull/push) outside the Tier 4 worker pipeline.

    Git ops don't fit the read/edit/build/verify Tier 4 worker loop:
    they mutate remote state, need their own network access, and produce
    side effects that the worker loop can't observe. They run inline here
    via `scripts.git_ops` and dispatch returns a synthesized checklist item
    shaped like a normal worker's `result` so the rest of dispatch doesn't
    need to know it's not a worker call.

    Found live 2026-08-18 (CARRYOVER.md queue item #1): the planner emits
    git items shaped like { "git": { "action": "clone", "path": "...",
    "repo_url": "..." } } etc., distinct from the usual
    { "target": ..., "build_cmd": ..., ... } shape; the dispatcher's main
    loop ignored them entirely because `target` was missing, so a clone
    step never ran.
    """
    from pathlib import Path

    git = item["git"]
    action = git["action"]
    path = _resolve_path(project_dir, git["path"])

    if action == "clone":
        result = git_ops.clone(
            repo_url=git["repo_url"],
            path=path,
            branch=git.get("branch"),
        )
        result_item = {
            "target": path,
            "result": result,
            "verify_only": True,
        }
        # Preserve context_files if the planner set them so downstream
            # reporting (e.g. regression_guard) sees the same shape.
        if "context_files" in item:
            result_item["context_files"] = item["context_files"]
        return result_item

    if action == "pull":
        result = git_ops.pull(
            path=path,
            branch=git.get("branch"),
        )
        result_item = {
            "target": path,
            "result": result,
            "verify_only": True,
        }
        if "context_files" in item:
            result_item["context_files"] = item["context_files"]
        return result_item

    if action == "push":
        result = git_ops.push(
            path=path,
            branch=git["branch"],
            remote=git.get("remote", "origin"),
            set_upstream=git.get("set_upstream", False),
        )
        result_item = {
            "target": path,
            "result": result,
            "verify_only": True,
        }
        if "context_files" in item:
            result_item["context_files"] = item["context_files"]
        return result_item

    raise ValueError(f"Unsupported git action: {action!r}")
