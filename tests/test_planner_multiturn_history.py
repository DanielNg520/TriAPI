from unittest import TestCase, mock

from scripts import planner


class TestPlannerMultiturnHistory(TestCase):
    """Regression coverage for the multi-turn statelessness bug
    (2026-08-28): non-'cli' tier_1_planner providers have no server-side
    session, and _plan_turn_llm() previously sent only the caller's latest
    message on every turn -- turn 2+ was blind to the original goal and
    all prior turns. Confirmed live: feedback on turn 2 got a response
    saying the goal wasn't visible at all. Fixed by having the caller
    (triapi.py) accumulate a `history` list and planner.py render it into
    the enriched prompt."""

    @mock.patch('scripts.planner.check_tier1_ok', return_value={'ok': True})
    @mock.patch('scripts.planner.build_context_blob', return_value='')
    @mock.patch('scripts.planner.secrets_loader.load_secrets', return_value={})
    @mock.patch('scripts.planner.llm_client.execute_llm')
    @mock.patch('scripts.planner.config_loader.load_tiers')
    def test_history_is_included_in_prompt_for_non_cli_provider(
        self, mock_load_tiers, mock_execute_llm, mock_secrets, mock_blob, mock_guard
    ):
        mock_load_tiers.return_value = {
            'tier_1_planner': {
                'provider': 'agy',
                'models': {'default': 'gemini-3.1-pro'},
                'default_model': 'default',
                'effort': 'high',
            }
        }
        mock_execute_llm.return_value = ('a revised plan', 'agy', 0, 0)

        history = [
            {'user': 'the original goal text', 'assistant': 'the first plan draft'},
        ]
        turn = planner.plan_turn('please add a test step', '.', 'stateless', history=history)

        self.assertEqual(turn['status'], 'ok')
        _, kwargs = mock_execute_llm.call_args
        prompt = kwargs['prompt']
        self.assertIn('the original goal text', prompt)
        self.assertIn('the first plan draft', prompt)
        self.assertIn('please add a test step', prompt)

    @mock.patch('scripts.planner.check_tier1_ok', return_value={'ok': True})
    @mock.patch('scripts.planner.build_context_blob', return_value='')
    @mock.patch('scripts.planner.secrets_loader.load_secrets', return_value={})
    @mock.patch('scripts.planner.llm_client.execute_llm')
    @mock.patch('scripts.planner.config_loader.load_tiers')
    def test_empty_history_on_first_turn_still_works(
        self, mock_load_tiers, mock_execute_llm, mock_secrets, mock_blob, mock_guard
    ):
        mock_load_tiers.return_value = {
            'tier_1_planner': {
                'provider': 'agy',
                'models': {'default': 'gemini-3.1-pro'},
                'default_model': 'default',
                'effort': 'high',
            }
        }
        mock_execute_llm.return_value = ('a plan', 'agy', 0, 0)

        turn = planner.plan_turn('the original goal text', '.', None, history=[])

        self.assertEqual(turn['status'], 'ok')
        _, kwargs = mock_execute_llm.call_args
        self.assertEqual(kwargs['prompt'], 'the original goal text')

    @mock.patch('scripts.planner.check_tier1_ok', return_value={'ok': True})
    def test_cli_provider_ignores_history(self, mock_guard):
        # provider='cli' relies on --resume for real session memory and
        # must not need history at all -- calling with history=None (the
        # default) must not raise.
        with mock.patch('scripts.planner.config_loader.load_tiers') as mock_load_tiers, \
             mock.patch('scripts.planner.subprocess.run') as mock_run:
            mock_load_tiers.return_value = {
                'tier_1_planner': {'provider': 'cli', 'models': {'default': 'claude-sonnet-5'}, 'default_model': 'default'}
            }
            mock_result = mock.MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = '{"result": "a plan"}'
            mock_run.return_value = mock_result

            turn = planner.plan_turn('goal', '.', None)

            self.assertEqual(turn['status'], 'ok')
