# Tech Debt

Fixes `handle_fix_forward` gave up on after a single Tier 3 attempt failed to rebuild. Tier 3 is in DeepSeek peak billing hours 01:00-04:00 UTC (LA local 2026-08-18T20:59:37.361917-07:00, UTC 2026-08-19T03:59:37.361917+00:00). Each entry's HASH is the file's SHA-256 at the moment it was logged; if the file has since changed, treat the entry as STALE.

- [ ] FILE: /home/dyne/Documents/Coding/TriAPI/tests/test_branch_features.py | HASH: 7cf20d6c26791bfae695b6493d2aed208906f52e0f379d7107dc7295b497add8 | REASON: Rebuild failed after Tier 3 rewrite: [Phase 1] (1/1) Test task
[Phase 1] (1/1) Test task
[Phase 1] (1/1) Test task
[HUMAN HANDOFF] Task 't1' needs manual review: reason
[HUMAN HANDOFF] See /tmp/tmp280xqr_t/escalation_t1.md
test_append_creates_file_with_header (tests.test_branch_features.AgentsMdGateTests.test_append_creates_file_with_header) ... ok
test_append_then_find_incomplete (tests.test_branch_features.AgentsMdGateTests.test_append_then_find_incomplete) ... ok
test_block_with_no_checkboxes_is_not_blocking (tests.test_branch_features.AgentsMdGateTests.test_block_with_no_checkboxes_is_not_blocking) ... ok
test_mark_plan_complete_clears_gate (tests.test_branch_features.AgentsMdGateTests.test_mark_plan_complete_clears_gate) ... ok
test_mark_plan_complete_unknown_run_is_noop (tests.test_branch_features.AgentsMdGateTests.test_mark_plan_complete_unknown_run_is_noop) ... ok
test_no_agents_md_means_no_incomplete_plan (tests.test_branch_features.AgentsMdGateTests.test_no_agents_md_means_no_incomplete_plan) ... ok
test_only_most_recent_block_gates (tests.test_branch_features.AgentsMdGateTests.test_only_most_recent_block_gates) ... ok
test_jules_test_dispatched_when_budget_ok_and_push_succeeds (tests.test_branch_features.BreakdownDispatchJulesHookTests.test_jules_test_dispatched_when_budget_ok_and_push_succeeds) ... ok
test_jules_test_skipped_when_budget_check_refuses (tests.test_branch_features.BreakdownDispatchJulesHookTests.test_jules_test_skipped_when_budget_check_refuses) ... ok
test_jules_test_skipped_when_push_fails (tests.test_branch_features.BreakdownDispatchJulesHookTests.test_jules_test_skipped_when_push_fails) ... ok
test_at_limit_refuses (tests.test_branch_features.CheckJulesOkTests.test_at_limit_refuses) ... ok
test_under_limit_reports_ok (tests.test_branch_features.CheckJulesOkTests.test_under_limit_reports_ok) ... ok
test_refactor_flag_bypasses_gate (tests.test_branch_features.CmdPlanRefactorGateTests.test_refactor_flag_bypasses_gate) ... ok
test_refuses_when_incomplete_plan_exists (tests.test_branch_features.CmdPlanRefactorGateTests.test_refuses_when_incomplete_plan_exists) ... ok
test_bad_score_is_advisory_error (tests.test_branch_features.CritiqueTests.test_bad_score_is_advisory_error) ... ok
test_critique_tokens_are_included_in_run_summary (tests.test_branch_features.CritiqueTests.test_critique_tokens_are_included_in_run_summary) ... ok
test_failed_revision_reverts_passing_content (tests.test_branch_features.CritiqueTests.test_failed_revision_reverts_passing_content) ... ok
test_invalid_numeric_config_skips_critique (tests.test_branch_features.CritiqueTests.test_invalid_numeric_config_skips_critique) ... ok
test_max_revision_attempts_retries_after_failed_apply (tests.test_branch_features.CritiqueTests.test_max_revision_attempts_retries_after_failed_apply) ... ok
test_revision_exception_keeps_passing_content (tests.test_branch_features.CritiqueTests.test_revision_exception_keeps_passing_content) ... ok
test_threshold_and_string_issue_normalization (tests.test_branch_features.CritiqueTests.test_threshold_and_string_issue_normalization) ... ok
test_zero_revision_attempts_still_scores_but_does_not_revise (tests.test_branch_features.CritiqueTests.test_zero_revision_attempts_still_scores_but_does_not_revise) ... ok
test_handle_fix_forward_failed_rebuild (tests.test_branch_features.DispatcherHookAndFixForwardTests.test_handle_fix_forward_failed_rebuild) ... FAIL
test_handle_fix_forward_successful_rebuild (tests.test_branch_features.DispatcherHookAndFixForwardTests.test_handle_fix_forward_successful_rebuild) ... ok
test_peak_hours_skipped_judge_passes_open_calls_extract_pattern (tests.test_branch_features.DispatcherHookAndFixForwardTests.test_peak_hours_skipped_judge_passes_open_calls_extract_pattern) ... ERROR
test_successful_item_failing_judge_calls_handle_fix_forward (tests.test_branch_features.DispatcherHookAndFixForwardTests.test_successful_item_failing_judge_calls_handle_fix_forward) ... ERROR
test_successful_item_passing_judge_calls_extract_pattern (tests.test_branch_features.DispatcherHookAndFixForwardTests.test_successful_item_passing_judge_calls_extract_pattern) ... ERROR
test_create_session_request_exception_returns_error (tests.test_branch_features.JulesClientErrorTests.test_create_session_request_exception_returns_error) ... ok
test_missing_api_key_short_circuits (tests.test_branch_features.JulesClientUnavailableTests.test_missing_api_key_short_circuits) ... ok
test_parses_real_confirmed_live_activity_shape (tests.test_branch_features.JulesGetFinalMessageTests.test_parses_real_confirmed_live_activity_shape) ... ok
test_failed_state_returns_failed_status (tests.test_branch_features.JulesPollResultFailedTests.test_failed_state_returns_failed_status) ... ok
test_completed_state_returns_ok_summary (tests.test_branch_features.JulesPollResultOkTests.test_completed_state_returns_ok_summary) ... ok
test_nonterminal_state_past_deadline_returns_timeout (tests.test_branch_features.JulesPollResultTimeoutTests.test_nonterminal_state_past_deadline_returns_timeout) ... ok
test_add_lesson_deduplicates_and_selection_avoids_extension_noise (tests.test_branch_features.LessonsTests.test_add_lesson_deduplicates_and_selection_avoids_extension_noise) ... ok
test_handoff_writes_runtime_store_not_committed_lessons (tests.test_branch_features.LessonsTests.test_handoff_writes_runtime_store_not_committed_lessons) ... ok
test_malformed_lines_are_skipped (tests.test_branch_features.LessonsTests.test_malformed_lines_are_skipped) ... ok
test_select_relevant_skips_unresolved_pattern (tests.test_branch_features.LessonsTests.test_select_relevant_skips_unresolved_pattern) ... ok
test_run_task_calls_tier3_escalate_when_peak_hours_ok (tests.test_branch_features.OrchestratorTier3PeakSkipTests.test_run_task_calls_tier3_escalate_when_peak_hours_ok) ... ok
test_run_task_falls_through_to_tier1_when_tier3_skipped_and_tier2_fails (tests.test_branch_features.OrchestratorTier3PeakSkipTests.test_run_task_falls_through_to_tier1_when_tier3_skipped_and_tier2_fails) ... ok
test_run_task_skips_tier3_escalate_when_peak_hours_not_ok (tests.test_branch_features.OrchestratorTier3PeakSkipTests.test_run_task_skips_tier3_escalate_when_peak_hours_not_ok) ... ok
test_approve_flips_drafted_run_to_planned (tests.test_branch_features.SelfFixTests.test_approve_flips_drafted_run_to_planned) ... ok
test_bad_config_during_crash_recovery_does_not_mask_original (tests.test_branch_features.SelfFixTests.test_bad_config_during_crash_recovery_does_not_mask_original) ... ok
test_capture_crash_writes_structured_report (tests.test_branch_features.SelfFixTests.test_capture_crash_writes_structured_report) ... ok
test_capture_failure_never_raises (tests.test_branch_features.SelfFixTests.test_capture_failure_never_raises) ... ok
test_dispatch_resumes_services_before_auto_queue_and_reraises (tests.test_branch_features.SelfFixTests.test_dispatch_resumes_services_before_auto_queue_and_reraises) ... ok
test_draft_prompt_names_triapi_source_file (tests.test_branch_features.SelfFixTests.test_draft_prompt_names_triapi_source_file) ... ok
test_import_does_not_replace_excepthook (tests.test_branch_features.SelfFixTests.test_import_does_not_replace_excepthook) ... ok
test_list_shows_unqueued_bug_stems (tests.test_branch_features.SelfFixTests.test_list_shows_unqueued_bug_stems) ... ok
test_queue_always_targets_triapi_root (tests.test_branch_features.SelfFixTests.test_queue_always_targets_triapi_root) ... ok
test_relative_source_files_resolve_against_repo_root_not_cwd (tests.test_branch_features.SelfFixTests.test_relative_source_files_resolve_against_repo_root_not_cwd) ... ok
test_self_fix_marker_skips_auto_queue (tests.test_branch_features.SelfFixTests.test_self_fix_marker_skips_auto_queue) ... ok
test_show_ignores_bug_report_outside_bugs_dir (tests.test_branch_features.SelfFixTests.test_show_ignores_bug_report_outside_bugs_dir) ... ok
test_triapi_rooted_run_without_marker_still_auto_queues (tests.test_branch_features.SelfFixTests.test_triapi_rooted_run_without_marker_still_auto_queues) ... ok
test_mid_off_peak_hour_passes (tests.test_branch_features.Tier3PeakHoursTests.test_mid_off_peak_hour_passes) ... ok
test_mid_second_peak_window_refuses (tests.test_branch_features.Tier3PeakHoursTests.test_mid_second_peak_window_refuses) ... ok
test_start_of_first_peak_window_refuses (tests.test_branch_features.Tier3PeakHoursTests.test_start_of_first_peak_window_refuses) ... ok
test_unload_models_get_exception_returns_empty (tests.test_branch_features.UnloadOllamaModelsTests.test_unload_models_get_exception_returns_empty) ... ok
test_unload_models_partial_failure (tests.test_branch_features.UnloadOllamaModelsTests.test_unload_models_partial_failure) ... ok
test_unload_models_successful (tests.test_branch_features.UnloadOllamaModelsTests.test_unload_models_successful) ... ok

