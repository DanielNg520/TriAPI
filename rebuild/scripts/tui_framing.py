"""Fixed supervisor-role framing prepended to every `triapi tui` prompt
before it's sent to `claude -p` -- each call is fresh and memory-less, so
this reminds it it's operating as TriAPI's supervisor.
"""

FRAMING_PREFIX = (
    "You are operating as TriAPI's supervisor for this repository. "
    "Follow AGENTS.md (hub-and-spoke: DeepSeek/agy write, you audit every "
    "response before the next step) and rebuild/RULES.md. Task:\n\n"
)


def build_framed_prompt(raw_prompt: str) -> str:
    """Return FRAMING_PREFIX + raw_prompt, unchanged otherwise -- do not
    alter raw_prompt's own content, only prepend the fixed prefix
    already defined above as the module-level constant FRAMING_PREFIX.
    """
    return FRAMING_PREFIX + raw_prompt
