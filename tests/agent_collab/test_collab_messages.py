"""Tests for collab.py's message folder, delivery rules and one-shot commands."""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

from tests.agent_collab.collab_helpers import COLLAB_SCRIPT, CollabRepo


def _publish_raw_message(repo: CollabRepo, sender: str, sent_at: datetime) -> None:
    """Publish a message file directly, with a chosen timestamp, under the next number."""
    number = len(repo.message_files()) + 1
    ts = sent_at.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    path = repo.folder / "messages" / f"{number:08d}.md"
    path.write_text(
        f"---\nts: {ts}\nfrom: {sender}\nharness: stratacode\nto: *\n---\nbody\n"
    )


def test_join_creates_self_ignoring_folder_at_repo_root(repo: CollabRepo) -> None:
    output = repo.join("alice")

    assert (repo.folder / ".gitignore").read_text() == "*\n"
    assert f"in {repo.root}" in output
    assert not (repo.root / "work" / ".agent-collab").exists()
    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=repo.root,
        capture_output=True,
        text=True,
        check=True,
    )
    assert ".agent-collab" not in status.stdout


def test_concurrent_sends_get_gapless_numbers_and_complete_files(
    repo: CollabRepo,
) -> None:
    repo.join("alice")
    bodies = [f"message {index}\nsecond line" for index in range(12)]

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(
            pool.map(
                lambda body: repo.run("send", "--as", "user", "--to", "*", stdin=body),
                bodies,
            )
        )

    assert all(result.returncode == 0 for result in results)
    files = repo.message_files()
    assert [path.name for path in files] == [
        f"{number:08d}.md" for number in range(1, 14)
    ]
    texts = [path.read_text() for path in files[1:]]
    assert sorted(text.split("---\n", 2)[2].strip() for text in texts) == sorted(bodies)
    assert not list((repo.folder / "messages").glob(".tmp-*"))


def test_message_file_has_header_and_body(repo: CollabRepo) -> None:
    repo.join("alice", harness="claude-code")
    repo.join("bob")

    repo.send("alice", "bob", "Can you review runner.py?\n")

    text = repo.message_files()[-1].read_text()
    header, body = text.removeprefix("---\n").split("---\n", 1)
    assert "from: alice\nharness: claude-code\nto: bob\n" in header
    assert header.startswith("ts: ")
    assert body == "Can you review runner.py?\n"


def test_delivery_skips_own_and_others_messages(repo: CollabRepo) -> None:
    for name in ("alice", "bob", "carol"):
        repo.join(name)
    repo.inbox("bob")

    repo.send("carol", "alice", "for alice only")
    repo.send("bob", "*", "from bob to everyone")
    repo.send("carol", "*", "carol to everyone")
    repo.send("alice", "bob", "alice to bob")

    output = repo.inbox("bob")
    assert "2 new messages for bob" in output
    assert "carol to everyone" in output
    assert "This is carol (stratacode), on behalf of the user, to everyone:" in output
    assert "alice to bob" in output
    assert "for alice only" not in output
    assert "from bob to everyone" not in output
    assert "No new messages for bob" in repo.inbox("bob")


def test_incoming_message_survives_recipient_sending_first(repo: CollabRepo) -> None:
    repo.join("alice")
    repo.join("bob")
    repo.inbox("bob")

    repo.send("alice", "bob", "question for bob")
    repo.send("bob", "alice", "unrelated note")

    assert "question for bob" in repo.inbox("bob")


def test_join_announces_and_peer_sees_it(repo: CollabRepo) -> None:
    repo.join("alice", harness="claude-code")
    repo.join("bob")

    output = repo.inbox("alice")

    assert "#2 · bob (stratacode) joined · no reply needed" in output


def test_new_name_starts_after_existing_history(repo: CollabRepo) -> None:
    repo.join("alice")
    repo.send("user", "*", "early message")

    output = repo.join("bob")

    assert "Recent history (already read):" in output
    assert "early message" in output
    assert "new message" not in output
    assert "No new messages for bob" in repo.inbox("bob")