======================================================================
ERROR: test_peak_hours_skipped_judge_passes_open_calls_extract_pattern (tests.test_branch_features.DispatcherHookAndFixForwardTests.test_peak_hours_skipped_judge_passes_open_calls_extract_pattern)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/usr/lib64/python3.14/unittest/mock.py", line 1439, in patched
    return func(*newargs, **newkeywargs)
  File "/home/dyne/Documents/Coding/TriAPI/tests/test_branch_features.py", line 1322, in test_peak_hours_skipped_judge_passes_open_calls_extract_pattern
    dispatcher.dispatch(state)
    ~~~~~~~~~~~~~~~~~~~^^^^^^^
  File "/home/dyne/Documents/Coding/TriAPI/scripts/dispatcher.py", line 833, in dispatch
    result = run_task(
        task_id=task_id,
    ...<4 lines>...
        context_files=item.get("context_files") or [],
    )
  File "/home/dyne/Documents/Coding/TriAPI/scripts/orchestrator.py", line 333, in run_task
    result3 = tier3_escalate(
        task_id, resolved_target, context_blob=context_blob, description=description
    )
  File "/home/dyne/Documents/Coding/TriAPI/scripts/tier3_escalate.py", line 164, in escalate
    secrets = load_secrets()
  File "/home/dyne/Documents/Coding/TriAPI/scripts/secrets_loader.py", line 34, in load_secrets
    secrets = json.loads(result.stdout)
  File "/usr/lib64/python3.14/json/__init__.py", line 352, in loads
    return _default_decoder.decode(s)
           ~~~~~~~~~~~~~~~~~~~~~~~^^^
  File "/usr/lib64/python3.14/json/decoder.py", line 345, in decode
    obj, end = self.raw_decode(s, idx=_w(s, 0).end())
               ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib64/python3.14/json/decoder.py", line 363, in raw_decode
    raise JSONDecodeError("Expecting value", s, err.value) from None
