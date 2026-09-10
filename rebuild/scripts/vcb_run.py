import argparse
import sys
from pathlib import Path

from scripts.vcb_slicer import build_skeleton
from scripts.vcb_materializer import materialize
from scripts.vcb_planner_call import make_planner_call_fn
from scripts.vcb_deepseek_call import make_deepseek_call_fn


def build_planner_prompt(skeleton: str, task_description: str) -> str:
    return f"""You are the Planner role acting as a local drafter over a code skeleton.

TASK DESCRIPTION:
{task_description}

CODE SKELETON:
{skeleton}

INSTRUCTIONS:
- Draft correctness-focused logic only for the target function/method.
- Formatting, style, and exact integration into the real file do not matter here; a separate cloud model will later integrate this draft into the real file.
- Do not repeat the other symbols' signatures back; only draft the target function/method's new body.
"""


def run_vcb(
    repo_path: str,
    file_path: str,
    target_symbol: str,
    task_description: str,
    planner_call_fn,
    materializer_call_fn,
) -> tuple[str | None, str]:
    skeleton = build_skeleton(repo_path, file_path, target_symbol)
    prompt = build_planner_prompt(skeleton, task_description)
    skeleton_draft = planner_call_fn(prompt)
    with open(file_path) as f:
        file_content = f.read()
    return materialize(file_path, file_content, skeleton_draft, task_description, materializer_call_fn)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-path", required=True)
    parser.add_argument("--file-path", required=True)
    parser.add_argument("--target-symbol", required=True)
    parser.add_argument("--task-description")
    parser.add_argument("--task-description-file", type=Path)
    parser.add_argument("--planner-system-file", required=True)
    parser.add_argument("--planner-task-id", default="vcb_planner")
    parser.add_argument("--materializer-task-id", default="vcb_materializer")
    args = parser.parse_args()

    if (args.task_description is None) == (args.task_description_file is None):
        print("Specify exactly one of --task-description or --task-description-file", file=sys.stderr)
        return 2

    if args.task_description_file is not None:
        task_description = args.task_description_file.read_text()
    else:
        task_description = args.task_description

    planner_call_fn = make_planner_call_fn(args.planner_task_id, args.planner_system_file)
    materializer_call_fn = make_deepseek_call_fn(args.materializer_task_id)

    new_content, error = run_vcb(
        args.repo_path,
        args.file_path,
        args.target_symbol,
        task_description,
        planner_call_fn,
        materializer_call_fn,
    )

    if error:
        print(error, file=sys.stderr)
        return 1

    print(new_content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
