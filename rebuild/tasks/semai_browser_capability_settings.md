Two separate excerpts from `semai/capabilities/browser.py`, both verbatim. Make these exact changes and nothing else:

**Excerpt A (the import block, lines 6-13):**
1. Change `from typing import Any, Optional` to `from typing import TYPE_CHECKING, Any, Optional`.
2. Add, immediately after the existing `from semai.workers.base import ProposedAction` line: a blank line, then `if TYPE_CHECKING:` then an indented `from semai.config.schema import Settings`.

```python
import ipaddress
import socket
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

from semai.security.path_guard import _allowed_roots, _is_allowed_path
from semai.workers.base import ProposedAction
```

**Excerpt B (top of `BrowserCapability`, lines 96-100, plus `export_pdf`, lines 267-310 — the exact same class, `read()` and `capture_html()` sit between these two points and are UNCHANGED and not shown here, do not reproduce them):**
1. Add `def __init__(self, settings: "Settings | None" = None) -> None: self.settings = settings` right after `requires_llm_postprocessing = False` and before `def available`.
2. In `export_pdf`, change `if not _is_allowed_path(file_path):` to `if not _is_allowed_path(file_path, self.settings):`.
3. In `export_pdf`, change `allowed = ", ".join(str(r) for r in _allowed_roots())` to `allowed = ", ".join(str(r) for r in _allowed_roots(self.settings))`.

```python
class BrowserCapability:
    name = "browser"
    requires_llm_postprocessing = False  # read() returns usable output without requiring a local LLM service.

    def available(self) -> bool:
        return True
```

```python
    def export_pdf(
        self,
        url: str,
        output_path: str,
        timeout_ms: int = 20_000,
    ) -> str:
        """Export the page at the target url as a PDF file, validating path safety."""
        try:
            file_path = Path(output_path).expanduser().resolve()
        except Exception as e:
            return f"Error resolving output path: {e}"

        if not _is_allowed_path(file_path):
            allowed = ", ".join(str(r) for r in _allowed_roots())
            return (
                f"Security Error: Access to {file_path} is forbidden. "
                f"Only the following roots are allowed: {allowed}"
            )

        ok, err = validate_destination_url(url)
        if not ok:
            return err or "Security Error"

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return "Error: playwright not installed. Cannot execute JS-heavy browsing."

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                try:
                    page = browser.new_page()
                    page.goto(url, timeout=timeout_ms)
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    page.pdf(path=str(file_path))
                    return f"OK: exported PDF to {file_path}"
                finally:
                    try:
                        browser.close()
                    except Exception:
                        pass
        except Exception as e:
            return f"Browser error: {e}"
```

Reply with two fenced code blocks in this same order: the corrected Excerpt A (import block), then the corrected Excerpt B's class-top (`class BrowserCapability:` through `available`) followed immediately by the corrected `export_pdf` method (same block, since they belong to the same class body). No other text.
