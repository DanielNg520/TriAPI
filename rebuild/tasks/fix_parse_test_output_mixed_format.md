Bug found live: `parse_test_output(output)` in `scripts/verify.py` checks for a unittest-style `"Ran N tests"` summary FIRST and returns immediately if found — but a wrapping test script (e.g. one that runs several unittest-style sub-suites, THEN a final pytest run) can print an early "Ran N tests" line from an unrelated sub-suite, followed later by the real, authoritative pytest summary ("114 passed" etc). The current function returns on the first match and never even looks at the real final summary — meaning real pytest failures later in the output would go completely undetected and get reported as a pass.

Current function:
```python
def parse_test_output(output: str) -> dict[str, int]:
    ran = re.search(r'\bRan\s+(\d+)\s+tests?\b', output)
    if ran:
        total_run = int(ran.group(1))
        failures = errors = skipped = 0
        for kind, value in re.findall(r'\b(failures|errors|skipped)=(\d+)', output):
            if kind == "failures":
                failures = int(value)
            elif kind == "errors":
                errors = int(value)
            else:
                skipped = int(value)
        passed = max(0, total_run - failures - errors - skipped)
        return {
            "passed": passed,
            "failed": failures,
            "errors": errors,
            "skipped": skipped,
            "total_executed": passed + failures + errors,
        }

    counts = {"passed": 0, "failed": 0, "errors": 0, "skipped": 0}
    for count, kind in re.findall(r'\b(\d+)\s+(passed|failed|errors?|skipped)\b', output):
        count = int(count)
        if kind == "passed":
            counts["passed"] += count
        elif kind == "failed":
            counts["failed"] += count
        elif kind in {"error", "errors"}:
            counts["errors"] += count
        elif kind == "skipped":
            counts["skipped"] += count
    counts["total_executed"] = counts["passed"] + counts["failed"] + counts["errors"]
    return counts
```

Fix requirement: instead of "unittest format always wins if present anywhere", pick whichever format's summary appears LAST (closer to the end of the string) as authoritative — that's the real final result of a wrapping script. Specifically:
- Find the LAST match of `\bRan\s+(\d+)\s+tests?\b` (if any), note its start position.
- Separately, find whether the pytest-style `\b(\d+)\s+(passed|failed|errors?|skipped)\b` pattern has any matches; if so, note the start position of its LAST match.
- If only one format has any match, use that format's existing logic (unchanged from above).
- If both formats have matches, use whichever format's LAST match has the greater (later) start position — treat that as authoritative and ignore the other format's matches entirely for this call.
- If neither format matches anything, return all zeros (passed=0, failed=0, errors=0, skipped=0, total_executed=0) — same as today's implicit behavior via the empty-findall fallback.
- Keep both individual format-parsing algorithms exactly as they are today (unittest: `Ran N tests` minus failures/errors/skipped via `kind=value` pairs; pytest: sum of `N (passed|failed|errors?|skipped)` occurrences) — only change which one gets chosen when both are present.

Reply with the complete corrected `parse_test_output` function in a single fenced python block. Same signature, same return shape, same two counting algorithms — only the selection logic changes.
