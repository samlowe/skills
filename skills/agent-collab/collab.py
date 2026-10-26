"""Message folder CLI that lets coding agents in different harnesses talk to each other."""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import secrets
import shlex
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import FrameType

_FOLDER_NAME = ".agent-collab"
_PROTOCOL_VERSION = 1
_UNVERSIONED_FOLDER_VERSION = 1
_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9-]{0,31}$")
_MESSAGE_FILE_PATTERN = re.compile(r"^(\d{8})\.md$")
_USER = "user"
_USER_HARNESS = "terminal"
_EVERYONE = "*"
_TAG = "[agent-collab]"
_RULE = "──"
_HISTORY_HEADING = f"{_TAG} Recent history (already read):"
_HISTORY_COUNT = 20
_POLL_SECONDS = 1.0
_BEAT_SECONDS = 5.0
_STALE_SECONDS = 15.0
_RATE_LIMIT_COUNT = 10
_RATE_LIMIT_WINDOW = timedelta(seconds=60)
_CLAUDE_CODE_HARNESS = "claude-code"
_CLAUDE_CODE_MAX_SECONDS = 1740
_CODEX_HARNESS = "codex"
_CODEX_THREAD_ENV = "CODEX_THREAD_ID"
_CODEX_QUEUE_TIMEOUT_SECONDS = 60
_WAKE_RETRY_MIN_SECONDS = 5.0
_WAKE_RETRY_MAX_SECONDS = 120.0

AnnouncementKind = Literal["joined", "left"]
WakeMode = Literal["codex"]


class CollabError(Exception):
    """A command can't go ahead; the message says why and what to do instead."""


class _WatchStopped(Exception):
    """Raised by the signal handler so the watcher exits through its cleanup."""


def _now() -> datetime:
    """Return the current time in UTC."""
    return datetime.now(UTC)


def _format_timestamp(moment: datetime) -> str:
    """Format a UTC time as ISO 8601 with milliseconds and a Z suffix."""
    return moment.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _write_atomically(path: Path, text: str) -> None:
    """Write a file through a temp file and os.replace, so readers never see half of it."""
    temp_path = path.with_name(f".tmp-{path.name}-{secrets.token_hex(4)}")
    temp_path.write_text(text, encoding="utf-8")
    os.replace(temp_path, path)


def _write_out(text: str) -> None:
    """Write text to stdout in one write and flush, so a piped watcher wakes its agent."""
    sys.stdout.write(text)
    sys.stdout.flush()


def _validate_name(name: str, *, what: str = "Name") -> None:
    """Raise CollabError unless the name matches the allowed pattern (section 5.3).

    Args:
        name: The name to check.
        what: What the name is, for the error message.

    Raises:
        CollabError: If the name isn't allowed.
    """
    if not _NAME_PATTERN.match(name):
        raise CollabError(
            f"{what} {name!r} isn't valid: use lowercase letters, digits and "
            "hyphens, starting with a letter, at most 32 characters.",
        )


def _parse_kind(value: str | None) -> AnnouncementKind | None:
    """Narrow a header's kind value to an announcement kind."""
    match value:
        case "joined" | "left":
            return value
        case _:
            return None


