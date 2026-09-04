# Tech Debt

Fixes `handle_fix_forward` gave up on after a single Tier 3 attempt failed to rebuild. Tier 3 is in DeepSeek peak billing hours 01:00-04:00 UTC (LA local 2026-08-18T20:59:37.361917-07:00, UTC 2026-08-19T03:59:37.361917+00:00). Each entry's HASH is the file's SHA-256 at the moment it was logged; if the file has since changed, treat the entry as STALE.

- [ ] FILE: scripts/triapi.py | HASH: n/a (design gap, not tied to one file's content) | REASON: `cmd_tech_debt()`'s `check_staleness()` correctly filters a hash-mismatched entry out of dispatch, but nothing then removes it -- `remove_resolved_entries()` only fires for entries that were actually dispatched successfully. A tech-debt entry whose underlying bug was fixed out-of-band (hand-fix, or a different dispatch) leaves its file hash stale forever, so `triapi tech-debt` silently no-ops on it every run (zero output, exit 0) instead of resolving or at least flagging it for manual review. Confirmed live 2026-09-04: the AGENTS.md narrow-test-command entry (already fixed in commit d6ab54c) sat through a full `triapi tech-debt` run with no effect and had to be dropped by hand. Fix: either re-run `check_staleness()`'s underlying verify condition (if the entry names one) before discarding a stale-hashed entry, or at minimum print/log which entries were skipped as stale so a human notices instead of silent no-op.
- [ ] FILE: /home/dyne/Documents/Coding/TriAPI/tests/test_branch_features.py | HASH: 7561d005b8b1e6fc4239a1b8183a863e3eee14de317acfa99b7ca5bce05f6962 | REASON: Rebuild failed after Tier 3 rewrite: [Phase 1] (1/1) Test task
  -> success (resolved_by=tier_3)
[Phase 1] (1/1) Test task
  -> build_failed (resolved_by=None)
[Phase 1] (1/1) Test task
  -> success (resolved_by=tier_3)
[Phase 1] (1/1) Test task
  -> success (resolved_by=tier_4)
[Phase 1] (1/1) Test task
  -> success (resolved_by=tier_5)
[HUMAN HANDOFF] Task 't1' needs manual review: reason
[HUMAN HANDOFF] See /tmp/tmpn2_yie56/escalation_t1.md
[BUDGET GUARD] Tier 2 skipped: no
[BUDGET GUARD] Tier 1 skipped: no
test_append_creates_file_with_header (tests.test_branch_features.AgentsMdGateTests.test_append_creates_file_with_header) ... ok
test_append_then_find_incomplete (tests.test_branch_features.AgentsMdGateTests.test_append_then_find_incomplete) ... ok
test_block_with_no_checkboxes_is_not_blocking (tests.test_branch_features.AgentsMdGateTests.test_block_with_no_checkboxes_is_not_blocking) ... ok
test_mark_plan_complete_clears_gate (tests.test_branch_features.AgentsMdGateTests.test_mark_plan_complete_clears_gate) ... ok
test_mark_plan_complete_unknown_run_is_noop (tests.test_branch_features.AgentsMdGateTests.test_mark_plan_complete_unknown_run_is_noop) ... ok
test_no_agents_md_means_no_incomplete_plan (tests.test_branch_features.AgentsMdGateTests.test_no_agents_md_means_no_incomplete_plan) ... ok
test_only_most_recent_block_gates (tests.test_branch_features.AgentsMdGateTests.test_only_most_recent_block_gates) ... ok
test_apply_edit_blocks_with_empty_string_returns_none_string (tests.test_branch_features.ApplyEditBlocksTests.test_apply_edit_blocks_with_empty_string_returns_none_string) ... ok
test_apply_edit_blocks_with_none_returns_none_string (tests.test_branch_features.ApplyEditBlocksTests.test_apply_edit_blocks_with_none_returns_none_string) ... ok
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
test_handle_fix_forward_failed_rebuild (tests.test_branch_features.DispatcherHookAndFixForwardTests.test_handle_fix_forward_failed_rebuild) ... ok
test_handle_fix_forward_successful_rebuild (tests.test_branch_features.DispatcherHookAndFixForwardTests.test_handle_fix_forward_successful_rebuild) ... ok
test_peak_hours_skipped_judge_passes_open_calls_extract_pattern (tests.test_branch_features.DispatcherHookAndFixForwardTests.test_peak_hours_skipped_judge_passes_open_calls_extract_pattern) ... ok
test_successful_item_failing_judge_calls_handle_fix_forward (tests.test_branch_features.DispatcherHookAndFixForwardTests.test_successful_item_failing_judge_calls_handle_fix_forward) ... ok
test_successful_item_passing_judge_calls_extract_pattern (tests.test_branch_features.DispatcherHookAndFixForwardTests.test_successful_item_passing_judge_calls_extract_pattern) ... ok
test_tier4_success_still_runs_design_judge (tests.test_branch_features.DispatcherHookAndFixForwardTests.test_tier4_success_still_runs_design_judge) ... ok
test_tier5_success_skips_design_judge (tests.test_branch_features.DispatcherHookAndFixForwardTests.test_tier5_success_skips_design_judge) ... ok
test_add_lesson_deduplicates_and_selection_avoids_extension_noise (tests.test_branch_features.LessonsTests.test_add_lesson_deduplicates_and_selection_avoids_extension_noise) ... ok
test_handoff_writes_runtime_store_not_committed_lessons (tests.test_branch_features.LessonsTests.test_handoff_writes_runtime_store_not_committed_lessons) ... ok
test_malformed_lines_are_skipped (tests.test_branch_features.LessonsTests.test_malformed_lines_are_skipped) ... ok
test_select_relevant_skips_unresolved_pattern (tests.test_branch_features.LessonsTests.test_select_relevant_skips_unresolved_pattern) ... ok
test_embedded_error_with_code_sets_response_status (tests.test_branch_features.LlmClientOpenAIErrorBodyTests.test_embedded_error_with_code_sets_response_status) ... ok
test_missing_choices_no_error_key_raises_clear_message (tests.test_branch_features.LlmClientOpenAIErrorBodyTests.test_missing_choices_no_error_key_raises_clear_message) ... ok
test_normal_response_with_choices_still_works (tests.test_branch_features.LlmClientOpenAIErrorBodyTests.test_normal_response_with_choices_still_works) ... ok
test_null_message_content_raises_instead_of_returning_none (tests.test_branch_features.LlmClientOpenAIErrorBodyTests.test_null_message_content_raises_instead_of_returning_none) ... ok
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
test_skip_tier4_defaults_false_and_calls_tier4_run (tests.test_branch_features.SkipTier4Tests.test_skip_tier4_defaults_false_and_calls_tier4_run) ... ok
test_skip_tier4_never_calls_tier4_run_and_starts_at_tier3 (tests.test_branch_features.SkipTier4Tests.test_skip_tier4_never_calls_tier4_run_and_starts_at_tier3) ... ok
test_check_staleness_false_when_file_unchanged (tests.test_branch_features.TechDebtTests.test_check_staleness_false_when_file_unchanged) ... ok
test_check_staleness_false_when_hash_is_na (tests.test_branch_features.TechDebtTests.test_check_staleness_false_when_hash_is_na) ... ok
test_check_staleness_true_when_file_deleted (tests.test_branch_features.TechDebtTests.test_check_staleness_true_when_file_deleted) ... ok
test_check_staleness_true_when_file_modified (tests.test_branch_features.TechDebtTests.test_check_staleness_true_when_file_modified) ... ok
test_cmd_tech_debt_builds_synthetic_state_and_skips_stale (tests.test_branch_features.TechDebtTests.test_cmd_tech_debt_builds_synthetic_state_and_skips_stale) ... ERROR
test_log_tech_debt_creates_backlog_file_with_hashed_entry (tests.test_branch_features.TechDebtTests.test_log_tech_debt_creates_backlog_file_with_hashed_entry) ... ok
test_after_peak_window_passes (tests.test_branch_features.Tier3PeakHoursTests.test_after_peak_window_passes) ... ok
test_before_peak_window_passes (tests.test_branch_features.Tier3PeakHoursTests.test_before_peak_window_passes) ... ok
test_mid_peak_window_refuses (tests.test_branch_features.Tier3PeakHoursTests.test_mid_peak_window_refuses) ... ok
test_weekday_refuses_in_peak (tests.test_branch_features.Tier3PeakHoursTests.test_weekday_refuses_in_peak) ... ok
test_weekend_passes_in_peak (tests.test_branch_features.Tier3PeakHoursTests.test_weekend_passes_in_peak) ... ok
test_unload_models_get_exception_returns_empty (tests.test_branch_features.UnloadOllamaModelsTests.test_unload_models_get_exception_returns_empty) ... ok
test_unload_models_partial_failure (tests.test_branch_features.UnloadOllamaModelsTests.test_unload_models_partial_failure) ... ok
test_unload_models_successful (tests.test_branch_features.UnloadOllamaModelsTests.test_unload_models_successful) ... ok

======================================================================
ERROR: test_cmd_tech_debt_builds_synthetic_state_and_skips_stale (tests.test_branch_features.TechDebtTests.test_cmd_tech_debt_builds_synthetic_state_and_skips_stale)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/home/dyne/Documents/Coding/TriAPI/tests/test_branch_features.py", line 1402, in test_cmd_tech_debt_builds_synthetic_state_and_skips_stale
    tech_debt.log_tech_debt(str(fresh), "retry me", build_cmd="make test")
    ~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: log_tech_debt() got an unexpected keyword argument 'build_cmd'

----------------------------------------------------------------------
Ran 63 tests in 0.050s

FAILED (errors=1)