def test_rejoin_keeps_cursor_and_delivers_missed_messages(repo: CollabRepo) -> None:
    repo.join("alice")
    repo.join("bob")
    repo.inbox("bob")
    repo.ok("leave", "--as", "bob")

    repo.send("alice", "bob", "while you were away")
    output = repo.join("bob")

    assert "1 new message for bob" in output
    assert "while you were away" in output


def test_leave_announces_and_removes_presence(repo: CollabRepo) -> None:
    repo.join("alice")
    repo.join("bob")
    repo.inbox("alice")

    repo.ok("leave", "--as", "bob")

    assert not (repo.folder / "agents" / "bob.json").exists()
    assert "bob (stratacode) left · no reply needed" in repo.inbox("alice")
    assert "bob" not in repo.ok("who")


def test_commands_refuse_a_name_that_has_not_joined(repo: CollabRepo) -> None:
    repo.join("alice")

    result = repo.run("inbox", "--as", "bob")

    assert result.returncode == 1
    assert '"bob" hasn\'t joined' in result.stderr


def test_join_refuses_reserved_and_invalid_names(repo: CollabRepo) -> None:
    assert repo.run("join", "--as", "user", "--harness", "x").returncode == 1
    assert repo.run("join", "--as", "Alice", "--harness", "x").returncode == 1
    assert repo.run("join", "--as", "alice", "--harness", "Claude Code").returncode == 1


def test_send_refuses_unknown_recipient_and_empty_body(repo: CollabRepo) -> None:
    repo.join("alice")

    unknown = repo.run("send", "--as", "alice", "--to", "carol", stdin="hi")
    empty = repo.run("send", "--as", "alice", "--to", "*", stdin="  \n")

    assert unknown.returncode == 1
    assert "never joined" in unknown.stderr
    assert empty.returncode == 1
    assert "empty" in empty.stderr


def test_rate_limit_refuses_eleventh_send_but_not_user(repo: CollabRepo) -> None:
    repo.join("alice")
    for index in range(10):
        repo.send("alice", "*", f"message {index}")

    refused = repo.run("send", "--as", "alice", "--to", "*", stdin="one too many")
    for index in range(11):
        repo.send("user", "*", f"user message {index}")

    assert refused.returncode == 1
    assert "Check with the user" in refused.stderr


def test_rate_limit_counts_recent_sends_published_before_an_older_one(
    repo: CollabRepo,
) -> None:
    repo.join("alice")
    for _ in range(10):
        _publish_raw_message(repo, "alice", datetime.now(UTC))
    _publish_raw_message(repo, "alice", datetime.now(UTC) - timedelta(minutes=5))

    result = repo.run("send", "--as", "alice", "--to", "*", stdin="another")

    assert result.returncode == 1
    assert "sent 10 messages" in result.stderr


def test_rate_limit_ignores_expired_sends(repo: CollabRepo) -> None:
    repo.join("alice")
    for _ in range(10):
        _publish_raw_message(repo, "alice", datetime.now(UTC) - timedelta(minutes=2))

    assert "Sent #12" in repo.send("alice", "*", "fine again")