@dataclass(frozen=True)
class Message:
    """One message file: a small key: value header and a markdown body (section 5.2)."""

    number: int
    ts: str
    sender: str
    harness: str
    to: str
    body: str
    kind: AnnouncementKind | None = None

    @classmethod
    def create(
        cls,
        sender: str,
        harness: str,
        to: str,
        body: str,
        *,
        kind: AnnouncementKind | None = None,
    ) -> Message:
        """Build a new, unnumbered message stamped with the current time."""
        return cls(
            number=0,
            ts=_format_timestamp(_now()),
            sender=sender,
            harness=harness,
            to=to,
            body=body,
            kind=kind,
        )

    @classmethod
    def from_text(cls, number: int, text: str) -> Message:
        """Parse a message file's text.

        Args:
            number: The message's number, taken from its filename.
            text: The whole file.

        Returns:
            The parsed message.

        Raises:
            CollabError: If the header is missing or incomplete.
        """
        lines = text.split("\n")
        if lines[0] != "---" or "---" not in lines[1:]:
            raise CollabError(f"Message #{number} has no complete header.")

        header_end = lines.index("---", 1)
        header = dict(
            line.split(": ", 1) for line in lines[1:header_end] if ": " in line
        )

        try:
            return cls(
                number=number,
                ts=header["ts"],
                sender=header["from"],
                harness=header["harness"],
                to=header["to"],
                body="\n".join(lines[header_end + 1 :]).strip("\n"),
                kind=_parse_kind(header.get("kind")),
            )
        except KeyError as error:
            raise CollabError(
                f"Message #{number} is missing {error.args[0]!r}.",
            ) from error

    def to_text(self) -> str:
        """Render the message file's text; the number lives only in the filename."""
        header = [
            f"ts: {self.ts}",
            f"from: {self.sender}",
            f"harness: {self.harness}",
            f"to: {self.to}",
        ]
        if self.kind:
            header.append(f"kind: {self.kind}")
        return "---\n" + "\n".join(header) + "\n---\n" + self.body + "\n"

    @property
    def sent_at(self) -> datetime:
        """The message's timestamp as a datetime."""
        return datetime.fromisoformat(self.ts)

    def is_for(self, name: str) -> bool:
        """Whether the message goes to the named agent, ignoring cursors (section 6.1)."""
        return self.sender != name and self.to in (name, _EVERYONE)

    def render_delivered(self) -> str:
        """Render the message as its recipient sees it, with the framing line (section 6.2)."""
        if self.kind:
            return (
                f"{_RULE} #{self.number} · {self.sender} ({self.harness}) "
                f"{self.kind} · no reply needed"
            )

        audience = ", to everyone" if self.to == _EVERYONE else ""

        if self.sender == _USER:
            framing = f"From the user{audience}:"
        else:
            framing = (
                f"This is {self.sender} ({self.harness}), on behalf of the user"
                f"{audience}:"
            )

        return f"{_RULE} #{self.number} · {framing}\n{self.body}\n{_RULE}"

    def render_history(self) -> str:
        """Render the message as a plain log entry, for history and the human's log."""
        origin = f"{_RULE} #{self.number} · {self.ts} · {self.sender} ({self.harness})"
        if self.kind:
            return f"{origin} {self.kind}"
        return f"{origin} → {self.to}\n{self.body}"


@dataclass(frozen=True)
class Presence:
    """An agent's presence file: who it is and when it joined."""

    name: str
    harness: str
    joined_at: str

    @classmethod
    def from_json(cls, text: str) -> Presence:
        """Parse a presence file's JSON."""
        data = json.loads(text)
        return cls(
            name=data["name"],
            harness=data["harness"],
            joined_at=data["joined_at"],
        )

    def to_json(self) -> str:
        """Render the presence file's JSON."""
        data = {"name": self.name, "harness": self.harness, "joined_at": self.joined_at}
        return json.dumps(data, indent=2) + "\n"


@dataclass(frozen=True)
class Heartbeat:
    """A watcher's heartbeat file: the watcher's id, touched every few seconds (section 6.4)."""

    path: Path

    def is_live(self) -> bool:
        """Whether a watcher has beaten recently enough to count as running."""
        try:
            modified = self.path.stat().st_mtime
        except FileNotFoundError:
            return False
        return time.time() - modified < _STALE_SECONDS

    def owner(self) -> str | None:
        """Return the id of the watcher that holds the file, or None if there's no file."""
        try:
            return self.path.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            return None

    def claim(self, watcher_id: str) -> None:
        """Write a watcher's id, taking the name over from any earlier watcher."""
        _write_atomically(self.path, f"{watcher_id}\n")

    def beat(self, watcher_id: str) -> bool:
        """Touch the file if the watcher still holds it, and return whether it does."""
        if self.owner() != watcher_id:
            return False
        try:
            os.utime(self.path)
        except FileNotFoundError:
            return False
        return True

    def release(self, watcher_id: str) -> None:
        """Delete the file if the watcher still holds it."""
        if self.owner() == watcher_id:
            self.path.unlink(missing_ok=True)


