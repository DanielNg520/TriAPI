#!/usr/bin/env python3
"""doc_staleness.py - determine if a model call should be skipped."""

import subprocess
from pathlib import Path
import os


def _fallback_is_doc_target(path: str) -> bool:
    """Fallback mirror of dispatcher.is_doc_target glob semantics.
    
    Patterns: ["*.md", "docs/**"]
    """
    # Match any .md file (regardless of directory depth)
    if path.endswith(".md"):
        return True
    # Match anything under docs/ (including the directory itself)
    if path.startswith("docs/") or path == "docs":
        return True
    return False


_DOC_GLOBS = ["*.md", "docs/**"]


def _get_is_doc_target():
    """Lazy guarded import of dispatcher.is_doc_target with fallback."""
    try:
        from dispatcher import is_doc_target as _real_is_doc_target
        # dispatcher.is_doc_target(rel_path, globs) requires an explicit
        # globs list; wrap it to the single-arg signature used here, mirroring
        # the same default glob set as the fallback.
        return lambda path: _real_is_doc_target(path, _DOC_GLOBS)
    except ImportError:
        return _fallback_is_doc_target


_is_doc_target = _get_is_doc_target()


def should_skip_model_call(doc_path, workdir, task_description) -> tuple[bool, str]:
    """Return (True, reason) if model call should be skipped.

    Skip only if all of the following hold:
    1. task_description does NOT explicitly mention the doc (forces model call).
    2. workdir is inside a git work tree.
    3. git status --porcelain is empty (clean tree).
    4. doc has at least one commit.
    5. The doc's last commit epoch is strictly greater than the epoch of the
       most recent commit that touched any non-doc file (within last 500 commits).

    Any failure returns (False, reason) (fail open).
    """
    try:
        # Normalize paths
        doc_path = Path(doc_path)
        workdir = Path(workdir)

        # Compute relative path from workdir to doc
        try:
            relpath = doc_path.relative_to(workdir)
        except ValueError:
            # If not relative, compute using os.path.relpath
            relpath = Path(os.path.relpath(doc_path, workdir))
        relpath_str = relpath.as_posix()
        basename = doc_path.name
        stem = doc_path.stem

        # (1) Explicit mention override
        task_lower = task_description.lower()
        if (
            relpath_str.lower() in task_lower
            or basename.lower() in task_lower
            or stem.lower() in task_lower
        ):
            return (False, "explicit mention in task description")

        # (2) Git work tree check
        proc = subprocess.run(
            ["git", "-C", str(workdir), "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0 or proc.stdout.strip() != "true":
            return (False, "not a git repository")

        # (3) Clean working tree
        proc = subprocess.run(
            ["git", "-C", str(workdir), "status", "--porcelain"],
            capture_output=True,
            text=True,
        )
        if proc.stdout.strip() != "":
            return (False, "dirty working tree")

        # (4) Doc has at least one commit
        proc = subprocess.run(
            ["git", "-C", str(workdir), "log", "-1", "--format=%ct", "--", relpath_str],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            return (False, "git log failed for doc")
        doc_commit_epoch_str = proc.stdout.strip()
        if not doc_commit_epoch_str:
            return (False, "doc has no commits")
        try:
            doc_commit_epoch = int(doc_commit_epoch_str)
        except ValueError:
            return (False, "invalid doc commit epoch")

        # (5) Scan recent commits for non-doc changes
        proc = subprocess.run(
            [
                "git",
                "-C",
                str(workdir),
                "log",
                "-n",
                "500",
                "--pretty=format:C %ct",
                "--name-only",
            ],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            return (False, "git log scan failed")

        lines = proc.stdout.splitlines()
        current_epoch = None
        current_files = []
        # Cumulative: has any commit visited so far (newest-first) touched
        # the doc? Using git log's own chronological ORDER (rather than raw
        # %ct epoch comparison) avoids false "not fresher" verdicts when two
        # sequential commits land in the same one-second epoch resolution
        # (common for scripted/CI commits made back-to-back).
        doc_touched_in_window = False

        def process_commit(files):
            """Mark doc-touch, and return True if commit has any non-doc file
            (excluding the target doc itself)."""
            nonlocal doc_touched_in_window
            if relpath_str in files:
                doc_touched_in_window = True
            for f in files:
                if f == relpath_str:
                    continue
                if not _is_doc_target(f):
                    return True
            return False

        result = None
        for line in lines:
            line = line.strip()
            if line.startswith("C "):
                # Process previous commit's files
                if current_epoch is not None:
                    if process_commit(current_files):
                        result = (
                            (True, "doc is fresh")
                            if doc_touched_in_window
                            else (False, "doc is not fresher than non-doc changes")
                        )
                        break
                # Start new commit
                try:
                    current_epoch = int(line[2:])
                except ValueError:
                    current_epoch = None
                    current_files = []
                    continue
                current_files = []
            elif line and current_epoch is not None:
                current_files.append(line)

        # Check the last commit in the list
        if result is None and current_epoch is not None:
            if process_commit(current_files):
                result = (
                    (True, "doc is fresh")
                    if doc_touched_in_window
                    else (False, "doc is not fresher than non-doc changes")
                )

        if result is None:
            # No non-doc commits in scan window -> cannot satisfy skip condition.
            return (False, "no non-doc commits in scan window")

        return result

    except Exception as e:
        return (False, f"exception: {e}")
