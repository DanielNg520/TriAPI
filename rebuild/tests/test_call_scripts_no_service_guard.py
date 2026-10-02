"""Regression test: call scripts must never touch the resource guard.

A batch of remote-API calls used to trip systemd user-service start limits.
The resource guard belongs only to the local-model run path, never to the
thin remote-API client scripts.
"""

import importlib
import inspect

import pytest


@pytest.mark.parametrize(
    "script_name",
    ["call_deepseek", "call_planner", "call_agy"],
    ids=["call_deepseek", "call_planner", "call_agy"],
)
def test_call_scripts_have_no_service_guard(script_name: str) -> None:
    """Each remote-API call script must not reference or expose the guard."""
    module = importlib.import_module(f"scripts.{script_name}")
    source = inspect.getsource(module)

    for forbidden in ("pause_services", "resume_services", "resource_guard"):
        assert forbidden not in source

    assert not hasattr(module, "pause_services")
    assert not hasattr(module, "resume_services")