@dataclass(frozen=True)
class Commands:
    """Builds the exact commands printed for the agent to copy (D11)."""

    prefix: str

    @classmethod
    def for_this_script(cls) -> Commands:
        """Use the running interpreter and this script's resolved path, both shell-quoted."""
        script_path = str(Path(__file__).resolve())
        return cls(prefix=f"{shlex.quote(sys.executable)} {shlex.quote(script_path)}")

    def join(self, name: str) -> str:
        """The command that joins under a name."""
        return f"{self.prefix} join --as {name} --harness <harness>"

    def watch(self, name: str, harness: str, *, max_seconds: int | None = None) -> str:
        """The command that starts a watcher for the agent's harness.

        Claude Code's watcher stays under its Monitor limit (section 8). Codex
        can't be woken by a watcher's output, so its watcher wakes it through
        codex queue instead.

        Args:
            name: The agent's name.
            harness: The agent's harness.
            max_seconds: How long the watcher runs, or None for the harness default.

        Returns:
            The command line to copy.
        """
        if max_seconds is None and harness == _CLAUDE_CODE_HARNESS:
            max_seconds = _CLAUDE_CODE_MAX_SECONDS
        limit = "" if max_seconds is None else f" --max-seconds {max_seconds}"
        wake = f" --wake {_CODEX_HARNESS}" if harness == _CODEX_HARNESS else ""
        return f"{self.prefix} watch --as {name}{limit}{wake}"

    def inbox(self, name: str) -> str:
        """The command that prints an agent's unread messages."""
        return f"{self.prefix} inbox --as {name}"

    def send(self, name: str, recipient: str) -> str:
        """The heredoc command that sends a message."""
        recipient_arg = shlex.quote(recipient)
        return f"{self.prefix} send --as {name} --to {recipient_arg} <<'EOF'\n...\nEOF"


