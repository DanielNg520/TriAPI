Current file (SemAI repo: src/semai/adapters/telegram.py) — edit in place, do not regenerate from memory:
```python
"""
semai.adapters.telegram
───────────────────────
Adds a new async adapter alongside `ohmyllama/telegram.py` (not a retirement).
"""

import asyncio
import logging
import re
import sys
from dataclasses import dataclass
from typing import Any

import httpx

log = logging.getLogger(__name__)


class TelegramError(RuntimeError):
    """A Bot API call failed.

    `permanent` distinguishes "this will never work" (the chat does not exist,
    the user blocked the bot) from "try again" (network blip, 429, 5xx). The
    caller needs that difference: retrying a permanent failure forever fills the
    log and never advances, while dropping a transient one loses a message.
    """

    def __init__(self, message: str, *, permanent: bool = False):
        super().__init__(message)
        self.permanent = permanent


_PERMANENT = re.compile(
    r"chat not found|bot was blocked|user is deactivated|bot was kicked|"
    r"chat_id is empty|have no rights to send|need administrator rights",
    re.IGNORECASE,
)

# ── markdown chunking ─────────────────────────────────────────────────────


def split_markdown_safely(text: str, limit: int) -> list[str]:
    if not text:
        return [""]
    
    chunks = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        cut = text.rfind("\n\n", 0, limit)
        if cut == -1:
            cut = text.rfind("\n", 0, limit)
        if cut == -1:
            cut = limit
        chunks.append(text[:cut])
        text = text[cut:].lstrip("\n")
    return chunks


# ── routing ───────────────────────────────────────────────────────────────

ROUTE_RE = re.compile(r"^(?P<chat>-?\d+)(?:\.t(?P<topic>\d+))?$")


@dataclass(frozen=True)
class Route:
    chat_id: int
    topic_id: int | None = None

    def __str__(self) -> str:
        if self.topic_id is not None:
            return f"{self.chat_id}.t{self.topic_id}"
        return str(self.chat_id)


def parse_route(s: str | int) -> Route | None:
    m = ROUTE_RE.match(str(s).strip())
    if not m:
        return None
    topic = m.group("topic")
    return Route(
        chat_id=int(m.group("chat")),
        topic_id=int(topic) if topic is not None else None,
    )


def build_route(chat_id: int, topic_id: int | None = None) -> str:
    return str(Route(chat_id=chat_id, topic_id=topic_id))


def send_kwargs(route: str) -> dict:
    r = parse_route(route)
    if r is None or r.topic_id is None:
        return {}
    return {"message_thread_id": r.topic_id}


class TelegramStore:
    """Dedicated store for Telegram-specific state (offset, topics).
    Encapsulates schema creation and data access so the adapter doesn't
    execute raw SQL or manage schema directly."""

    def __init__(self, db) -> None:
        self.db = db
        self._init_schema()

    def _init_schema(self) -> None:
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS telegram_meta (key TEXT PRIMARY KEY, value TEXT)"
        )
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS telegram_topics (name TEXT PRIMARY KEY, topic_id INTEGER)"
        )

    def get_offset(self) -> int:
        row = self.db.execute(
            "SELECT value FROM telegram_meta WHERE key = 'offset'"
        ).fetchone()
        return int(row["value"]) if row else 0

    def set_offset(self, offset: int) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO telegram_meta (key, value) VALUES ('offset', ?)",
            (str(offset),)
        )

    def get_topic_id(self, name: str) -> int | None:
        row = self.db.execute(
            "SELECT topic_id FROM telegram_topics WHERE name = ?", (name,)
        ).fetchone()
        return row["topic_id"] if row else None

    def set_topic_id(self, name: str, topic_id: int) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO telegram_topics (name, topic_id) VALUES (?, ?)",
            (name, topic_id)
        )


class TelegramAdapter:
    _FORUM_TOPICS = ("reminders",)

    def __init__(self, cfg, store, dispatcher):
        if not cfg.telegram_bot_token:
            raise SystemExit(
                "TELEGRAM_BOT_TOKEN not set — see .env.example"
            )
        if not cfg.telegram_allowed_chats:
            raise SystemExit(
                "TELEGRAM_ALLOWED_CHAT_IDS is empty (fail-closed). Add your chat "
                "id — DM the bot then check /status output, or use @userinfobot."
            )
        self.cfg = cfg
        self.store = store
        self._dispatcher = dispatcher
        self._api = f"https://api.telegram.org/bot{cfg.telegram_bot_token}"
        self._client = httpx.AsyncClient(
            timeout=cfg.telegram_poll_timeout_s + 10
        )
        # In-memory state for reachability and last sent message ID
        self._unreachable: set[int | str] = set()
        self._last_sent_id: int | None = None
        self.tg_store = TelegramStore(store.db)

    # ── Bot API helpers ───────────────────────────────────────────────

    def _format_for_telegram(self, text: str) -> str:
        text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        def code_repl(m):
            return f"<pre>{m.group(1)}</pre>"
        text = re.sub(r'```(?:\w+\n)?(.*?)```', code_repl, text, flags=re.DOTALL)

        def inline_code_repl(m):
            return f"<code>{m.group(1)}</code>"
        text = re.sub(r'`([^`]+)`', inline_code_repl, text)

        # Headers have no HTML equivalent Telegram renders distinctly, so fold
        # them into bold — better than leaving literal leading '#'s on screen.
        text = re.sub(r'^#{1,6}[ \t]+(.+)$', r'<b>\1</b>', text, flags=re.MULTILINE)

        text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
        text = re.sub(r'(?<!\*)\*([^\*]+)\*(?!\*)', r'<i>\1</i>', text)
        text = re.sub(r'(?<!_)__(.*?)__(?!_)', r'<b>\1</b>', text)
        text = re.sub(r'(?<!_)_([^_]+)_(?!_)', r'<i>\1</i>', text)

        # Markdown links: [text](url) -> <a href="url">text</a>.
        text = re.sub(r'\[([^\]]+)\]\((https?://[^\s)]+)\)', r'<a href="\2">\1</a>', text)

        # Bullet lists: leading '-'/'*' at line start becomes a bullet glyph.
        text = re.sub(r'^[ \t]*[-*][ \t]+(.+)$', r'• \1', text, flags=re.MULTILINE)
        return text

    async def _call(self, method: str, **params):
        """One Bot API call. Raises TelegramError (already redacted, and marked
        permanent/transient) instead of leaking httpx's URL-bearing errors."""
        try:
            r = await self._client.post(f"{self._api}/{method}", json=params)
        except httpx.HTTPError as e:
            raise TelegramError(
                f"{method}: {self._redact(str(e))}"
            ) from None
        if r.status_code >= 400:
            try:
                desc = str(r.json().get("description", ""))
            except ValueError:
                desc = r.text[:200]
            raise TelegramError(
                f"{method}: HTTP {r.status_code} {self._redact(desc)}",
                permanent=r.status_code in (400, 403) and bool(_PERMANENT.search(desc)),
            ) from None
        try:
            return r.json()
        except ValueError as e:
            raise TelegramError(f"{method}: bad JSON ({e})") from None

    async def _load_offset(self) -> int:
        """Retrieve the last processed offset from durable storage."""
        return self.tg_store.get_offset()

    async def _save_offset(self, offset: int) -> None:
        """Persist the last processed offset to durable storage."""
        self.tg_store.set_offset(offset)

    # ── Bot API helpers ────────────────────────
    #
    # Additional helper methods for sending and editing messages

    async def _send(
        self, chat_id: int | str, text: str, keyboard: list | None = None
    ) -> bool:
        """Deliver one message asynchronously. Returns True only if Telegram accepted it."""
        if text.startswith("mail_ping:"):
            parts = text.split(":", 2)
            if len(parts) == 3:
                _, msg_id, sender = parts
                text = f"📧 New email from {sender}"
                keyboard = [
                    [
                        {"text": "[ Full ]", "callback_data": f"mail_action:full:{msg_id}"},
                        {"text": "[ Summary ]", "callback_data": f"mail_action:summary:{msg_id}"},
                        {"text": "[ Remind me ]", "callback_data": f"mail_action:remind:{msg_id}"},
                        {"text": "[ Add task ]", "callback_data": f"mail_action:task:{msg_id}"},
                        {"text": "[ Mute ]", "callback_data": f"mail_action:mute:{msg_id}"},
                    ]
                ]

        route = parse_route(str(chat_id))
        bare_chat = route.chat_id if route is not None else chat_id
        thread_kwargs = send_kwargs(str(chat_id))

        self._last_sent_id = None
        chunks = split_markdown_safely(text, 4000) if text else [" "]
        for i, chunk in enumerate(chunks):
            chunk = chunk or " "
            formatted_chunk = self._format_for_telegram(chunk)
            params: dict[str, Any] = {
                "chat_id": bare_chat,
                "text": formatted_chunk,
                "parse_mode": "HTML",
                **thread_kwargs,
            }
            if keyboard and i == len(chunks) - 1:
                params["reply_markup"] = {"inline_keyboard": keyboard}
            try:
                resp = await self._call("sendMessage", **params)
                self._last_sent_id = (resp.get("result") or {}).get(
                    "message_id"
                )
            except TelegramError as e:
                # Fallback if HTML parsing fails due to chunking splitting a tag
                if "can't parse entities" in str(e).lower():
                    params.pop("parse_mode", None)
                    params["text"] = chunk
                    try:
                        resp = await self._call("sendMessage", **params)
                        self._last_sent_id = (
                            (resp.get("result") or {}).get("message_id")
                        )
                        continue
                    except TelegramError:
                        pass

                if e.permanent:
                    if bare_chat not in self._unreachable:
                        self._unreachable.add(bare_chat)
                        log.warning(
                            "chat %s is unreachable (%s) — it must DM the bot "
                            "first; suppressing further warnings for it",
                            bare_chat, e,
                        )
                    else:
                        log.debug("chat %s still unreachable: %s", bare_chat, e)
                else:
                    log.warning("sendMessage failed for %s: %s", bare_chat, e)
                return False
        if bare_chat in self._unreachable:
            self._unreachable.discard(bare_chat)
            log.info("chat %s is reachable again", bare_chat)
        return True

    async def _edit(self, chat_id: int | str, message_id: int, text: str,
                   keyboard: list | None = None) -> None:
        """Rewrite a message asynchronously."""
        try:
            params: dict[str, Any] = {
                "chat_id": chat_id,
                "message_id": message_id,
                "text": text[:4000],
            }
            if keyboard is not None:
                params["reply_markup"] = {"inline_keyboard": keyboard}
            await self._call("editMessageText", **params)
        except TelegramError as e:
            log.debug("editMessageText failed for %s/%s: %s", chat_id, message_id, e)

    async def _answer_cb(self, cb_id: str, text: str = "") -> None:
        """Clear the client‑side spinner asynchronously."""
        try:
            await self._call(
                "answerCallbackQuery",
                callback_query_id=cb_id,
                text=text[:200],
            )
        except TelegramError as e:
            log.debug("answerCallbackQuery failed: %s", e)

    def _approval_kb(self, approval_id: int) -> list:
        """Return an inline‑keyboard for approving or rejecting the given
        approval ID."""
        return [
            [
                {"text": "✅ Approve",
                 "callback_data": f"a:{approval_id}"},
                {"text": "❌ Reject",
                 "callback_data": f"r:{approval_id}"},
            ]
        ]

    @staticmethod
    def _parse_cb(data: str):
        """Parse callback data and return a (action, id) tuple if valid."""
        parts = data.split(":", 1)
        if len(parts) != 2:
            return None
        kind, num_str = parts
        if kind not in ("a", "r"):
            return None
        try:
            n = int(num_str)
        except ValueError:
            return None
        if n < 0:
            return None
        return kind, n

    async def _handle_callback(self, data: str, callback_query: dict) -> None:
        """Handle a callback query from Telegram.

        The method is intentionally minimal; subclasses or callers can extend it.
        It parses the callback data, acknowledges the query to clear the spinner,
        and delegates to `_decide_cb` when appropriate.
        """
        mail_match = re.match(r'^mail_action:(.+):(.+)$', data)
        if mail_match:
            action, msg_id = mail_match.groups()
            try:
                from semai.core.intents import MarkMailRead
                from semai.workers.mail import MarkMailReadWorker
                worker = MarkMailReadWorker()
                intent = MarkMailRead(
                    kind="mark_mail_read",
                    msg_id=msg_id,
                    confidence=1.0,
                    raw_utterance=f"mail_action:{action}:{msg_id}",
                )
                await asyncio.to_thread(worker, intent)
            except Exception as e:
                log.error("Failed to invoke MarkMailReadWorker: %s", e)
            
            if hasattr(self, "_dispatcher") and self._dispatcher is not None:
                utterance_by_action = {
                    "full": f"show full email {msg_id}",
                    "summary": f"summarize email {msg_id}",
                    "remind": f"remind me about email {msg_id}",
                    "task": f"add task from email {msg_id}",
                    "mute": f"mute email {msg_id}",
                }
                utterance = utterance_by_action.get(
                    action, f"Handle email {msg_id} action {action}"
                )
                chat_id = callback_query.get("message", {}).get("chat", {}).get("id")
                result = await asyncio.to_thread(self._dispatcher.dispatch, utterance)
                if chat_id and result and hasattr(result, "message"):
                    await self._send(chat_id, result.message)
            
            await self._answer_cb(callback_query.get("id", ""), "Action processed")
            return

        parsed = self._parse_cb(data)
        if not parsed:
            await self._answer_cb(callback_query.get("id", ""), "Invalid action")
            return
        kind, approval_id = parsed
        # Currently only approve/reject are supported. The decision logic
        # should be implemented in `_decide_cb`; here we just log.
        log.debug(
            "_handle_callback: kind=%s, approval_id=%s, query=%s",
            kind,
            approval_id,
            callback_query,
        )
        await self._answer_cb(callback_query.get("id", ""), "")

    async def _decide_cb(self, data: str, callback_query: dict) -> None:
        """Build a `Confirm` intent from the callback and resolve it.

        This method demonstrates how to construct a confirmation intent
        (`semai.core.intents.Confirm`) with the raw utterance from the user,
        then invoke the dispatcher's private `_resolve_confirm` path via
        ``asyncio.to_thread``.  It edits the original message to remove
        the inline‑keyboard and sends a textual reply.
        """
        parsed = self._parse_cb(data)
        if not parsed:
            await self._answer_cb(callback_query.get("id", ""), "Invalid action")
            return

        kind, approval_id = parsed
        # Retrieve raw utterance – in this simplified example we just use the
        # placeholder string.  Real implementations would look up the pending
        # approval record in a store.
        raw_utterance = f"Confirm #{approval_id}"
        from semai.core.intents import Confirm

        intent = Confirm(
            kind="confirm",
            confidence=1.0,
            raw_utterance=raw_utterance,
            approval_id=approval_id,
            accept=(kind == "a"),
        )
        # Document that we are calling the private confirm-resolution path.
        log.debug(
            "_decide_cb: resolving confirm for approval #%s via _resolve_confirm",
            approval_id,
        )
        if hasattr(self, "_dispatcher") and self._dispatcher is not None:
            await asyncio.to_thread(
                self._dispatcher._resolve_confirm, intent
            )

        # Edit the message to remove buttons and reply with a confirmation.
        chat_id = callback_query.get("chat", {}).get("id")
        msg_id = callback_query.get("message", {}).get("message_id")
        if chat_id is not None and msg_id is not None:
            await self._edit(chat_id, msg_id, "Done.")
        await self._answer_cb(callback_query.get("id", ""), "")

    async def _ensure_forum_topics(self, store=None) -> None:
        chat_id = self.cfg.telegram_forum_chat_id
        if chat_id is None:
            return
        for name in self._FORUM_TOPICS:
            topic_id = self.tg_store.get_topic_id(name)
            if topic_id is not None:
                continue
            try:
                resp = await self._call(
                    "createForumTopic",
                    chat_id=chat_id,
                    name=name.capitalize(),
                )
                new_topic_id = (resp.get("result") or {}).get("message_thread_id")
                if new_topic_id is not None:
                    self.tg_store.set_topic_id(name, new_topic_id)
                    log.info(
                        "created forum topic %r (id=%s) in chat %s",
                        name,
                        new_topic_id,
                        chat_id,
                    )
            except TelegramError as e:
                log.warning(
                    "could not create forum topic %r in chat %s: %s",
                    name,
                    chat_id,
                    e,
                )

    def _topic_route(self, store, chat_id: int, capability: str) -> str:
        if chat_id == self.cfg.telegram_forum_chat_id:
            topic_id = self.tg_store.get_topic_id(capability)
            if topic_id is not None:
                return build_route(chat_id, topic_id)
        return str(chat_id)

    async def _handle_message(self, upd: dict) -> None:
        msg = upd.get("message")
        if not msg:
            return
        chat_id = msg["chat"]["id"]
        # Allowlist check
        if chat_id not in self.cfg.telegram_allowed_chats:
            log.debug("Ignoring message from unallowed chat %s", chat_id)
            return
        text = msg.get("text") or ""
        if text.startswith("/rule"):
            try:
                with open("10-Memory/Rules/EmailRules.md", "r", encoding="utf-8") as f:
                    content = f.read()
                await self._send(chat_id, content)
            except Exception as e:
                await self._send(chat_id, f"Failed to read rules: {e}")
            return

        if text.startswith("/memory"):
            try:
                import sqlite3
                conn = sqlite3.connect(".state-semai/mail_state.sqlite3")
                try:
                    cursor = conn.cursor()
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                    tables = cursor.fetchall()
                    lines = []
                    for (tname,) in tables:
                        lines.append(f"Table: {tname}")
                        cursor.execute(f"SELECT * FROM {tname}")
                        for row in cursor.fetchall():
                            lines.append(str(row))
                finally:
                    conn.close()
                dump_str = "\n".join(lines)
                if len(dump_str) > 4000:
                    dump_str = dump_str[:3997] + "..."
                await self._send(chat_id, dump_str if dump_str else "Memory is empty.")
            except Exception as e:
                await self._send(chat_id, f"Failed to read memory: {e}")
            return

        # Drop non-text messages and slash commands
        if not text.startswith("/"):
            if getattr(self.cfg, "agent_enabled", False):
                # Use the bounded tool-calling Agent instead of the
                # single-shot dispatcher.
                from semai.agent import Agent
                from semai.providers.ollama import OllamaProvider

                llm = OllamaProvider(self.cfg.ollama_base_url)
                agent = Agent(self.cfg, llm, self._dispatcher._registry)
                res = await agent.run(text)
                await self._send(chat_id, res.answer)
                for kind, action in res.proposals:
                    approval_id = self._dispatcher._approval_store.create(kind, action)
                    kb = self._approval_kb(approval_id)
                    await self._send(
                        chat_id,
                        f"Approval #{approval_id} needed: {getattr(action, 'description', '')}",
                        keyboard=kb,
                    )
            else:
                # Dispatch in separate thread to avoid blocking the event loop
                result = await asyncio.to_thread(self._dispatcher.dispatch, text)
                await self._send(chat_id, result.message)
                if not result.ok and "approval_id" in getattr(result, "data", {}):
                    approval_id = result.data["approval_id"]
                    kb = self._approval_kb(approval_id)
                    await self._send(
                        chat_id,
                        f"Approval #{approval_id} needed",
                        keyboard=kb,
                    )

    async def run(self) -> None:
        """Async long‑polling loop."""
        try:
            me = (await self._call("getMe")).get("result", {})
            log.info("Telegram bot ready: %s", me)
            offset = await self._load_offset()
            while True:
                resp = await self._call(
                    "getUpdates",
                    offset=offset,
                    timeout=self.cfg.telegram_poll_timeout_s,
                )
                updates = resp.get("result", [])
                if not updates:
                    continue
                for upd in updates:
                    log.debug("got update %s", upd)
                    offset = max(offset, int(upd["update_id"]) + 1)
                    await self._handle_message(upd)
        except TelegramError as e:
            log.warning("Telegram error: %s", e)
        finally:
            await self._client.aclose()

    # ── redact helper ───────────────────────────────────────────────

    def _redact(self, text: str) -> str:
        """Replace the bot token wherever it appears. The token is the URL path
        of every Bot API request, so anything derived from a request — an httpx
        exception string above all — carries the credential until this runs."""
        return text.replace(self.cfg.telegram_bot_token or "\0", "<TOKEN>")


async def _amain() -> int:  # pragma: no cover
    from semai.config.schema import Settings
    from semai.memory.store import Store
    from semai.adapters.cli import build_dispatcher

    try:
        settings = Settings.load()
    except Exception as e:
        print(f"fatal: {e}", file=sys.stderr)
        return 1

    store = Store(settings.db_path)
    dispatcher = build_dispatcher(settings)
    adapter = TelegramAdapter(settings, store, dispatcher)
    await adapter.run()
    return 0


def main() -> int:
    return asyncio.run(_amain())


if __name__ == "__main__":
    raise SystemExit(main())
```

Target file: `src/semai/adapters/telegram.py` in the SemAI repo (current file
content pasted below — edit in place, return the complete updated file).

Root cause being fixed: `semai.adapters.push.deliver()` writes a `kind='alert'`
row into the shared `tasks` table (via `store.enqueue()` + `store.finish()`)
but nothing ever reads it back out and sends it via Telegram — `reply_to` and
`kind='alert'` are written once and never queried anywhere else in the
codebase. Add the missing consumer to `TelegramAdapter`.

Three changes, all in this one file, nothing else:

1. Add one import alongside the existing ones at the top of the file, for a
   helper that returns the current UTC time as an ISO string:
   `from semai.adapters.task_store import now_iso`

2. Add a new async method to `TelegramAdapter`, `_poll_alerts(self) -> None`,
   placed near `run()`. Contract:
   - Runs forever (`while True`), sleeping 5.0 seconds between iterations
     (hardcoded — no configurable interval, this isn't a config knob task).
   - Each iteration, query `self.store.db` (a `sqlite3.Connection` with
     `row_factory` already set so `row["col"]` indexing works — see
     `TelegramStore` in this same file for the existing pattern) for rows
     where `kind = 'alert'`, `status = 'done'`, `last_notify IS NULL`, and
     `reply_to IS NOT NULL`, oldest first. Select `id, reply_to, result`.
   - For each row: call `await self._send(reply_to, result or "")`. If it
     returns `True`, set that row's `last_notify` to `now_iso()` (so it is
     never sent twice); if `False`, leave it NULL so the next tick retries.
   - Wrap each iteration's body in `try/except Exception`, logging a warning
     (`log.warning(...)`) on failure and continuing the loop — one bad
     iteration must never kill the poller.

3. In `run()`, start `_poll_alerts` as a background `asyncio` task before
   entering the existing `while True:` update-polling loop, and cancel +
   await that task in the existing `finally:` block (before
   `self._client.aclose()`), swallowing `asyncio.CancelledError`. Do not
   change anything else about `run()`'s existing logic or control flow.

Do not modify any other method, class, or the module docstring. Do not add
retries, backoff, or a configurable poll interval. Reply with only the
complete updated file content, no prose before or after, no markdown fence
unless it wraps the whole file.
