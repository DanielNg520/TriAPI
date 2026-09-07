from scripts import tui_stream


class _FakeStdout:
    def __init__(self, lines):
        self._lines = iter(lines)

    def __iter__(self):
        return self

    def __next__(self):
        return next(self._lines)


class _FakeProcess:
    def __init__(self, lines):
        self.stdout = _FakeStdout(lines)
        self.waited = False

    def wait(self):
        self.waited = True


def test_stream_claude_output_yields_lines_and_strips_newline(monkeypatch):
    fake_proc = _FakeProcess(["line one\n", "line two\n"])

    def fake_popen(cmd, stdout=None, stderr=None, text=None):
        assert cmd == ["claude", "-p", "hello"]
        return fake_proc

    monkeypatch.setattr(tui_stream.subprocess, "Popen", fake_popen)

    lines = list(tui_stream.stream_claude_output("hello"))
    assert lines == ["line one", "line two"]
    assert fake_proc.waited is True


def test_stream_claude_output_stops_cleanly_on_empty_output(monkeypatch):
    fake_proc = _FakeProcess([])
    monkeypatch.setattr(tui_stream.subprocess, "Popen", lambda *a, **k: fake_proc)

    assert list(tui_stream.stream_claude_output("hello")) == []