json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)

======================================================================
ERROR: test_successful_item_failing_judge_calls_handle_fix_forward (tests.test_branch_features.DispatcherHookAndFixForwardTests.test_successful_item_failing_judge_calls_handle_fix_forward)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/usr/lib64/python3.14/unittest/mock.py", line 1439, in patched
    return func(*newargs, **newkeywargs)
  File "/home/dyne/Documents/Coding/TriAPI/tests/test_branch_features.py", line 1279, in test_successful_item_failing_judge_calls_handle_fix_forward
    dispatcher.dispatch(state)
    ~~~~~~~~~~~~~~~~~~~^^^^^^^
  File "/home/dyne/Documents/Coding/TriAPI/scripts/dispatcher.py", line 833, in dispatch
    result = run_task(
        task_id=task_id,
    ...<4 lines>...
        context_files=item.get("context_files") or [],
    )
  File "/home/dyne/Documents/Coding/TriAPI/scripts/orchestrator.py", line 333, in run_task
    result3 = tier3_escalate(
        task_id, resolved_target, context_blob=context_blob, description=description
    )
  File "/home/dyne/Documents/Coding/TriAPI/scripts/tier3_escalate.py", line 164, in escalate
    secrets = load_secrets()
  File "/home/dyne/Documents/Coding/TriAPI/scripts/secrets_loader.py", line 34, in load_secrets
    secrets = json.loads(result.stdout)
  File "/usr/lib64/python3.14/json/__init__.py", line 352, in loads
    return _default_decoder.decode(s)
           ~~~~~~~~~~~~~~~~~~~~~~~^^^
  File "/usr/lib64/python3.14/json/decoder.py", line 345, in decode
    obj, end = self.raw_decode(s, idx=_w(s, 0).end())
               ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib64/python3.14/json/decoder.py", line 363, in raw_decode
    raise JSONDecodeError("Expecting value", s, err.value) from None
json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)

