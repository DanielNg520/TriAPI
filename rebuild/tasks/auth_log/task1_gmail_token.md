Edit one function in `/home/dyne/Documents/Coding/SemAI/src/semai/google_auth.py`.

Current full file content (edit in place, do not reconstruct from memory):

```python
from __future__ import annotations

import httpx
from google.auth.transport.requests import Request
from google.oauth2.service_account import Credentials as GCredentials

from semai.security.secrets import resolve_secret
from semai.core.errors import PermanentError


class GoogleAuthError(PermanentError):
    """Google auth (token exchange, missing/expired credentials) failed.
    A PermanentError, not RetryableError: a missing or expired refresh
    token will not succeed on blind retry, only after a human re-runs
    OAuth consent."""


def gmail_access_token() -> str:
    """
    Retrieve an OAuth 2.0 access token for Gmail using a refresh token.

    The function reads the following secrets via `resolve_secret`:

        - GMAIL_OAUTH_CLIENT_ID
        - GMAIL_OAUTH_CLIENT_SECRET
        - GMAIL_OAUTH_REFRESH_TOKEN

    It then performs a POST request to Google's OAuth token endpoint with a 30‑second timeout.
    If any secret is missing, the HTTP request fails, or the response cannot be decoded,
    a :class:`GoogleAuthError` is raised.

    Returns:
        str: The Gmail access token.
    """
    client_id = resolve_secret("GMAIL_OAUTH_CLIENT_ID")
    client_secret = resolve_secret("GMAIL_OAUTH_CLIENT_SECRET")
    refresh_token = resolve_secret("GMAIL_OAUTH_REFRESH_TOKEN")

    if not all([client_id, client_secret, refresh_token]):
        raise GoogleAuthError(
            "Missing required Google credentials in secrets"
        )

    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }

    try:
        resp = httpx.post(
            "https://oauth2.googleapis.com/token",
            data=payload,
            timeout=30.0,
        )
    except Exception as exc:
        raise GoogleAuthError("Failed to make HTTP request for Gmail access token") from exc

    if resp.status_code != 200:
        raise GoogleAuthError(
            f"Token endpoint returned {resp.status_code}: {resp.text}"
        )

    try:
        data = resp.json()
        return data["access_token"]
    except Exception as exc:
        raise GoogleAuthError("Failed to decode token response") from exc
```

Task: modify ONLY the `except Exception as exc:` block inside `gmail_access_token` that currently reads:

```python
    except Exception as exc:
        raise GoogleAuthError("Failed to make HTTP request for Gmail access token") from exc
```

Change the raised message to include the real exception's type name and string, e.g. so a caller logging just `str(exc_or_error)` still sees the underlying cause instead of a generic sentence. Use this exact replacement:

```python
    except Exception as exc:
        raise GoogleAuthError(
            f"Failed to make HTTP request for Gmail access token: {type(exc).__name__}: {exc}"
        ) from exc
```

Do not touch any other function, any other except block, imports, docstrings, or the `calendar_service_account_token` function. Reply with ONLY the full corrected `gmail_access_token` function (from `def gmail_access_token` to its closing return of the last except block), as a single python code block, no other text.
