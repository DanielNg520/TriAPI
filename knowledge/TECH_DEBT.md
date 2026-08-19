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

