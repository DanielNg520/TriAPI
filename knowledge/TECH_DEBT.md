# Tech Debt

Fixes `handle_fix_forward` gave up on after a single Tier 3 attempt failed to rebuild. Tier 3 is in DeepSeek peak billing hours 01:00-04:00 UTC (LA local 2026-08-18T20:59:37.361917-07:00, UTC 2026-08-19T03:59:37.361917+00:00). Each entry's HASH is the file's SHA-256 at the moment it was logged; if the file has since changed, treat the entry as STALE.

- [ ] FILE: /home/dyne/Documents/Coding/TriAPI/scripts/config_loader.py | HASH: 45eb587e61195582560e1730ee288c773d66be31980d82504c71dd8c64e6e765 | REASON: Could not apply proposed edit: No SEARCH/REPLACE blocks found in the response.
- [ ] FILE: /home/dyne/Documents/Coding/TriAPI/tests/test_llm_client_sanitize.py | HASH: b5500a9d2ac3532869f9a6bfe469821ffa284434bb6b6bf98094f2213001b231 | REASON: Could not apply proposed edit: No SEARCH/REPLACE blocks found in the response.
- [ ] FILE: /home/dyne/Documents/Coding/TriAPI/tests/test_run_build_pipefail.py | HASH: 4f5e3fba9b580482393ec0a4c8f530a5839d912f18badecf1f168d75d5c57b2a | REASON: Could not apply proposed edit: No SEARCH/REPLACE blocks found in the response.
- [ ] FILE: /home/dyne/Documents/Coding/TriAPI/tests/test_tier5_librarian.py | HASH: df0b962e57db330d750f8a7c45f300f870ee35221e0cc5afe1583e47085095ed | REASON: Could not apply proposed edit: No SEARCH/REPLACE blocks found in the response.
- [ ] FILE: /home/dyne/Documents/Coding/oh-my-llama/src/semai/capabilities/browser.py | HASH: 7fe26fc593fcde23d04bd360f91664078a96c6b9d1ded590f23f747f963de33a | REASON: Could not apply proposed edit: Block 2: SEARCH text matches 3 locations in the file -- ambiguous, needs more surrounding context to be unique.
- [ ] FILE: /home/dyne/Documents/Coding/oh-my-llama/src/semai/config.py | HASH: 8ee0cff5fc8c89a7c6b4543aad5792aa9a4d4e4e6ea0b72785741402207f98f2 | REASON: Could not apply proposed edit: No SEARCH/REPLACE blocks found in the response.
- [ ] FILE: /home/dyne/Documents/Coding/oh-my-llama/src/semai/providers/ollama.py | HASH: 0ea1189f5840649c2142beb4a0bc1f7e45d8ec7b4ef97b8fdc8f17f016c1a155 | REASON: Could not apply proposed edit: Block 1: SEARCH text not found verbatim in the current file.
- [ ] FILE: /home/dyne/Documents/Coding/oh-my-llama/src/semai/providers/ollama.py | HASH: 6cade7bf4aef6bc83546ba3f982a32e95eaa134819c97edef7c2544982ef24f6 | REASON: Could not apply proposed edit: No SEARCH/REPLACE blocks found in the response.
- [ ] FILE: /home/dyne/Documents/Coding/TriAPI/scripts/orchestrator.py | HASH: 3011d2fe2ea1832cbf50d68c147016e3f2a0979f5c5dc61db1967f2b7fdbbbf8 | REASON: Rebuild failed after Tier 3 rewrite: 
