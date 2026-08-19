"""Static-analysis lint for mock.patch target/import binding mismatches.

Guards against the bug class where a test patches a dotted target such as
``scripts.orchestrator.run_task`` but the module actually under test imports
that name via a *different* binding path (e.g. ``dispatcher.py`` does
``from scripts.orchestrator import run_task``, a name-binding import that
copies the reference into ``dispatcher``'s own namespace). When the patch
target is the name's *defining* module instead of the *importing* module
where it's actually looked up at call time, ``mock.patch`` silently patches
a name nobody reads, the original (real) function stays live, and the test
passes while a real network call (or other real side effect) still fires in
production. Written after exactly that incident involving
``scripts.orchestrator.run_task`` / ``scripts.dispatcher.py``: a test mocked
the wrong module and a live Ollama network call slipped through undetected
for several rounds before being caught by a live 7+ minute hang. See
``content_guard.py`` and ``regression_guard.py`` for the header/docstring
style this module follows.
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path


def _resolve_module_and_attr(dotted: str, repo_root: Path) -> tuple[str, str] | None:
    """Find the longest dotted prefix of `dotted` that resolves to an
    existing `repo_root/<prefix>.py` file, returning (module, attr) where
    attr is the single remaining trailing component. Returns None if no
    such prefix exists or more than one trailing component remains."""
    parts = dotted.split(".")
    for i in range(len(parts) - 1, 0, -1):
        candidate = repo_root.joinpath(*parts[:i]).with_suffix(".py")
        if candidate.is_file():
            trailing = parts[i:]
            if len(trailing) == 1:
                return ".".join(parts[:i]), trailing[0]
            return None
    return None


def _top_level_imports(module_path: Path) -> list[dict]:
    """Module-load-time `from X import Y` imports only (top-level, absolute)."""
    tree = ast.parse(module_path.read_text(), filename=str(module_path))
    imports = []
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module and not node.level:
            bound_names = {(alias.asname or alias.name): alias.name for alias in node.names}
            imports.append({"module": node.module, "bound_names": bound_names})
    return imports


def _is_patch_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
        return False
    if node.func.attr == "patch":
        return True
    if node.func.attr == "object" and isinstance(node.func.value, ast.Attribute):
        return node.func.value.attr == "patch"
    return False


def _extract_patch_targets_by_function(tree: ast.Module) -> dict[ast.AST, list[dict]]:
    """Find @mock.patch("dotted.string") / mock.patch.object(...) calls used
    as decorators or `with` items, grouped by the enclosing function node.
    Returns {function_node: [{"target": str, "lineno": int}, ...]}."""
    targets_by_func: dict[ast.AST, list[dict]] = {}

    def _record(func_node: ast.AST, node: ast.AST) -> None:
        if not _is_patch_call(node) or not node.args:
            return
        first = node.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            targets_by_func.setdefault(func_node, []).append(
                {"target": first.value, "lineno": node.lineno}
            )

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for dec in node.decorator_list:
                _record(node, dec)
            for inner in ast.walk(node):
                if isinstance(inner, ast.With):
                    for item in inner.items:
                        _record(node, item.context_expr)
    return targets_by_func


def _local_name_to_module(test_file: Path, repo_root: Path) -> dict[str, str]:
    """Map each name the test file's top-level imports bind locally (e.g.
    "dispatcher" from `from scripts import dispatcher`, or "d" from
    `import scripts.dispatcher as d`) to its dotted module path, for
    modules that resolve to a real repo file."""
    tree = ast.parse(test_file.read_text(), filename=str(test_file))
    mapping: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module and not node.level:
            for alias in node.names:
                local = alias.asname or alias.name
                dotted = f"{node.module}.{alias.name}"
                if repo_root.joinpath(*dotted.split(".")).with_suffix(".py").is_file():
                    mapping[local] = dotted
                elif repo_root.joinpath(*node.module.split(".")).with_suffix(".py").is_file():
                    mapping[local] = node.module
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if repo_root.joinpath(*alias.name.split(".")).with_suffix(".py").is_file():
                    mapping[alias.asname or alias.name.split(".")[0]] = alias.name
    return mapping


def _modules_called_in_function(func_node: ast.AST, name_to_module: dict[str, str]) -> set[str]:
    """Modules actually invoked as `module_name.something(...)` inside this
    specific test function -- scoped to just this function, not the whole
    file, so an unrelated test class's import style never cross-contaminates
    a different test's patch-target check."""
    called: set[str] = set()
    for node in ast.walk(func_node):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            base = node.func.value
            if isinstance(base, ast.Name) and base.id in name_to_module:
                called.add(name_to_module[base.id])
    return called


def find_issues(test_file: Path, repo_root: Path, search_dirs: list[str] = ["scripts"]) -> list[dict]:
    """Flag mock.patch targets whose module doesn't match how the module(s)
    actually called *within that same test function* reach that name.
    search_dirs is accepted for CLI-compatibility; candidates resolve from
    repo_root directly."""
    issues: list[dict] = []
    tree = ast.parse(test_file.read_text(), filename=str(test_file))
    targets_by_func = _extract_patch_targets_by_function(tree)
    if not targets_by_func:
        return issues

    name_to_module = _local_name_to_module(test_file, repo_root)

    for func_node, patch_targets in targets_by_func.items():
        called_modules = _modules_called_in_function(func_node, name_to_module)
        if not called_modules:
            continue  # can't scope confidently -- skip rather than false-flag

        for pt in patch_targets:
            resolved = _resolve_module_and_attr(pt["target"], repo_root)
            if resolved is None:
                continue
            patched_module, attr = resolved
            if patched_module in called_modules:
                continue  # patched module is itself directly called here -- correct

            for other_module in called_modules:
                other_path = repo_root.joinpath(*other_module.split(".")).with_suffix(".py")
                if not other_path.is_file():
                    continue
                for imp in _top_level_imports(other_path):
                    if imp["module"] == patched_module and attr in imp["bound_names"].values():
                        correct = [
                            f"{other_module}.{bound}"
                            for bound, orig in imp["bound_names"].items()
                            if orig == attr
                        ]
                        issues.append({
                            "lineno": pt["lineno"],
                            "wrong_target": f"{patched_module}.{attr}",
                            "correct_targets": correct,
                            "message": (
                                f'mock.patch("{patched_module}.{attr}") patches where the name is '
                                f"defined, but {other_module} (called in this test) imports it via "
                                f"`from {patched_module} import {attr}` -- patch "
                                f'"{correct[0]}" instead, where it is actually looked up at call time.'
                            ),
                        })
    return issues


def format_issues(issues: list[dict]) -> str:
    return "\n".join(f"line {i['lineno']}: {i['message']}" for i in issues)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check for name-binding-import mismatches causing unmocked real network calls."
    )
    parser.add_argument("test_file", type=str)
    parser.add_argument(
        "--repo-root", type=str, default=str(Path(__file__).resolve().parent.parent)
    )
    parser.add_argument("--search-dirs", nargs="+", default=["scripts"])
    args = parser.parse_args(argv)

    issues = find_issues(Path(args.test_file), Path(args.repo_root), args.search_dirs)
    if issues:
        sys.stderr.write(format_issues(issues) + "\n")
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