======================================================================
ERROR: test_successful_item_passing_judge_calls_extract_pattern (tests.test_branch_features.DispatcherHookAndFixForwardTests.test_successful_item_passing_judge_calls_extract_pattern)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/usr/lib64/python3.14/unittest/mock.py", line 1439, in patched
    return func(*newargs, **newkeywargs)
  File "/home/dyne/Documents/Coding/TriAPI/tests/test_branch_features.py", line 1236, in test_successful_item_passing_judge_calls_extract_pattern
    dispatcher.dispatch(state)
    ~~~~~~~~~~~~~~~~~~~^^^^^^^
  File "/home/dyne/Documents/Coding/TriAPI/scripts/dispatcher.py", line 833, in dispatch
    result = run_task(
        task_id=task_id,
    ...<4 lines>...
        context_files=item.get("context_files") or [],
    )
  File "/home/dyne/Documents/Coding/TriAPI/scripts/orchestrator.py", line 333, in run_task
    result3 = tier3_escalate(
        task_id, resolved_target, context_blob=context_blob, description=description
    )
  File "/home/dyne/Documents/Coding/TriAPI/scripts/tier3_escalate.py", line 164, in escalate
    secrets = load_secrets()
  File "/home/dyne/Documents/Coding/TriAPI/scripts/secrets_loader.py", line 34, in load_secrets
    secrets = json.loads(result.stdout)
  File "/usr/lib64/python3.14/json/__init__.py", line 352, in loads
    return _default_decoder.decode(s)
           ~~~~~~~~~~~~~~~~~~~~~~~^^^
  File "/usr/lib64/python3.14/json/decoder.py", line 345, in decode
    obj, end = self.raw_decode(s, idx=_w(s, 0).end())
               ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib64/python3.14/json/decoder.py", line 363, in raw_decode
    raise JSONDecodeError("Expecting value", s, err.value) from None
json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)

======================================================================
FAIL: test_handle_fix_forward_failed_rebuild (tests.test_branch_features.DispatcherHookAndFixForwardTests.test_handle_fix_forward_failed_rebuild)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/usr/lib64/python3.14/unittest/mock.py", line 1439, in patched
    return func(*newargs, **newkeywargs)
  File "/home/dyne/Documents/Coding/TriAPI/tests/test_branch_features.py", line 1425, in test_handle_fix_forward_failed_rebuild
    self.assertEqual(self.target_file.read_text(encoding="utf-8"), "original content\n")
    ~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: 'tier 3 rewrite\n' != 'original content\n'
- tier 3 rewrite
+ original content


----------------------------------------------------------------------
Ran 59 tests in 37.530s

FAILED (failures=1, errors=3)