def test_inbox_that_cannot_print_leaves_messages_unread(repo: CollabRepo) -> None:
    repo.join("alice")
    repo.join("bob")
    repo.inbox("bob")
    repo.send("alice", "bob", "must not be lost")
    read_end, write_end = os.pipe()
    os.close(read_end)

    result = subprocess.run(
        [sys.executable, str(repo.script), "inbox", "--as", "bob"],
        cwd=repo.root / "work",
        stdout=write_end,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    os.close(write_end)

    assert result.returncode != 0
    assert "must not be lost" in repo.inbox("bob")


def test_log_follow_prints_history_then_new_messages_once(repo: CollabRepo) -> None:
    repo.join("alice")
    follower = repo.start("log", "--follow")
    try:
        follower.read_until("alice (stratacode) joined")
        repo.send("user", "*", "later message")
        output = follower.read_until("later message")
    finally:
        follower.stop()

    assert output.count("joined") == 1


def test_outside_git_the_current_directory_is_the_root(tmp_path: Path) -> None:
    workdir = tmp_path / "plain"
    workdir.mkdir()

    result = subprocess.run(
        [sys.executable, str(COLLAB_SCRIPT), "join", "--as", "alice", "--harness", "x"],
        cwd=workdir,
        env={**os.environ, "GIT_CEILING_DIRECTORIES": str(tmp_path)},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert (workdir / ".agent-collab" / ".gitignore").exists()


def test_user_messages_are_framed_as_from_the_user(repo: CollabRepo) -> None:
    repo.join("alice")

    repo.send("user", "*", "please pair on this")

    assert "From the user, to everyone:\nplease pair on this" in repo.inbox("alice")


def test_inbox_last_prints_history_before_unread(repo: CollabRepo) -> None:
    repo.join("alice")
    repo.join("bob")
    for index in range(3):
        repo.send("alice", "bob", f"old {index}")
    repo.inbox("bob")
    repo.send("alice", "bob", "fresh")

    output = repo.inbox("bob", "--last", "2")

    history, unread = output.split("1 new message for bob")
    assert "old 0" not in history
    assert "old 1" in history
    assert "old 2" in history
    assert "fresh" in unread


def test_log_prints_every_message(repo: CollabRepo) -> None:
    repo.join("alice")
    repo.join("bob")
    repo.send("alice", "bob", "private to bob")

    output = repo.ok("log")

    assert "#1" in output
    assert "alice (stratacode) → bob\nprivate to bob" in output


def test_who_and_log_need_a_started_collaboration(repo: CollabRepo) -> None:
    result = repo.run("who")

    assert result.returncode == 1
    assert "No agent collaboration" in result.stderr


def test_join_records_the_protocol_version(repo: CollabRepo) -> None:
    repo.join("alice")

    assert (repo.folder / "VERSION").read_text() == "1\n"


def test_unversioned_folder_counts_as_version_1(repo: CollabRepo) -> None:
    repo.join("alice")
    (repo.folder / "VERSION").unlink()

    repo.send("alice", "*", "still works")
    repo.join("bob")

    assert (repo.folder / "VERSION").read_text() == "1\n"


def test_every_command_refuses_a_different_protocol_version(repo: CollabRepo) -> None:
    repo.join("alice")
    (repo.folder / "VERSION").write_text("2\n")

    for args in (
        ("who",),
        ("inbox", "--as", "alice"),
        ("join", "--as", "bob", "--harness", "x"),
    ):
        result = repo.run(*args)
        assert result.returncode == 1
        assert "uses protocol version 2" in result.stderr
        assert str(COLLAB_SCRIPT) in result.stderr
    assert not (repo.folder / "agents" / "bob.json").exists()


def test_printed_commands_use_running_interpreter_and_resolved_script(
    tmp_path: Path,
) -> None:
    real_dir = tmp_path / "skills dir" / "agent-collab"
    real_dir.mkdir(parents=True)
    real_script = real_dir / "collab.py"
    shutil.copy(COLLAB_SCRIPT, real_script)
    linked_dir = tmp_path / "linked"
    linked_dir.symlink_to(real_dir)
    repo = CollabRepo.create(tmp_path)
    repo.script = linked_dir / "collab.py"

    output = repo.join("alice", harness="claude-code")

    watch_line = next(
        line for line in output.splitlines() if " watch --as alice" in line
    )
    assert shlex.split(watch_line) == [
        sys.executable,
        str(real_script.resolve()),
        "watch",
        "--as",
        "alice",
        "--max-seconds",
        "1740",
    ]
    repo.join("bob")
    repo.send("bob", "alice", "hello")
    reply_line = next(
        line for line in repo.inbox("alice").splitlines() if " send --as alice" in line
    )
    assert shlex.split(reply_line)[:2] == [sys.executable, str(real_script.resolve())]
    assert reply_line.endswith("--to bob <<'EOF'")
