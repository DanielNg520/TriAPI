# Ghostwriter capability — brief plan

Status: queued, first in line (ahead of self-fix and good-vs-bad-code judgment).
Scope for this pass: basic working version only, no AI-detection/critique loop.
Goes through `triapi plan`/`triapi dispatch` against oh-my-llama's own repo —
not hand-implemented, per the standing supervisor rule.

## What it does

A folder-walk batch job, run on demand (CLI command or semAI intent, not a
background service). Given one job folder:

```
ghostwriter/<job-name>/
  sample/
    writing-guide.pdf
    writing-sample.pdf
  1.pdf
  2.png
  3.doc
  prompt.md
```

- `sample/` — any number of files defining voice/style (a guide + sample
  writing). All ingested and folded into one style profile.
- Numbered root-level files (`1.pdf`, `2.png`, `3.doc`, ...) — source material,
  one per prompt, matched by number.
- `prompt.md` — a numbered list (`1. ...`, `2. ...`); prompt N pairs with
  source file N.
- Output: one `result.txt` in the job folder, prompt outputs concatenated in
  order, clearly delimited (e.g. `--- 1 ---`). No genre restriction — the
  style profile plus per-prompt instruction is all that shapes it.

No AI-detector/revision loop in this pass — one pass per prompt, straight to
`result.txt`. User proofreads by hand.

## Reuse, don't rebuild

- **Ingestion**: `ohmyllama/capabilities/ingestion.py`'s `DocumentIngester`
  already handles PDF/DOC/XLSX/CSV via MarkItDown and routes images to a
  vision-model branch. Its `allowed_dirs` allowlist (`~/Downloads`,
  `~/Documents`) will need the ghostwriter job root added, or the check
  loosened for this capability specifically — flag as an explicit plan item,
  don't silently bypass the security check.
- **Vision**: `Config.model_vision` (moondream) already wired for image
  description — reuse for `2.png`-style inputs instead of a new vision path.
- **Worker shape**: `src/semai/workers/base.py` — this is a fixed-shape,
  low-blast-radius local write (writes one `result.txt` inside the job's own
  folder), same category the docstring gives for `remember_fact` — no
  approval-gate ABC needed, a plain function registered in `core.registry`
  is enough.

## New pieces

1. **Style-profile step**: one model call over the concatenated `sample/`
   ingested text, producing a reusable style summary (tone, sentence rhythm,
   vocabulary, quirks) — not re-fed as raw sample text on every prompt call,
   to keep later calls cheap.
2. **Per-prompt draft step**: for each numbered prompt, ingest its paired
   source file, call the heavy model once with (style profile + source
   content + prompt text), append result to `result.txt`.
3. **Folder-walk + pairing logic**: match `prompt.md`'s numbered list against
   root-level numbered files; a missing pair or gap in numbering should fail
   loudly (human-visible error), not silently skip.
4. **CLI/intent entry point**: `omll ghostwrite <job-folder>` or an
   equivalent semAI intent — whichever fits the current command surface more
   directly; decide at plan time by reading `ohmyllama/cli.py`'s current
   subcommand list.

## Model recommendation

Use **`model_heavy`** (already configured as `qwen3-coder:30b` per
`ohmyllama/config.py`) for both the style-profile step and the per-prompt
draft step — it's the only locally-resident model in this repo's roster
sized for long-form generative writing quality; `model_fast` is tuned for
triage/classification, not prose. If output quality on creative (non-code)
genres disappoints in proofreading, the next thing worth trying is swapping
in an Ollama-pullable general-purpose model better suited to prose than a
coder-tuned one (e.g. a Llama-3.1-70B-instruct-class or Mistral-Large-class
model, hardware permitting) via a dedicated `model_ghostwriter` role —
same pattern `model_vision`/`model_classify` already use — rather than
repurposing `model_heavy`'s coder-tuned weights long-term. Don't add a new
role speculatively in this pass; only introduce it if `model_heavy` proves
inadequate in practice.

## Explicitly out of scope this pass

- AI-detection / iterative critique-until-below-threshold loop (Binoculars
  or HF classifier) — deferred, per user instruction, to a later polish pass.
- Telegram delivery — deferred; file-write-only for now.
- Any approval/confirmation gate — not needed per the worker-shape reasoning
  above; revisit only if scope grows beyond a local file write.
