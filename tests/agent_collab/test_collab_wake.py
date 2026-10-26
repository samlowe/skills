"""Tests for collab.py's Codex wake mode, with a stub codex on PATH."""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from pathlib import Path

import pytest

from tests.agent_collab.collab_helpers import CollabRepo, Watcher, wait_for, wait_until

StartWatch = Callable[..., Watcher]
_CALL_SEPARATOR = "\n--- end of call ---\n"


class StubCodex:
    """A fake codex executable that records each call's arguments."""

    def __init__(self, bin_dir: Path) -> None:
        """Write the stub into bin_dir; it succeeds until fail() is called."""
        self.calls_path = bin_dir / "codex-calls.log"
        self.fail_path = bin_dir / "codex-should-fail"
        script = bin_dir / "codex"
        script.write_text(
            "#!/bin/sh\n"
            f"printf '%s\\n' \"$@\" >> '{self.calls_path}'\n"
            f"printf '{_CALL_SEPARATOR}' >> '{self.calls_path}'\n"
            f"if [ -e '{self.fail_path}' ]; then echo 'Read-only file system' >&2; exit 1; fi\n"
            "echo 'Queued message q1 for thread T.'\n",
        )
        script.chmod(0o755)

    def fail(self) -> None:
        """Make later calls exit with an error."""
        self.fail_path.touch()

    def calls(self) -> list[list[str]]:
        """Return each call's arguments, in order."""
        if not self.calls_path.exists():
            return []
        chunks = self.calls_path.read_text().split(_CALL_SEPARATOR)
        return [chunk.strip("\n").split("\n") for chunk in chunks if chunk.strip()]


@pytest.fixture
def codex(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> StubCodex:
    """Put a stub codex first on PATH and set the Codex thread id, as Codex does."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("CODEX_THREAD_ID", "thread-123")
    return StubCodex(bin_dir)


def _queued_text(call: list[str]) -> str:
    """Return the --message text from a codex queue call."""
    return "\n".join(call[call.index("--message") + 1 :])


def test_join_as_codex_prints_wake_watch_command(repo: CollabRepo) -> None:
    output = repo.join("cody", harness="codex")

    assert "watch --as cody --wake codex" in output


def test_wake_codex_refuses_outside_a_codex_session(
    repo: CollabRepo,
    start_watch: StartWatch,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    repo.join("cody", harness="codex")

    watcher = start_watch("cody", "--wake", "codex")

    assert "needs CODEX_THREAD_ID" in watcher.read_until("The watcher failed")
    assert watcher.wait_for_exit() == 1


def test_wake_codex_queues_pointer_once_and_leaves_messages_unread(
    repo: CollabRepo,
    start_watch: StartWatch,
    codex: StubCodex,
) -> None:
    repo.join("alice")
    repo.join("cody", harness="codex")
    watcher = start_watch("cody", "--wake", "codex")
    wait_for(repo.alive_path("cody"))

    repo.send("alice", "cody", "first")
    watcher.read_until("Woke Codex")

    [call] = codex.calls()
    assert call[:3] == ["queue", "--thread", "thread-123"]
    text = _queued_text(call)
    assert "1 new message for cody from alice" in text
    assert "not a message from the user" in text
    assert text.endswith("inbox --as cody")

    inbox = repo.inbox("cody")
    assert "first" in inbox
    time.sleep(2)
    assert len(codex.calls()) == 1


def test_wake_codex_wakes_again_for_later_messages_but_not_announcements(
    repo: CollabRepo,
    start_watch: StartWatch,
    codex: StubCodex,
) -> None:
    repo.join("alice")
    repo.join("cody", harness="codex")
    watcher = start_watch("cody", "--wake", "codex")
    wait_for(repo.alive_path("cody"))

    repo.join("bob")
    time.sleep(2)
    assert codex.calls() == []

    repo.send("alice", "cody", "first")
    watcher.read_until("Woke Codex")
    repo.send("bob", "*", "second")
    wait_until(lambda: len(codex.calls()) == 2, "no second wake-up")

    assert "1 new message for cody from bob" in _queued_text(codex.calls()[1])


def test_wake_codex_backs_off_after_failure_and_keeps_messages(
    repo: CollabRepo,
    start_watch: StartWatch,
    codex: StubCodex,
) -> None:
    codex.fail()
    repo.join("alice")
    repo.join("cody", harness="codex")
    watcher = start_watch("cody", "--wake", "codex")
    wait_for(repo.alive_path("cody"))

    repo.send("alice", "cody", "first")

    output = watcher.read_until("Retrying in 5s")
    assert "codex queue exited 1: Read-only file system" in output
    time.sleep(3)
    assert len(codex.calls()) == 1
    assert "first" in repo.inbox("cody")


def test_wake_codex_holds_the_heartbeat_so_self_check_is_quiet(
    repo: CollabRepo,
    start_watch: StartWatch,
    codex: StubCodex,
) -> None:
    repo.join("cody", harness="codex")
    start_watch("cody", "--wake", "codex")
    wait_for(repo.alive_path("cody"))

    assert "Your watcher isn't running" not in repo.inbox("cody")


def test_reply_to_a_user_only_batch_goes_to_the_user(repo: CollabRepo) -> None:
    repo.join("alice")
    repo.send("user", "alice", "hello")

    assert "send --as alice --to user <<'EOF'" in repo.inbox("alice")
