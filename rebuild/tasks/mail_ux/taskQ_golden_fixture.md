File: `/home/dyne/Documents/Coding/SemAI/tests/fixtures/intents.jsonl`

This is a JSONL golden-intent fixture (one JSON object per line) used by
`tests/test_golden_intents_seam.py`, which requires every declared intent kind to have at least 5
labeled examples. Two new kinds were just added to `semai.core.intents` (`summarize_mail`,
`create_google_task`, both with a single field `msg_id: str`) and currently have zero examples,
failing that check.

Existing examples for the most similar kind, `get_mail_full` (same shape: `msg_id` field, varied
phrasing of "give me this email"):

```
{"id": "synth-getmail-1", "source": "cli", "raw_utterance": "get full content for email 12345", "kind": "get_mail_full", "confidence": 0.9, "msg_id": "12345"}
{"id": "synth-getmail-2", "source": "cli", "raw_utterance": "show me the whole email abcde", "kind": "get_mail_full", "confidence": 0.9, "msg_id": "abcde"}
{"id": "synth-getmail-3", "source": "cli", "raw_utterance": "fetch message body 999", "kind": "get_mail_full", "confidence": 0.9, "msg_id": "999"}
{"id": "synth-getmail-4", "source": "cli", "raw_utterance": "download full mail XXXXX", "kind": "get_mail_full", "confidence": 0.9, "msg_id": "XXXXX"}
{"id": "synth-getmail-5", "source": "cli", "raw_utterance": "display entire message 123", "kind": "get_mail_full", "confidence": 0.9, "msg_id": "123"}
```

Task: write 5 new lines for `kind: "summarize_mail"` (varied natural phrasings of "give me a summary
of this email", ids `synth-summarizemail-1`..`5`) and 5 new lines for `kind: "create_google_task"`
(varied natural phrasings of "turn this email into a task"/"add this to my tasks", ids
`synth-googletask-1`..`5`), same JSON shape as the examples above (`id`, `source`: `"cli"`, `raw_utterance`,
`kind`, `confidence`: `0.9`, `msg_id`: any plausible placeholder id string, varied per line like the
examples above do).

Reply with ONLY the 10 new JSONL lines (one JSON object per line, no surrounding array/brackets), no
other text.
