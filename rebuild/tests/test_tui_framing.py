from scripts import tui_framing


def test_build_framed_prompt_prefixes_and_preserves_raw():
    raw = "claim the next task and dispatch it"
    framed = tui_framing.build_framed_prompt(raw)
    assert framed.startswith(tui_framing.FRAMING_PREFIX)
    assert framed.endswith(raw)
    assert raw in framed
