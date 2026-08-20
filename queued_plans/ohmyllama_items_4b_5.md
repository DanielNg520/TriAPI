# Queued plan — CARRYOVER items #4b + #5 (oh-my-llama)

**Status: prompt drafted, `triapi plan` never run against it yet.** No
plan text to review here — the prompt itself was reviewed carefully
(covers the `test_dep_triage_seam.py` stale-`webui.py` fix and the
`AGENTS.md` deep-clean + final doc write-up), but generation was
interrupted before launch.

## To resume

```
cd ~/Documents/Coding/TriAPI
PROMPT="$(cat queued_plans/ohmyllama_items_4b_5_prompt.txt)"
python3 scripts/triapi.py plan --project-dir /home/dyne/Documents/Coding/oh-my-llama "$PROMPT"
```

Review the generated plan for real (it's untested — this is the first
time it'll actually run) before approving. Two things to watch for
specifically, given tonight's track record:

- The `AGENTS.md` pruning item touches an oversized file
  (`_enforce_no_raw_edits_to_encrypted_files`/`_enforce_file_size_ceiling`
  guards will mark it `skip_tier4` automatically — that's expected and
  fine, not a bug).
- Do **not** let this plan attempt to split `ohmyllama/state.py` again —
  the prompt explicitly forbids it, but double-check the generated plan
  respects that (see `CARRYOVER.md` item #4c for why).
- `ohmyllama/webui.py` is an **uncommitted** `git status` deletion (`D`,
  still tracked, last real content at commit `2a1e974`), not a file
  that's actually gone from history — the prompt now asks the plan to
  investigate real importers and either restore it or finalize the
  deletion with `git rm` before touching `test_dep_triage_seam.py`. Make
  sure the generated plan actually does that investigation rather than
  just assuming the file is meant to be gone.

The exact prompt is in `ohmyllama_items_4b_5_prompt.txt` next to this
file.