class Folder:
    """The .agent-collab message folder and every read and write on it (section 5)."""

    def __init__(self, root: Path) -> None:
        """Point at the message folder inside a repo root, without creating it."""
        self.root = root
        self.path = root / _FOLDER_NAME
        self.messages_dir = self.path / "messages"
        self.agents_dir = self.path / "agents"
        self.cursors_dir = self.path / "cursors"
        self.version_path = self.path / "VERSION"

    @classmethod
    def discover(cls) -> Folder:
        """Find the repo root with git, falling back to the current directory."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError:
            return cls(Path.cwd())

        return (
            cls(Path(result.stdout.strip()))
            if result.returncode == 0
            else cls(Path.cwd())
        )

    def ensure(self) -> None:
        """Create the folder, its subfolders and a .gitignore of * (D2)."""
        for directory in (self.messages_dir, self.agents_dir, self.cursors_dir):
            directory.mkdir(parents=True, exist_ok=True)

        gitignore = self.path / ".gitignore"
        if not gitignore.exists():
            _write_atomically(gitignore, "*\n")

        if not self.version_path.exists():
            _write_atomically(self.version_path, f"{_PROTOCOL_VERSION}\n")

    def check_version(self) -> None:
        """Refuse a folder written by a collab.py with a different protocol version.

        Two installs of the skill (say a project copy and a home copy) can meet in
        one folder. A folder that has no VERSION file yet was made before the file
        existed, by protocol version 1.

        Raises:
            CollabError: If the folder's version differs from this script's, or
                its VERSION file can't be read as a number.
        """
        if not self.path.is_dir():
            return

        try:
            found = int(self.version_path.read_text().strip())
        except FileNotFoundError:
            found = _UNVERSIONED_FOLDER_VERSION
        except ValueError as error:
            raise CollabError(
                f"{self.version_path} doesn't hold a version number."
            ) from error

        if found != _PROTOCOL_VERSION:
            raise CollabError(
                f"The collaboration in {self.root} uses protocol version {found}, but "
                f"{Path(__file__).resolve()} uses version {_PROTOCOL_VERSION}. Every agent "
                "must use the same version of the agent-collab skill: update the older copy.",
            )

    def require(self) -> None:
        """Raise CollabError if no collaboration has been started here."""
        if not self.messages_dir.is_dir():
            raise CollabError(
                f"No agent collaboration in {self.root} yet. An agent starts one with join.",
            )

    def message_numbers(self) -> list[int]:
        """Return every message number in order, ignoring temp files."""
        numbers = [
            int(match.group(1))
            for entry in os.listdir(self.messages_dir)
            if (match := _MESSAGE_FILE_PATTERN.match(entry))
        ]
        return sorted(numbers)

    def latest_number(self) -> int:
        """Return the highest message number, or 0 when there are none."""
        numbers = self.message_numbers()
        return numbers[-1] if numbers else 0

    def read_message(self, number: int) -> Message:
        """Read one message by number."""
        path = self.messages_dir / f"{number:08d}.md"
        return Message.from_text(number, path.read_text(encoding="utf-8"))

    def messages_after(self, number: int) -> list[Message]:
        """Return every message numbered above the given one, in order."""
        numbers = [each for each in self.message_numbers() if each > number]
        return [self.read_message(each) for each in numbers]

    def recent_messages(self, count: int, *, up_to: int) -> list[Message]:
        """Return the last count messages numbered at or below up_to, in order."""
        if count <= 0:
            return []
        numbers = [each for each in self.message_numbers() if each <= up_to]
        return [self.read_message(each) for each in numbers[-count:]]

    def append(self, message: Message) -> int:
        """Publish a message under the next free number and return that number (section 5.1).

        The file is written in full under a temp name, then hard-linked to its
        number. os.link fails if the number is taken, so a number only appears
        once its file is complete and every lower number already exists.

        Args:
            message: The message to publish; its number is ignored.

        Returns:
            The number the message was published under.
        """
        temp_path = self.messages_dir / f".tmp-{secrets.token_hex(8)}"
        temp_path.write_text(message.to_text(), encoding="utf-8")

        try:
            number = self.latest_number() + 1
            while True:
                try:
                    os.link(temp_path, self.messages_dir / f"{number:08d}.md")
                    return number
                except FileExistsError:
                    number += 1
        finally:
            temp_path.unlink()

    def count_recent_sends(self, sender: str, *, since: datetime) -> int:
        """Count the sender's messages, not announcements, sent since the given time.

        Every message is checked, because concurrent senders can publish in a
        different order from their timestamps.
        """
        messages = (self.read_message(number) for number in self.message_numbers())
        return sum(
            1
            for message in messages
            if message.sender == sender
            and message.kind is None
            and message.sent_at >= since
        )

    def read_presence(self, name: str) -> Presence | None:
        """Return an agent's presence, or None if it hasn't joined."""
        try:
            text = self._presence_path(name).read_text(encoding="utf-8")
        except FileNotFoundError:
            return None

        return Presence.from_json(text)

    def write_presence(self, presence: Presence) -> None:
        """Write an agent's presence file."""
        _write_atomically(self._presence_path(presence.name), presence.to_json())

    def remove_presence(self, name: str) -> None:
        """Remove an agent's presence file, if it's there."""
        self._presence_path(name).unlink(missing_ok=True)

    def present_agents(self) -> list[Presence]:
        """Return every joined agent, sorted by name."""
        names = sorted(entry.stem for entry in self.agents_dir.glob("*.json"))
        return [presence for name in names if (presence := self.read_presence(name))]

    def read_cursor(self, name: str) -> int | None:
        """Return an agent's cursor, or None if the name has never joined."""
        try:
            return int(self._cursor_path(name).read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None

    def write_cursor(self, name: str, number: int) -> None:
        """Set an agent's cursor, even backwards; only join uses this, for a new name."""
        _write_atomically(self._cursor_path(name), f"{number}\n")

    def advance_cursor(self, name: str, number: int) -> None:
        """Move an agent's cursor forward to number, if it's behind.

        There's no locking, so two overlapping updates can still leave the lower
        value; the worst outcome is some messages shown again (section 5.4).
        """
        if number > (self.read_cursor(name) or 0):
            self.write_cursor(name, number)

    def heartbeat(self, name: str) -> Heartbeat:
        """Return the heartbeat file for an agent's watcher."""
        return Heartbeat(self.agents_dir / f"{name}.alive")

    def _presence_path(self, name: str) -> Path:
        """Return the path of an agent's presence file."""
        return self.agents_dir / f"{name}.json"

    def _cursor_path(self, name: str) -> Path:
        """Return the path of an agent's cursor file."""
        return self.cursors_dir / name


@dataclass(frozen=True)
class Delivery:
    """An agent's unread messages, and how far the scan that found them reached."""

    messages: list[Message]
    scanned_up_to: int


class Session:
    """One agent's view of the collaboration: delivery, history and the self-check."""

    def __init__(self, folder: Folder, name: str, commands: Commands) -> None:
        """Bind an agent name to the folder and the commands to print."""
        self.folder = folder
        self.name = name
        self.commands = commands

    def require_joined(self) -> Presence:
        """Return the agent's presence, or raise CollabError if it hasn't joined."""
        self.folder.require()
        presence = self.folder.read_presence(self.name)
        if presence is None:
            raise CollabError(
                f'"{self.name}" hasn\'t joined. Run: {self.commands.join(self.name)}',
            )
        return presence

    def scan_unread(self) -> Delivery:
        """Find the agent's unread messages without moving its cursor.

        Call mark_delivered once the messages have been printed, so a failed or
        interrupted write leaves them unread rather than skipping them (section 6.1).

        Returns:
            The messages for the agent, and the highest number scanned, which
            includes messages that weren't for it.
        """
        cursor = self.folder.read_cursor(self.name) or 0
        scanned = self.folder.messages_after(cursor)
        return Delivery(
            messages=[message for message in scanned if message.is_for(self.name)],
            scanned_up_to=scanned[-1].number if scanned else cursor,
        )

    def mark_delivered(self, delivery: Delivery) -> None:
        """Move the agent's cursor past a delivery that has been printed."""
        self.folder.advance_cursor(self.name, delivery.scanned_up_to)

    def render_history(self, count: int) -> str:
        """Render the last count messages the agent's cursor has passed, or nothing."""
        cursor = self.folder.read_cursor(self.name) or 0
        if not (messages := self.folder.recent_messages(count, up_to=cursor)):
            return ""
        entries = "\n".join(message.render_history() for message in messages)
        return f"{_HISTORY_HEADING}\n{entries}\n"

    def render_batch(self, messages: list[Message]) -> str:
        """Render delivered messages with a heading and the self-explaining footer (D4)."""
        noun = "message" if len(messages) == 1 else "messages"
        lines = [f"{_TAG} {len(messages)} new {noun} for {self.name}"]
        lines += [message.render_delivered() for message in messages]
        lines += [
            f'{_TAG} You are "{self.name}" in an agent collaboration on this repo '
            "(rules: the agent-collab skill). Reply with:",
            self.commands.send(self.name, _reply_recipient(messages)),
        ]
        return "\n".join(lines) + "\n"

    def render_watcher_warning(self, harness: str) -> str:
        """Render the self-check warning if the agent's watcher isn't running, or nothing (D12)."""
        if self.folder.heartbeat(self.name).is_live():
            return ""
        return (
            f"{_TAG} Your watcher isn't running, so you won't be woken. "
            f"Restart it with: {self.commands.watch(self.name, harness)}\n"
        )


def _reply_recipient(messages: list[Message]) -> str:
    """Pick who a reply goes to: the last agent who wrote, or the user if only they did."""
    for message in reversed(messages):
        if message.sender != _USER:
            return message.sender
    return _USER


def _render_who(folder: Folder) -> str:
    """Render who is present and whether each one's watcher is running."""
    if not (agents := folder.present_agents()):
        return f"{_TAG} Nobody has joined.\n"

    lines = [f"{_TAG} Present:"]
    for presence in agents:
        live = folder.heartbeat(presence.name).is_live()
        watcher = "watcher running" if live else "watcher not running"
        lines.append(
            f"  {presence.name} ({presence.harness}), joined {presence.joined_at}, {watcher}",
        )

    return "\n".join(lines) + "\n"


def cmd_join(folder: Folder, commands: Commands, name: str, harness: str) -> None:
    """Join, announce it, and print presence, history, unread messages and the next step.

    A new name's cursor starts at the latest message. A name that joined before
    keeps its cursor, so a rejoining agent gets what it missed.

    Args:
        folder: The message folder.
        commands: The command builder for printed commands.
        name: The agent's name.
        harness: The agent's harness, e.g. claude-code or stratacode.

    Raises:
        CollabError: If the name is invalid, reserved, or has a running watcher.
    """
    _validate_name(name)
    _validate_name(harness, what="Harness")
    if name == _USER:
        raise CollabError(f'"{_USER}" is reserved for the human. Pick another name.')

    folder.ensure()
    if folder.heartbeat(name).is_live():
        raise CollabError(
            f'"{name}" already has a running watcher, so another session is using '
            "that name. Pick another name, or stop that session's watcher first.",
        )

    if folder.read_cursor(name) is None:
        folder.write_cursor(name, folder.latest_number())

    presence = Presence(name=name, harness=harness, joined_at=_format_timestamp(_now()))
    folder.write_presence(presence)
    folder.append(Message.create(name, harness, _EVERYONE, "", kind="joined"))

    session = Session(folder, name, commands)
    output = f'{_TAG} Joined as "{name}" ({harness}) in {folder.root}\n'
    output += _render_who(folder)
    output += session.render_history(_HISTORY_COUNT)

    delivery = session.scan_unread()
    if delivery.messages:
        output += session.render_batch(delivery.messages)

    output += (
        f"{_TAG} Next, start your watcher in the background (the agent-collab skill "
        f"says how):\n{commands.watch(name, harness)}\n"
        f"{_TAG} Every command starts with this prefix, which the user can approve "
        f"once: {commands.prefix}\n"
    )
    _write_out(output)
    session.mark_delivered(delivery)


def cmd_leave(folder: Folder, commands: Commands, name: str) -> None:
    """Announce that the agent has left and remove its presence; its watcher then exits."""
    presence = Session(folder, name, commands).require_joined()
    folder.append(Message.create(name, presence.harness, _EVERYONE, "", kind="left"))
    folder.remove_presence(name)
    _write_out(
        f"{_TAG} You have left the collaboration. Your watcher stops by itself.\n"
    )


def cmd_send(
    folder: Folder,
    commands: Commands,
    name: str,
    recipient: str,
    body: str,
) -> None:
    """Send a message, after the rate limit, and print the caller's self-check.

    Args:
        folder: The message folder.
        commands: The command builder for printed commands.
        name: The sender, or user for the human.
        recipient: An agent that has joined at some point, user, or * for everyone.
        body: The message text.

    Raises:
        CollabError: If the sender hasn't joined, the recipient is unknown, the
            body is empty, or the rate limit is hit.
    """
    session = Session(folder, name, commands)
    if name == _USER:
        folder.require()
        harness = _USER_HARNESS
        warning = ""
    else:
        harness = session.require_joined().harness
        warning = session.render_watcher_warning(harness)
        _check_rate_limit(folder, name)

    _validate_recipient(folder, recipient)

    text = body.strip()
    if not text:
        raise CollabError("Not sent: the message is empty. Pass the body on stdin.")

    number = folder.append(Message.create(name, harness, recipient, text))
    _write_out(f"{warning}{_TAG} Sent #{number} to {recipient}.\n")


def _check_rate_limit(folder: Folder, name: str) -> None:
    """Refuse a send once the agent has sent too many messages recently (section 6.5)."""
    sent = folder.count_recent_sends(name, since=_now() - _RATE_LIMIT_WINDOW)
    if sent >= _RATE_LIMIT_COUNT:
        window = int(_RATE_LIMIT_WINDOW.total_seconds())
        raise CollabError(
            f"Not sent: you've sent {sent} messages in the last {window} seconds. "
            "You and your peer may be replying to each other in a loop. Check with "
            "the user before sending more.",
        )


def _validate_recipient(folder: Folder, recipient: str) -> None:
    """Refuse a recipient that isn't everyone, the user, or a name that has joined."""
    if recipient in (_EVERYONE, _USER):
        return

    _validate_name(recipient, what="Recipient")
    if folder.read_cursor(recipient) is None:
        present = ", ".join(each.name for each in folder.present_agents()) or "nobody"
        raise CollabError(
            f'Not sent: "{recipient}" has never joined (present: {present}). '
            f"Use a present agent's name or '{_EVERYONE}'.",
        )


def cmd_inbox(folder: Folder, commands: Commands, name: str, last: int) -> None:
    """Print the self-check, optional history and unread messages, moving the cursor."""
    session = Session(folder, name, commands)
    presence = session.require_joined()
    output = session.render_watcher_warning(presence.harness)
    output += session.render_history(last)

    delivery = session.scan_unread()
    if delivery.messages:
        output += session.render_batch(delivery.messages)
    else:
        output += f"{_TAG} No new messages for {name}.\n"

    _write_out(output)
    session.mark_delivered(delivery)


def cmd_watch(
    folder: Folder,
    commands: Commands,
    name: str,
    max_seconds: int | None,
    wake: WakeMode | None,
) -> None:
    """Deliver each batch of unread messages as it arrives, beating the heartbeat.

    By default each batch is printed, for a harness that wakes on output. With
    wake set to codex, it wakes the Codex session instead (see CodexWaker).

    Exits after leave, after max_seconds with a re-arm footer, or on SIGTERM or
    SIGINT. Whichever way it exits, it deletes the heartbeat if it still holds it.

    Args:
        folder: The message folder.
        commands: The command builder for printed commands.
        name: The agent whose messages to watch.
        max_seconds: Exit cleanly after this long, or None to run until stopped.
        wake: How to wake the agent, or None to print batches.

    Raises:
        CollabError: If the agent hasn't joined, or wake is codex outside a
            Codex session.
    """
    session = Session(folder, name, commands)
    presence = session.require_joined()
    deliver = (
        CodexWaker.for_this_session(session).deliver
        if wake == _CODEX_HARNESS
        else lambda: _print_unread(session)
    )
    heartbeat = folder.heartbeat(name)
    watcher_id = secrets.token_hex(8)

    try:
        signal.signal(signal.SIGTERM, _raise_watch_stopped)
        signal.signal(signal.SIGINT, _raise_watch_stopped)
        heartbeat.claim(watcher_id)
        _watch_until_done(
            session,
            presence.harness,
            heartbeat,
            watcher_id,
            max_seconds,
            deliver,
        )
    except _WatchStopped:
        pass
    finally:
        heartbeat.release(watcher_id)


def _print_unread(session: Session) -> None:
    """Print the agent's unread messages, if any, and move its cursor past them."""
    delivery = session.scan_unread()
    if delivery.messages:
        _write_out(session.render_batch(delivery.messages))
    session.mark_delivered(delivery)


class CodexWaker:
    """Wakes a Codex session through codex queue when messages arrive.

    Codex doesn't wake on a background command's output, but codex queue gives
    a session a message that starts a turn as soon as it's idle. The queued
    message only points at inbox, and the cursor isn't moved, so inbox still
    delivers the messages themselves. A failed codex queue is retried with
    backoff; a successful one isn't repeated for the same messages.
    """

    def __init__(self, session: Session, thread_id: str) -> None:
        """Wake the given Codex thread about messages after the agent's current cursor."""
        self.session = session
        self.thread_id = thread_id
        self.notified_up_to = session.folder.read_cursor(session.name) or 0
        self.retry_delay = 0.0
        self.next_attempt = 0.0

    @classmethod
    def for_this_session(cls, session: Session) -> CodexWaker:
        """Wake the Codex session this watcher was started from.

        Raises:
            CollabError: If the watcher wasn't started from a Codex session.
        """
        thread_id = os.environ.get(_CODEX_THREAD_ENV)
        if not thread_id:
            raise CollabError(
                f"--wake {_CODEX_HARNESS} needs {_CODEX_THREAD_ENV}, which Codex sets "
                "for commands it runs. Start the watcher from the Codex session.",
            )
        return cls(session, thread_id)

    def deliver(self) -> None:
        """Queue one wake-up for messages not yet notified, when a retry is due."""
        fresh = [
            message
            for message in self.session.scan_unread().messages
            if message.number > self.notified_up_to and message.kind is None
        ]
        if not fresh or time.monotonic() < self.next_attempt:
            return

        if self._queue(self._wake_text(fresh)):
            self.notified_up_to = fresh[-1].number
            self.retry_delay = 0.0
        else:
            self.retry_delay = min(
                max(self.retry_delay * 2, _WAKE_RETRY_MIN_SECONDS),
                _WAKE_RETRY_MAX_SECONDS,
            )
            _write_out(f"{_TAG} Retrying in {self.retry_delay:.0f}s.\n")
        self.next_attempt = time.monotonic() + self.retry_delay

    def _wake_text(self, messages: list[Message]) -> str:
        """Build the queued message: who wrote, and the inbox command that reads them."""
        name = self.session.name
        senders = ", ".join(sorted({message.sender for message in messages}))
        noun = "message" if len(messages) == 1 else "messages"
        return (
            f"{_TAG} {len(messages)} new {noun} for {name} from {senders}. This is "
            "an automatic wake-up from your agent-collab watcher, not a message from "
            f"the user. Read and handle them with:\n{self.session.commands.inbox(name)}"
        )

    def _queue(self, text: str) -> bool:
        """Run codex queue for the thread, print the outcome, and return whether it worked."""
        try:
            result = subprocess.run(
                ["codex", "queue", "--thread", self.thread_id, "--message", text],
                capture_output=True,
                text=True,
                timeout=_CODEX_QUEUE_TIMEOUT_SECONDS,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            _write_out(f"{_TAG} codex queue failed: {error}\n")
            return False

        output = (result.stdout + result.stderr).strip()
        if result.returncode != 0:
            _write_out(f"{_TAG} codex queue exited {result.returncode}: {output}\n")
            return False
        _write_out(f"{_TAG} Woke Codex: {output}\n")
        return True


def _watch_until_done(
    session: Session,
    harness: str,
    heartbeat: Heartbeat,
    watcher_id: str,
    max_seconds: int | None,
    deliver: Callable[[], None],
) -> None:
    """Poll for messages until leave or max_seconds, beating while the watcher holds the name."""
    started = last_beat = time.monotonic()
    holds_name = True
    while True:
        if session.folder.read_presence(session.name) is None:
            _write_out(
                f"{_TAG} You have left the collaboration. The watcher has stopped.\n"
            )
            return

        deliver()

        now = time.monotonic()
        if holds_name and now - last_beat >= _BEAT_SECONDS:
            holds_name = heartbeat.beat(watcher_id)
            last_beat = now

        if max_seconds is not None and now - started >= max_seconds:
            restart = session.commands.watch(
                session.name,
                harness,
                max_seconds=max_seconds,
            )
            _write_out(
                f"{_TAG} The watcher has exited; start it again with:\n{restart}\n"
            )
            return

        time.sleep(_POLL_SECONDS)


def _raise_watch_stopped(signum: int, frame: FrameType | None) -> None:
    """Turn SIGTERM and SIGINT into a clean watcher exit; Python's default SIGTERM skips finally."""
    raise _WatchStopped


def cmd_who(folder: Folder) -> None:
    """Print who is present and whether each one's watcher is running."""
    folder.require()
    _write_out(_render_who(folder))


def cmd_log(folder: Folder, *, follow: bool) -> None:
    """Print the whole conversation for the human; with follow, keep printing new messages."""
    folder.require()
    printed_up_to = 0
    try:
        while True:
            if new_messages := folder.messages_after(printed_up_to):
                entries = "".join(each.render_history() + "\n" for each in new_messages)
                _write_out(entries)
                printed_up_to = new_messages[-1].number
            if not follow:
                return
            time.sleep(_POLL_SECONDS)
    except KeyboardInterrupt:
        return


def _build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(
        prog="collab.py",
        description="Let coding agents message each other through .agent-collab/.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    join = subparsers.add_parser("join", help="join the collaboration")
    join.add_argument("--as", dest="name", required=True)
    join.add_argument("--harness", required=True, help="e.g. claude-code or stratacode")

    leave = subparsers.add_parser("leave", help="leave the collaboration")
    leave.add_argument("--as", dest="name", required=True)

    send = subparsers.add_parser(
        "send",
        help="send a message; the body comes from stdin",
    )
    send.add_argument("--as", dest="name", required=True)
    send.add_argument("--to", dest="recipient", required=True, help="a name, or '*'")

    watch = subparsers.add_parser("watch", help="print new messages as they arrive")
    watch.add_argument("--as", dest="name", required=True)
    watch.add_argument("--max-seconds", type=int, default=None)
    watch.add_argument(
        "--wake",
        choices=[_CODEX_HARNESS],
        default=None,
        help="wake the agent this way instead of printing messages",
    )

    inbox = subparsers.add_parser("inbox", help="print unread messages without waiting")
    inbox.add_argument("--as", dest="name", required=True)
    inbox.add_argument(
        "--last",
        type=int,
        default=0,
        help="first print K messages of history",
    )

    subparsers.add_parser("who", help="list joined agents")

    log = subparsers.add_parser("log", help="print the whole conversation")
    log.add_argument("--follow", action="store_true")
    return parser


def _read_body() -> str:
    """Read a message body from stdin, prompting a human at a terminal."""
    if sys.stdin.isatty():
        sys.stderr.write("Type your message, then press Ctrl+D on a new line.\n")
    return sys.stdin.read()


def _run(args: argparse.Namespace, folder: Folder, commands: Commands) -> None:
    """Dispatch to the chosen command."""
    match args.command:
        case "join":
            cmd_join(folder, commands, args.name, args.harness)
        case "leave":
            cmd_leave(folder, commands, args.name)
        case "send":
            cmd_send(folder, commands, args.name, args.recipient, _read_body())
        case "watch":
            cmd_watch(folder, commands, args.name, args.max_seconds, args.wake)
        case "inbox":
            cmd_inbox(folder, commands, args.name, args.last)
        case "who":
            cmd_who(folder)
        case "log":
            cmd_log(folder, follow=args.follow)


def main(argv: list[str] | None = None) -> int:
    """Run collab.py and return its exit code.

    Errors go to stderr. A failing watcher also prints a one-line stdout notice,
    because its stdout is what wakes the agent (section 6.2).

    Args:
        argv: Arguments, or None for sys.argv.

    Returns:
        0 on success, 1 on an error.
    """
    args = _build_parser().parse_args(argv)

    try:
        folder = Folder.discover()
        folder.check_version()
        _run(args, folder, Commands.for_this_script())
    except (CollabError, OSError, ValueError) as error:
        sys.stderr.write(f"{_TAG} Error: {error}\n")
        if args.command == "watch":
            with contextlib.suppress(OSError):
                _write_out(f"{_TAG} The watcher failed: {error}\n")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
