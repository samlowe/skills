"""Tests for collab.py's watcher, heartbeat and self-check."""

from __future__ import annotations

import signal
import time
from collections.abc import Callable

from tests.agent_collab.collab_helpers import (
    CollabRepo,
    Watcher,
    make_stale,
    wait_for,
    wait_until,
)

StartWatch = Callable[..., Watcher]
_WARNING = "Your watcher isn't running"


def test_watch_prints_message_promptly_through_a_pipe(
    repo: CollabRepo,
    start_watch: StartWatch,
) -> None:
    repo.join("alice")
    repo.join("bob")
    watcher = start_watch("bob", "--max-seconds", "30")
    wait_for(repo.alive_path("bob"))

    repo.send("alice", "bob", "short note")

    output = watcher.read_until("EOF")
    assert "This is alice (stratacode), on behalf of the user:\nshort note" in output
    assert 'You are "bob" in an agent collaboration' in output
    assert watcher.process.poll() is None


def test_watch_exits_after_leave_and_cleans_up(
    repo: CollabRepo,
    start_watch: StartWatch,
) -> None:
    repo.join("bob")
    watcher = start_watch("bob", "--max-seconds", "30")
    wait_for(repo.alive_path("bob"))

    repo.ok("leave", "--as", "bob")

    watcher.read_until("You have left the collaboration. The watcher has stopped.")
    assert watcher.wait_for_exit() == 0
    assert not repo.alive_path("bob").exists()
    assert not (repo.folder / "agents" / "bob.json").exists()


def test_watch_max_seconds_prints_rearm_footer_and_restart_misses_nothing(
    repo: CollabRepo,
    start_watch: StartWatch,
) -> None:
    repo.join("alice")
    repo.join("bob", harness="claude-code")
    first = start_watch("bob", "--max-seconds", "1")

    output = first.read_until("--max-seconds 1")
    assert "The watcher has exited; start it again with:" in output
    assert first.wait_for_exit() == 0
    assert not repo.alive_path("bob").exists()

    repo.send("alice", "bob", "sent in the gap")
    second = start_watch("bob", "--max-seconds", "30")
    assert "sent in the gap" in second.read_until("EOF")


def test_sigterm_exits_cleanly_and_self_check_warns_at_once(
    repo: CollabRepo,
    start_watch: StartWatch,
) -> None:
    repo.join("bob")
    watcher = start_watch("bob")
    wait_for(repo.alive_path("bob"))
    assert _WARNING not in repo.inbox("bob")

    assert watcher.send_signal(signal.SIGTERM) == 0
    assert not repo.alive_path("bob").exists()
    assert _WARNING in repo.inbox("bob")


def test_sigint_exits_cleanly(repo: CollabRepo, start_watch: StartWatch) -> None:
    repo.join("bob")
    watcher = start_watch("bob")
    wait_for(repo.alive_path("bob"))

    assert watcher.send_signal(signal.SIGINT) == 0
    assert not repo.alive_path("bob").exists()
    assert "Traceback" not in (
        watcher.process.stderr.read() if watcher.process.stderr else ""
    )


def test_sigkill_leaves_heartbeat_that_warns_once_stale(
    repo: CollabRepo,
    start_watch: StartWatch,
) -> None:
    repo.join("bob")
    watcher = start_watch("bob")
    wait_for(repo.alive_path("bob"))

    watcher.send_signal(signal.SIGKILL)

    assert repo.alive_path("bob").exists()
    assert _WARNING not in repo.inbox("bob")
    make_stale(repo.alive_path("bob"))
    assert _WARNING in repo.inbox("bob")


def test_send_self_check_warns_with_restart_command(repo: CollabRepo) -> None:
    repo.join("alice", harness="claude-code")

    output = repo.send("alice", "*", "hello")

    assert _WARNING in output
    assert "watch --as alice --max-seconds 1740" in output
    assert "Sent #2 to *." in output


def test_send_self_check_is_quiet_while_watcher_runs(
    repo: CollabRepo,
    start_watch: StartWatch,
) -> None:
    repo.join("alice")
    start_watch("alice", "--max-seconds", "30")
    wait_for(repo.alive_path("alice"))

    assert _WARNING not in repo.send("alice", "*", "hello")
    assert "watcher running" in repo.ok("who")


def test_who_reports_stale_heartbeat_as_not_running(repo: CollabRepo) -> None:
    repo.join("alice")
    repo.alive_path("alice").write_text("someone\n")
    assert "alice (stratacode)" in repo.ok("who")
    assert ", watcher running" in repo.ok("who")

    make_stale(repo.alive_path("alice"))

    assert "watcher not running" in repo.ok("who")


def test_join_refuses_name_with_live_watcher_and_accepts_stale(
    repo: CollabRepo,
) -> None:
    repo.join("alice")
    repo.alive_path("alice").write_text("other-session\n")

    refused = repo.run("join", "--as", "alice", "--harness", "stratacode")
    make_stale(repo.alive_path("alice"))
    accepted = repo.run("join", "--as", "alice", "--harness", "stratacode")

    assert refused.returncode == 1
    assert "already has a running watcher" in refused.stderr
    assert accepted.returncode == 0


def test_superseded_watcher_stops_beating_and_leaves_newer_heartbeat(
    repo: CollabRepo,
    start_watch: StartWatch,
) -> None:
    repo.join("bob")
    watcher = start_watch("bob")
    wait_for(repo.alive_path("bob"))
    repo.alive_path("bob").write_text("newer-watcher\n")
    make_stale(repo.alive_path("bob"))
    stale_mtime = repo.alive_path("bob").stat().st_mtime

    time.sleep(6.5)

    assert repo.alive_path("bob").stat().st_mtime == stale_mtime
    assert watcher.send_signal(signal.SIGTERM) == 0
    assert repo.alive_path("bob").read_text() == "newer-watcher\n"


def test_watcher_beats_while_it_holds_the_name(
    repo: CollabRepo,
    start_watch: StartWatch,
) -> None:
    repo.join("bob")
    start_watch("bob")
    alive_path = repo.alive_path("bob")
    wait_for(alive_path)
    make_stale(alive_path)
    stale_mtime = alive_path.stat().st_mtime

    wait_until(
        lambda: alive_path.stat().st_mtime > stale_mtime,
        "the watcher never beat",
    )

    assert "watcher running" in repo.ok("who")


def test_beat_after_leave_never_recreates_presence(
    repo: CollabRepo,
    start_watch: StartWatch,
) -> None:
    repo.join("bob")
    watcher = start_watch("bob", "--max-seconds", "30")
    wait_for(repo.alive_path("bob"))

    repo.ok("leave", "--as", "bob")
    watcher.wait_for_exit()

    assert not (repo.folder / "agents" / "bob.json").exists()
    assert not repo.alive_path("bob").exists()


def test_watch_refuses_name_that_has_not_joined(
    repo: CollabRepo,
    start_watch: StartWatch,
) -> None:
    repo.join("alice")
    watcher = start_watch("bob")

    output = watcher.read_until("The watcher failed")

    assert "hasn't joined" in output
    assert watcher.wait_for_exit() == 1
