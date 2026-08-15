#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script for managing lesson records.
"""

import argparse
import json
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Optional

from scripts.tri_logging import get_logger

log = get_logger("lessons")


# Paths ---------------------------------------------------------------

LESSONS_PATH = (
    Path(__file__).resolve().parent.parent / "knowledge" / "lessons.jsonl"
)

# Helper Functions ----------------------------------------------

def _tokenize(text: str) -> List[str]:
    """Simple whitespace and non-alphanumeric tokenizer, lowercased."""
    import re
    return [t.lower() for t in re.split(r"\W+", text) if len(t) > 2]


def _ensure_file_exists(path: Path) -> None:
    if not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.touch()


# Core Functions ----------------------------------------------

def load_lessons() -> List[Dict]:
    """Parse lessons from the JSONL file."""
    lessons: List[Dict] = []
    _ensure_file_exists(LESSONS_PATH)

    with LESSONS_PATH.open("r", encoding="utf-8") as fp:
        for lineno, line in enumerate(fp, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                lesson = json.loads(line)
                lessons.append(lesson)
            except (json.JSONDecodeError, TypeError) as exc:
                log.warning("Failed to parse line %s in lessons file: %s", lineno, exc)
    return lessons


def add_lesson(
    bug_description: str,
    what_went_wrong: str,
    fix_description: str,
    category: str = "bug_fix",
    component: str = "",
    tags: Optional[List[str]] = None,
) -> Dict:
    """Append a lesson safely, deduplicating identical records."""
    import fcntl

    _ensure_file_exists(LESSONS_PATH)

    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y%m%d%H%M%S%f")
    slug_component = component.strip().replace(" ", "-").replace("/", "-").lower()
    id_ = f"{slug_component}-{timestamp}" if slug_component else timestamp

    lesson_record = {
        "id": id_,
        "date": now.date().isoformat(),
        "category": category,
        "component": component,
        "tags": tags or [],
        "bug_description": bug_description,
        "what_went_wrong": what_went_wrong,
        "fix_description": fix_description,
    }

    with LESSONS_PATH.open("a+", encoding="utf-8") as fp:
        fcntl.flock(fp.fileno(), fcntl.LOCK_EX)
        fp.seek(0)
        for line in fp:
            try:
                existing = json.loads(line)
            except (json.JSONDecodeError, TypeError):
                continue
            identity = ("category", "component", "bug_description", "what_went_wrong")
            if all(existing.get(key) == lesson_record.get(key) for key in identity):
                return existing
        fp.seek(0, os.SEEK_END)
        fp.write(json.dumps(lesson_record, ensure_ascii=False) + "\n")
        fp.flush()
        os.fsync(fp.fileno())

    return lesson_record


def select_relevant(
    target_name: str,
    description: str,
    max_n: int = 3,
) -> List[Dict]:
    """
    Return top lessons based on keyword overlap with the target and description.
    Deterministic, no LLM involved.
    """
    target_base = os.path.splitext(target_name)[0]
    query_tokens = set(_tokenize(target_base + " " + description))

    scored: List[tuple] = []

    for lesson in load_lessons():
        # Extract relevant tokens
        component_toks = set(_tokenize(lesson.get("component", "")))
        tags_toks = set(_tokenize(" ".join(str(t) for t in lesson.get("tags", []))))
        bug_desc_toks = set(_tokenize(lesson.get("bug_description", "")))

        overlap = (
            3 * len(query_tokens & component_toks)
            + 2 * len(query_tokens & tags_toks)
            + len(query_tokens & bug_desc_toks)
        )

        if overlap > 0:
            scored.append((overlap, lesson))

    scored.sort(key=lambda x: -x[0])  # descending by score
    return [lesson for _, lesson in scored[:max_n]]


def format_lessons_for_prompt(lessons: List[Dict]) -> str:
    """Generate a Markdown prompt section from lessons."""
    if not lessons:
        return ""

    lines = ["## Known past mistakes on this project (do/don't)"]
    for l in lessons:
        dont = l.get("what_went_wrong", "")
        do_ = l.get("fix_description", "")
        lines.append(f"- **Don't:** {dont} **Do:** {do_}")
    return "\n".join(lines)


# CLI ---------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Manage lesson records."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Add command
    add_parser = subparsers.add_parser("add", help="Add a new lesson")
    add_parser.add_argument("--bug", required=True, help="Bug description")
    add_parser.add_argument(
        "--wrong",
        required=True,
        dest="what_went_wrong",
        help="What went wrong",
    )
    add_parser.add_argument(
        "--fix", required=True, dest="fix_description", help="Fix description"
    )
    add_parser.add_argument("--component", default="", help="Component name")
    add_parser.add_argument(
        "--category",
        choices=("bug_fix", "unresolved_pattern"),
        default="bug_fix",
    )
    add_parser.add_argument(
        "--tags",
        default="",
        help="Comma-separated tags (optional)",
    )

    args = parser.parse_args()

    if args.command == "add":
        tags = [t.strip() for t in args.tags.split(",") if t.strip()]
        lesson = add_lesson(
            bug_description=args.bug,
            what_went_wrong=args.what_went_wrong,
            fix_description=args.fix_description,
            category=args.category,
            component=args.component,
            tags=tags or None,
        )
        print(json.dumps(lesson, ensure_ascii=False, indent=2))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
