from unittest import TestCase, mock

from scripts import planner


class TestPlannerEffortForwarding(TestCase):
    """Regression coverage for the tier_1_planner effort-forwarding bug
    (2026-08-28): _plan_turn_llm()'s non-'cli' branch called
    llm_client.execute_llm() without an `effort` kwarg, so a provider whose
    model requires --effort (e.g. agy's gemini-3.1-pro) errored out with
    "requires --effort" and every planning turn silently fell back to
    tier_1_manager's Claude CLI. Confirmed live before this fix."""

    @mock.patch('scripts.planner.check_tier1_ok', return_value={'ok': True})
    @mock.patch('scripts.planner.build_context_blob', return_value='')
    @mock.patch('scripts.planner.secrets_loader.load_secrets', return_value={})
    @mock.patch('scripts.planner.llm_client.execute_llm')
    @mock.patch('scripts.planner.config_loader.load_tiers')
    def test_effort_is_forwarded_to_execute_llm(
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

        turn = planner.plan_turn('goal', '.', None)

        self.assertEqual(turn['status'], 'ok')
        _, kwargs = mock_execute_llm.call_args
        self.assertEqual(kwargs.get('effort'), 'high')

    @mock.patch('scripts.planner.check_tier1_ok', return_value={'ok': True})
    @mock.patch('scripts.planner.build_context_blob', return_value='')
    @mock.patch('scripts.planner.secrets_loader.load_secrets', return_value={})
    @mock.patch('scripts.planner.llm_client.execute_llm')
    @mock.patch('scripts.planner.config_loader.load_tiers')
    def test_missing_effort_key_forwards_none(
        self, mock_load_tiers, mock_execute_llm, mock_secrets, mock_blob, mock_guard
    ):
        # A provider with no `effort` key configured (e.g. the old free
        # OpenRouter models) must still work -- effort=None is a valid,
        # already-supported value for execute_llm().
        mock_load_tiers.return_value = {
            'tier_1_planner': {
                'provider': 'openrouter',
                'models': {'default': 'some/free-model:free'},
                'default_model': 'default',
            }
        }
        mock_execute_llm.return_value = ('a plan', 'openrouter', 0, 0)

        turn = planner.plan_turn('goal', '.', None)

        self.assertEqual(turn['status'], 'ok')
        _, kwargs = mock_execute_llm.call_args
        self.assertIsNone(kwargs.get('effort'))