- [ ] FILE: /home/dyne/Documents/Coding/TriAPI/CARRYOVER.md | HASH: 11d1b6ed4fed70e82df2a4950a4a6290c20435642505768b91b801ebcda92fa2 | REASON: Could not apply proposed edit: Block 1: SEARCH text not found verbatim in the current file.
- [ ] FILE: /home/dyne/Documents/Coding/TriAPI/CARRYOVER.md | HASH: 7ab25834239af794cc73a36427a1d681f4a83b11ccfe547ac754ef93c8ef015f | REASON: Rebuild failed after Tier 3 rewrite: 86:  extension of the context_files grounding guard (#1 above), user

- [ ] FILE: /home/dyne/Documents/Coding/TriAPI/AGENTS.md | HASH: ca7d25447ba7ffa43d5541357206cd8ad5ac572d2a034bb9f7920b58f835c9fe | REASON: Could not apply proposed edit: Block 1: SEARCH text not found verbatim in the current file.
- [ ] FILE: /home/dyne/Documents/Coding/oh-my-llama/ohmyllama/orchestrator.py | HASH: c4a29fcba69ca3dc781fdb3bf87674fcd46f70d95d3fd0c029024ce3b36c2f04 | REASON: Rebuild failed after Tier 3 rewrite: ============================= test session starts ==============================
platform linux -- Python 3.13.14, pytest-9.1.1, pluggy-1.6.0
rootdir: /home/dyne/Documents/Coding/oh-my-llama
configfile: pyproject.toml
plugins: anyio-4.14.2, asyncio-1.4.0
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 18 items

tests/test_orchestrator.py FFF...............                            [100%]

=================================== FAILURES ===================================
_______________ test_model_for_primary_reachable_not_quarantined _______________

    def test_model_for_primary_reachable_not_quarantined():
>       assert _model_for_heavy(set()) == "gpt-oss:20b"
               ^^^^^^^^^^^^^^^^^^^^^^^

tests/test_orchestrator.py:232: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

quarantined = set()

    def _model_for_heavy(quarantined):
        """Exercise AsyncOrchestrator._model_for's tier=='heavy' branch
        directly against a real (unpatched) implementation, with a store
        double whose quarantined_models() is deterministic per test case.
        Direct unit-level testing here (rather than driving the whole
        _process/_answer pipeline) avoids depending on incidental details of
        LLM-call argument shapes to infer which model was picked."""
        cfg = SimpleNamespace(models_for=lambda role: _HEAVY_FALLBACKS)
        orch = object.__new__(AsyncOrchestrator)
        orch.cfg = cfg
        store = RecordingStore()
        store.quarantined_models = lambda: quarantined
>       return orch._model_for("chat", "heavy", store)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       TypeError: AsyncOrchestrator._model_for() takes 3 positional arguments but 4 were given

tests/test_orchestrator.py:228: TypeError
______________________ test_model_for_primary_quarantined ______________________

    def test_model_for_primary_quarantined():
>       assert _model_for_heavy({"gpt-oss:20b"}) == "deepseek-r1:32b"
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

tests/test_orchestrator.py:236: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

quarantined = {'gpt-oss:20b'}

    def _model_for_heavy(quarantined):
        """Exercise AsyncOrchestrator._model_for's tier=='heavy' branch
        directly against a real (unpatched) implementation, with a store
        double whose quarantined_models() is deterministic per test case.
        Direct unit-level testing here (rather than driving the whole
        _process/_answer pipeline) avoids depending on incidental details of
        LLM-call argument shapes to infer which model was picked."""
        cfg = SimpleNamespace(models_for=lambda role: _HEAVY_FALLBACKS)
        orch = object.__new__(AsyncOrchestrator)
        orch.cfg = cfg
        store = RecordingStore()
        store.quarantined_models = lambda: quarantined
>       return orch._model_for("chat", "heavy", store)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       TypeError: AsyncOrchestrator._model_for() takes 3 positional arguments but 4 were given

tests/test_orchestrator.py:228: TypeError
______________ test_model_for_primary_and_escalation_quarantined _______________

    def test_model_for_primary_and_escalation_quarantined():
>       assert _model_for_heavy({"gpt-oss:20b", "deepseek-r1:32b"}) == "qwen2.5-coder:32b"
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

tests/test_orchestrator.py:240: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

quarantined = {'deepseek-r1:32b', 'gpt-oss:20b'}

    def _model_for_heavy(quarantined):
        """Exercise AsyncOrchestrator._model_for's tier=='heavy' branch
        directly against a real (unpatched) implementation, with a store
        double whose quarantined_models() is deterministic per test case.
        Direct unit-level testing here (rather than driving the whole
        _process/_answer pipeline) avoids depending on incidental details of
        LLM-call argument shapes to infer which model was picked."""
        cfg = SimpleNamespace(models_for=lambda role: _HEAVY_FALLBACKS)
        orch = object.__new__(AsyncOrchestrator)
        orch.cfg = cfg
        store = RecordingStore()
        store.quarantined_models = lambda: quarantined
>       return orch._model_for("chat", "heavy", store)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       TypeError: AsyncOrchestrator._model_for() takes 3 positional arguments but 4 were given

tests/test_orchestrator.py:228: TypeError
=========================== short test summary info ============================
FAILED tests/test_orchestrator.py::test_model_for_primary_reachable_not_quarantined
FAILED tests/test_orchestrator.py::test_model_for_primary_quarantined - TypeE...
FAILED tests/test_orchestrator.py::test_model_for_primary_and_escalation_quarantined
========================= 3 failed, 15 passed in 0.16s =========================

- [ ] FILE: /home/dyne/Documents/Coding/oh-my-llama/tests/test_orchestrator.py | HASH: 240f729dba51cafb5eeeb1062dacbaecf5d9a9b3bb6395e9c6c58ae0fc374951 | REASON: Rebuild failed after Tier 3 rewrite: ============================= test session starts ==============================
platform linux -- Python 3.13.14, pytest-9.1.1, pluggy-1.6.0
rootdir: /home/dyne/Documents/Coding/oh-my-llama
configfile: pyproject.toml
plugins: anyio-4.14.2, asyncio-1.4.0
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 17 items

tests/test_orchestrator.py ........F........                             [100%]

=================================== FAILURES ===================================
__________________ test_chat_kind_triggers_searchrouter_read ___________________

    def test_chat_kind_triggers_searchrouter_read():
        orch = make_orchestrator()
        store = RecordingStore()
        task = make_task(kind="chat", prompt="What's the weather?", reply_to=None)
    
        call_order = []
        async def mock_read(*args, **kwargs):
            call_order.append("read")
            return "sunny"
    
        async def mock_llm(*args, **kwargs):
            call_order.append("llm")
            return MagicMock()
    
        search_router_read = AsyncMock(side_effect=mock_read)
        # orch.llm is the LLM client OBJECT; production code calls its .chat(...)
        # method, not the object itself -- side_effect/assertions must target
        # .chat, a distinct auto-generated child mock.
        orch.llm.chat.side_effect = mock_llm
    
        with patch("ohmyllama.capabilities.search_router.SearchRouter.read", search_router_read), \
             patch("asyncio.to_thread", AsyncMock(side_effect=_run_in_thread)):
            try:
                asyncio.run(orch._process(store, task))
            except Exception:
                pass
    
        search_router_read.assert_awaited_once()
>       orch.llm.chat.assert_awaited()

tests/test_orchestrator.py:361: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

self = <AsyncMock name='mock.chat' id='140329550829552'>

    def assert_awaited(self):
        """
        Assert that the mock was awaited at least once.
        """
        if self.await_count == 0:
            msg = f"Expected {self._mock_name or 'mock'} to have been awaited."
>           raise AssertionError(msg)
E           AssertionError: Expected chat to have been awaited.

../../../.local/share/uv/python/cpython-3.13.14-linux-x86_64-gnu/lib/python3.13/unittest/mock.py:2361: AssertionError
------------------------------ Captured log call -------------------------------
ERROR    ohmyllama.orchestrator:orchestrator.py:491 task #1 crashed
Traceback (most recent call last):
  File "/home/dyne/Documents/Coding/oh-my-llama/ohmyllama/orchestrator.py", line 480, in _process
    await self._answer(store, task, intent.kind, intent.tier,
                       intent.capability)
  File "/home/dyne/Documents/Coding/oh-my-llama/ohmyllama/orchestrator.py", line 581, in _answer
    if self.cfg.rag_auto and store.rag_count() > 0:
       ^^^^^^^^^^^^^^^^^
AttributeError: 'types.SimpleNamespace' object has no attribute 'rag_auto'
=========================== short test summary info ============================
FAILED tests/test_orchestrator.py::test_chat_kind_triggers_searchrouter_read
========================= 1 failed, 16 passed in 0.22s =========================

- [ ] FILE: /home/dyne/Documents/Coding/oh-my-llama/AGENTS.md | HASH: 52b12f80cc8558ea90191954292248673fdca0b60d27c3b9eaae5d645d8c11df | REASON: Refused write to /home/dyne/Documents/Coding/oh-my-llama/AGENTS.md: only 26% of the original 541 non-blank lines survive in the proposed replacement (163 non-blank lines), below the 50% threshold. This usually means the model regenerated the whole file instead of making a targeted edit, silently deleting unrelated content. Original left untouched; proposed content saved to /home/dyne/Documents/Coding/TriAPI/logs/rejected_writes/20260820-021946-1a1bd7-p1-i1.txt for review.
- [ ] FILE: /home/dyne/Documents/Coding/oh-my-llama/AGENTS.md | HASH: da4fbf3620921bbcda17f5e9cc1d3876ef32ff4c89d1893d05dcb5d513b794d5 | REASON: Refused write to /home/dyne/Documents/Coding/oh-my-llama/AGENTS.md: only 25% of the original 547 non-blank lines survive in the proposed replacement (153 non-blank lines), below the 50% threshold. This usually means the model regenerated the whole file instead of making a targeted edit, silently deleting unrelated content. Original left untouched; proposed content saved to /home/dyne/Documents/Coding/TriAPI/logs/rejected_writes/20260820-021946-1a1bd7-p1-i3.txt for review.
- [ ] FILE: /home/dyne/Documents/Coding/oh-my-llama/AGENTS.md | HASH: 31d0333601e67581f423af00ada819d5c774d8f1821a873c7ca10aa2f948de2d | REASON: Refused write to /home/dyne/Documents/Coding/oh-my-llama/AGENTS.md: only 32% of the original 557 non-blank lines survive in the proposed replacement (181 non-blank lines), below the 50% threshold. This usually means the model regenerated the whole file instead of making a targeted edit, silently deleting unrelated content. Original left untouched; proposed content saved to /home/dyne/Documents/Coding/TriAPI/logs/rejected_writes/20260820-021946-1a1bd7-p1-i4.txt for review.
- [ ] FILE: /home/dyne/Documents/Coding/oh-my-llama/tests/test_semai_intents.py | HASH: 9f815402a5edb2f5ced19a45efccb0f29b842732d6348396d928db340bfbb371 | REASON: Could not apply proposed edit: No SEARCH/REPLACE blocks found in the response.
- [ ] FILE: /home/dyne/Documents/Coding/TriAPI/scripts/config_loader.py | HASH: 45eb587e61195582560e1730ee288c773d66be31980d82504c71dd8c64e6e765 | REASON: Could not apply proposed edit: No SEARCH/REPLACE blocks found in the response.
- [ ] FILE: /home/dyne/Documents/Coding/TriAPI/scripts/dispatcher.py | HASH: 18c4a89f6a7299bfc2e2e7d524f05a41bd1f1af55b45fabcb4c06ef200472b6a | REASON: Could not apply proposed edit: No SEARCH/REPLACE blocks found in the response.
- [ ] FILE: /home/dyne/Documents/Coding/TriAPI/scripts/librarian_escalate.py | HASH: 3df0182ed6d568a0c10c28507b039974eea862d804bd8ac02e6c22edcc3065c2 | REASON: Could not apply proposed edit: Block 2: SEARCH text not found verbatim in the current file.
- [ ] FILE: /home/dyne/Documents/Coding/TriAPI/scripts/librarian_escalate.py | HASH: 34af9ac50f062cffde0a4881abc52f19923cf93c8ce4c22fcdfadd90d0b946b3 | REASON: Could not apply proposed edit: No SEARCH/REPLACE blocks found in the response.
- [ ] FILE: /home/dyne/Documents/Coding/TriAPI/tests/test_tier5_librarian.py | HASH: 8c5c973bb9fba924ab3fa09b8bb25b58de58cf202f012fbc710c23e9359f6f46 | REASON: Could not apply proposed edit: Block 9: SEARCH text matches 12 locations in the file -- ambiguous, needs more surrounding context to be unique.
- [ ] FILE: /home/dyne/Documents/Coding/TriAPI/tests/test_llm_client_sanitize.py | HASH: b5500a9d2ac3532869f9a6bfe469821ffa284434bb6b6bf98094f2213001b231 | REASON: Could not apply proposed edit: No SEARCH/REPLACE blocks found in the response.
- [ ] FILE: /home/dyne/Documents/Coding/TriAPI/scripts/dispatcher.py | HASH: ec0caac07da2a2f89abace914035acc7fd10c0c79774291b9c4a58316c5d2a2a | REASON: Could not apply proposed edit: No SEARCH/REPLACE blocks found in the response.
- [ ] FILE: /home/dyne/Documents/Coding/TriAPI/scripts/budget_guard.py | HASH: a5fc7a08e9f2833f2721ee207f7a5db7f70d551649d4af255fef795d5f155641 | REASON: Could not apply proposed edit: No SEARCH/REPLACE blocks found in the response.
- [ ] FILE: /home/dyne/Documents/Coding/TriAPI/tests/test_tier_reassignment_prep.py | HASH: 0c73fea6965e5d99ef3543371e89bd6c963da48de4348ef5e42f1254d82fa9fe | REASON: Could not apply proposed edit: No SEARCH/REPLACE blocks found in the response.
- [ ] FILE: /home/dyne/Documents/Coding/TriAPI/tests/test_tier_reassignment_prep.py | HASH: 19116bdbfc611c5090ce5eb7180fe08fe0dc0f75da9659e0f3fe3817bfb4cb2d | REASON: Rebuild failed after Tier 3 rewrite: test_non_string_response_raises_calledprocesserror (tests.test_tier_reassignment_prep.TestAgyProviderGracefulFailure.test_non_string_response_raises_calledprocesserror) ... [32mok[0m
test_non_success_status_raises_calledprocesserror (tests.test_tier_reassignment_prep.TestAgyProviderGracefulFailure.test_non_success_status_raises_calledprocesserror) ... [32mok[0m
test_nonzero_returncode_raises_calledprocesserror (tests.test_tier_reassignment_prep.TestAgyProviderGracefulFailure.test_nonzero_returncode_raises_calledprocesserror) ... [32mok[0m
test_undecodable_stdout_raises_calledprocesserror (tests.test_tier_reassignment_prep.TestAgyProviderGracefulFailure.test_undecodable_stdout_raises_calledprocesserror) ... [32mok[0m
test_execute_llm_agy_success (tests.test_tier_reassignment_prep.TestAgyProviderSuccess.test_execute_llm_agy_success) ... [32mok[0m
test_routing_for_google_provider (tests.test_tier_reassignment_prep.TestBreakdownPhaseAttemptRouting.test_routing_for_google_provider) ... [32mok[0m
test_routing_for_non_google_providers (tests.test_tier_reassignment_prep.TestBreakdownPhaseAttemptRouting.test_routing_for_non_google_providers) ... [32mok[0m
test_is_deepseek_peak_hours_true_despite_check_tier3_false (tests.test_tier_reassignment_prep.TestDispatcherAdvisoryDelegation.test_is_deepseek_peak_hours_true_despite_check_tier3_false) ... [32mok[0m
test_no_deepseek_returns_none_and_default_peak_hours (tests.test_tier_reassignment_prep.TestPeakHoursPositionIndependence.test_no_deepseek_returns_none_and_default_peak_hours) ... [32mok[0m
test_peak_hours_boundary_inclusive_start_exclusive_end (tests.test_tier_reassignment_prep.TestPeakHoursPositionIndependence.test_peak_hours_boundary_inclusive_start_exclusive_end) ... [31mFAIL[0m
test_peak_hours_gating_position_independent (tests.test_tier_reassignment_prep.TestPeakHoursPositionIndependence.test_peak_hours_gating_position_independent) ... [32mok[0m
test_resolve_deepseek_tier_position_independent (tests.test_tier_reassignment_prep.TestPeakHoursPositionIndependence.test_resolve_deepseek_tier_position_independent) ... [32mok[0m

======================================================================
[31mFAIL[0m[1;31m: test_peak_hours_boundary_inclusive_start_exclusive_end (tests.test_tier_reassignment_prep.TestPeakHoursPositionIndependence.test_peak_hours_boundary_inclusive_start_exclusive_end)[0m
----------------------------------------------------------------------
Traceback (most recent call last):
  File [35m"/home/dyne/Documents/Coding/TriAPI/tests/test_tier_reassignment_prep.py"[0m, line [35m258[0m, in [35mtest_peak_hours_boundary_inclusive_start_exclusive_end[0m
    [31mself.assertTrue[0m[1;31m(result_end["ok"], "10:00 UTC should no longer be in peak hours")[0m
    [31m~~~~~~~~~~~~~~~[0m[1;31m^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^[0m
[1;35mAssertionError[0m: [35mFalse is not true : 10:00 UTC should no longer be in peak hours[0m

----------------------------------------------------------------------
Ran 12 tests in 0.003s

[1;31mFAILED[0m ([1;31mfailures=1[0m)

- [ ] FILE: /home/dyne/Documents/Coding/TriAPI/AGENTS.md | HASH: 28d92a67536f7d269095093ebecff99c79c59a58abdd789eac4a8f02b8c2f191 | REASON: Could not apply proposed edit: Block 3: SEARCH text matches 6 locations in the file -- ambiguous, needs more surrounding context to be unique.
- [ ] FILE: /home/dyne/Documents/Coding/TriAPI/scripts/tier4_worker.py | HASH: 93d98e4095469bb38ce26cf67d0b7357bcbc14a15a2d87401e8bd8b74a860206 | REASON: Could not apply proposed edit: No SEARCH/REPLACE blocks found in the response.
- [ ] FILE: /home/dyne/Documents/Coding/TriAPI/tests/test_run_build_pipefail.py | HASH: 4f5e3fba9b580482393ec0a4c8f530a5839d912f18badecf1f168d75d5c57b2a | REASON: Could not apply proposed edit: No SEARCH/REPLACE blocks found in the response.
- [ ] FILE: /home/dyne/Documents/Coding/TriAPI/config/tiers.yaml | HASH: 3fdd7e358c9c7be10033b57b68df352ef68e49e31543f52005b9f557b1af2ebe | REASON: Could not apply proposed edit: No SEARCH/REPLACE blocks found in the response.
- [ ] FILE: /home/dyne/Documents/Coding/TriAPI/config/tiers.yaml | HASH: ccccebc9e61ab31494d92c1d664c63978cc700dd564a008323dbcf189fedda2f | REASON: Could not apply proposed edit: No SEARCH/REPLACE blocks found in the response.
- [ ] FILE: /home/dyne/Documents/Coding/TriAPI/tests/test_orchestrator_tier3_peak_skip.py | HASH: 8c0c1fe0c1e786a198c131b2540ebbad9b435b336342eaf6a64dabe9c3b4ebd6 | REASON: Tier 3 request failed: Command '['agy', '-p', 'The current file already passes its build/verification. Improve only the following quality issues without regressing behavior: Rewrite this file to apply this refactor: The diff only updates the configuration dictionary but completely misses the requested updates to the test assertions in test_config_matches_tiers_yaml and the mock return values in test_peak_hours_skip_tier3 and test_off_peak_allows_tier3.', '--model', 'gemini-3.1-pro', '--effort', 'high', '--dangerously-skip-permissions', '--output-format', 'json']' timed out after 300 seconds
- [ ] FILE: /home/dyne/Documents/Coding/TriAPI/AGENTS.md | HASH: b3b1e07fcdadb8b395156bd81a1584a2a4397f59482c091e454f42f77d0f169b | REASON: Could not apply proposed edit: No SEARCH/REPLACE blocks found in the response.
- [ ] FILE: /home/dyne/Documents/Coding/TriAPI/scripts/dispatcher.py | HASH: 666a12462df96efe2cfbe6940ffc88b5f8f60b2b77266ea8c093ad0b00d72459 | REASON: Could not apply proposed edit: No SEARCH/REPLACE blocks found in the response.
- [ ] FILE: /home/dyne/Documents/Coding/TriAPI/scripts/dispatcher.py | HASH: 647c1bd397c231b80b85d6cc18905d81b6c50e08c38e61ea5bd2a3a737f3145f | REASON: Could not apply proposed edit: No SEARCH/REPLACE blocks found in the response.
- [ ] FILE: /home/dyne/Documents/Coding/TriAPI/ARCHITECTURE.md | HASH: b40996897b091db5156e8a4c572d1db0eb7f7383d66bd557523ba3b836c1f5b0 | REASON: Could not apply proposed edit: Block 3: SEARCH text not found verbatim in the current file.
