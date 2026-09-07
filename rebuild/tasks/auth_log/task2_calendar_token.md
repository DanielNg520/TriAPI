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


def calendar_service_account_token(scope: str) -> str:
    """
    Retrieve an access token for the Google Calendar API using a service account.

    The function reads the `CALENDAR_SA_FILE` secret via :func:`resolve_secret`,
    which should contain the path to a JSON key file. It then loads the credentials,
    scopes them with the provided scope, refreshes the token, and returns it.

    Args:
        scope: The OAuth scope string for the Calendar API (e.g., "https://www.googleapis.com/auth/calendar").

    Returns:
        str: The service account access token.

    Raises:
        GoogleAuthError: If the secret is missing, credentials cannot be loaded,
            refreshed, or a token could not be obtained.
    """
    sa_file_path = resolve_secret("CALENDAR_SA_FILE")
    if not sa_file_path:
        raise GoogleAuthError(
            "Missing CALENDAR_SA_FILE secret for service account"
        )

    try:
        creds: GCredentials = GCredentials.from_service_account_file(
            sa_file_path, scopes=[scope]
        )
        request = Request()
        creds.refresh(request)
        token = creds.token
        if not token:
            raise GoogleAuthError("Service account refresh returned empty token")
        return token
    except Exception as exc:
        raise GoogleAuthError("Failed to obtain service account token") from exc
```

Task: modify ONLY the final `except Exception as exc:` block inside `calendar_service_account_token` that currently reads:

```python
    except Exception as exc:
        raise GoogleAuthError("Failed to obtain service account token") from exc
```

Change the raised message to include the real exception's type name and string. Use this exact replacement:

```python
    except Exception as exc:
        raise GoogleAuthError(
            f"Failed to obtain service account token: {type(exc).__name__}: {exc}"
        ) from exc
```

Do not touch the inner `if not token: raise GoogleAuthError(...)` line, any other function, imports, docstrings, or `gmail_access_token`. Reply with ONLY the full corrected `calendar_service_account_token` function (from `def calendar_service_account_token` to its final line), as a single python code block, no other text.
