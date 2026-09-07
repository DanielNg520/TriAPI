Give `BrowserActionWorker` an optional `settings` constructor argument and pass it to the `BrowserCapability` it constructs in `execute()`. `BrowserCapability.__init__` already accepts an optional `settings` parameter (added in a prior change). Do not change any other logic.

1. Add `def __init__(self, settings: "Settings | None" = None) -> None: self.settings = settings` to `BrowserActionWorker` (it currently has no `__init__`), placed right after `name = "browser_action"`.
2. In `execute()`, change `browser = BrowserCapability()` to `browser = BrowserCapability(self.settings)`.
3. Add `from typing import TYPE_CHECKING` and `if TYPE_CHECKING: from semai.config.schema import Settings` near the top imports.

Reply with the complete corrected file content only, in a single fenced code block.

```python
from semai.capabilities.browser import BrowserCapability
from semai.core.intents import Intent
from semai.core.results import Result
from semai.workers.base import ApprovalRequiredWorker, ProposedAction

_SUPPORTED_BROWSER_ACTIONS = ("fill_form", "export_pdf")


def _is_browser_error_message(result: object) -> bool:
    """Return True when the capability returned an error string."""
    return isinstance(result, str) and (
        result.startswith("Security Error")
        or result.startswith("Error:")
        or result.startswith("Browser error")
    )


class BrowserActionWorker(ApprovalRequiredWorker):
    """Approval-required worker that executes browser actions."""
    name = "browser_action"

    def propose(self, intent: Intent) -> list[ProposedAction]:
        """
        Return a ProposedAction describing the browser action.
        The action is only proposed if url is truthy and action is fill_form or export_pdf.
        """
        action = getattr(intent, "action", None)
        url = getattr(intent, "url", "")

        if not url or action not in _SUPPORTED_BROWSER_ACTIONS:
            return []

        desc = f"Execute browser {action} on {url}"
        payload = {
            "action": action,
            "url": url,
            "field_values": getattr(intent, "field_values", {}) or {},
            "output_path": getattr(intent, "output_path", "") or "",
            "submit_selector": getattr(intent, "submit_selector", None),
        }
        return [ProposedAction(action=self.name, description=desc, payload=payload)]

    def execute(self, action: ProposedAction) -> Result:
        """
        Perform the approved browser action.
        Validates the action.
        """
        if action.action != self.name:
            return Result(ok=False, message=f"Unsupported action: {action.action}")

        payload = action.payload or {}
        browser_action = payload.get("action")
        url = payload.get("url", "")
        field_values = payload.get("field_values") or {}
        output_path = payload.get("output_path") or ""
        submit_selector = payload.get("submit_selector") or None

        if not browser_action or not url:
            return Result(ok=False, message="Missing action or URL in payload")

        if browser_action not in _SUPPORTED_BROWSER_ACTIONS:
            return Result(ok=False, message=f"Unsupported browser action: {browser_action}")

        try:
            browser = BrowserCapability()
            res = None
            if browser_action == "fill_form":
                res = browser.fill_form(url, field_values, submit_selector)
            elif browser_action == "export_pdf":
                res = browser.export_pdf(url, output_path)
            else:
                return Result(ok=False, message=f"Unsupported browser action: {browser_action}")

            if _is_browser_error_message(res):
                return Result(ok=False, message=res)
        except Exception as e:
            return Result(ok=False, message=f"Failed to execute browser action: {e}")

        return Result(
            ok=True,
            message=f"Successfully executed {browser_action} on {url}",
        )
```
