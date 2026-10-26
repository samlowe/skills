"""Helpers that run the agent-collab skill's collab.py as a subprocess against a temp repo."""

from __future__ import annotations

import os
import queue
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO

COLLAB_SCRIPT = (
    Path(__file__).resolve().parents[2] / "skills" / "agent-collab" / "collab.py"
)
WATCH_TIMEOUT_SECONDS = 10.0


@dataclass
class CollabRepo:
    """A temp git repo whose commands run from a subfolder, away from the script."""

    root: Path
    script: Path = COLLAB_SCRIPT

    @classmethod
    def create(cls, tmp_path: Path) -> CollabRepo:
        """Initialise a git repo with a work subfolder under tmp_path."""
        root = tmp_path / "repo"
        (root / "work").mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        return cls(root=root.resolve())

    @property
    def folder(self) -> Path:
        """The .agent-collab folder at the repo root."""
        return self.root / ".agent-collab"

    def run(self, *args: str, stdin: str = "") -> subprocess.CompletedProcess[str]:
        """Run a collab.py command from the work subfolder and return its result."""
        return subprocess.run(
            [sys.executable, str(self.script), *args],
            cwd=self.root / "work",
            input=stdin,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )

    def ok(self, *args: str, stdin: str = "") -> str:
        """Run a command that must succeed and return its stdout."""
        result = self.run(*args, stdin=stdin)
        assert result.returncode == 0, result.stderr + result.stdout
        return result.stdout

    def join(self, name: str, *, harness: str = "stratacode") -> str:
        """Join under a name and return the output."""
        return self.ok("join", "--as", name, "--harness", harness)

    def send(self, sender: str, recipient: str, body: str) -> str:
        """Send a message and return the output."""
        return self.ok("send", "--as", sender, "--to", recipient, stdin=body)

    def inbox(self, name: str, *extra: str) -> str:
        """Run inbox and return the output."""
        return self.ok("inbox", "--as", name, *extra)

    def alive_path(self, name: str) -> Path:
        """The heartbeat file for a name."""
        return self.folder / "agents" / f"{name}.alive"

    def message_files(self) -> list[Path]:
        """Every published message file, in order."""
        return sorted((self.folder / "messages").glob("*.md"))

    def start_watch(self, name: str, *extra: str) -> Watcher:
        """Start a watcher with stdout piped, as both harnesses run it."""
        return self.start("watch", "--as", name, *extra)

    def start(self, *args: str) -> Watcher:
        """Start a long-running command with stdout read on a thread."""
        process = subprocess.Popen(
            [sys.executable, str(self.script), *args],
            cwd=self.root / "work",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        watcher = Watcher(process)
        watcher.start_reading()
        return watcher


@dataclass
class Watcher:
    """A long-running collab.py process (watch, or log --follow) whose stdout is read on a thread."""

    process: subprocess.Popen[str]
    lines: queue.Queue[str] = field(default_factory=queue.Queue)
    seen: list[str] = field(default_factory=list)

    def start_reading(self) -> None:
        """Copy stdout lines into the queue as they arrive."""
        stdout = self.process.stdout
        if stdout is None:
            raise RuntimeError("watcher stdout isn't piped")
        threading.Thread(target=self._pump, args=(stdout,), daemon=True).start()

    def _pump(self, stdout: IO[str]) -> None:
        """Read lines until the pipe closes."""
        for line in stdout:
            self.lines.put(line)

    def read_until(self, text: str, *, timeout: float = WATCH_TIMEOUT_SECONDS) -> str:
        """Return everything read so far once a line containing text arrives.

        Raises:
            AssertionError: If the text doesn't arrive within the timeout.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                line = self.lines.get(timeout=0.1)
            except queue.Empty:
                continue
            self.seen.append(line)
            if text in line:
                return "".join(self.seen)
        raise AssertionError(f"{text!r} not seen; got:\n{''.join(self.seen)}")

    def wait_for_exit(self, *, timeout: float = WATCH_TIMEOUT_SECONDS) -> int:
        """Wait for the watcher to exit and return its exit code."""
        return self.process.wait(timeout=timeout)

    def send_signal(self, signum: signal.Signals) -> int:
        """Send a signal and wait for the watcher to exit."""
        self.process.send_signal(signum)
        return self.wait_for_exit()

    def stop(self) -> None:
        """Kill the watcher if it's still running."""
        if self.process.poll() is None:
            self.process.kill()
            self.process.wait()


def wait_for(
    path: Path,
    *,
    exists: bool = True,
    timeout: float = WATCH_TIMEOUT_SECONDS,
) -> None:
    """Wait until a path exists, or no longer exists.

    Raises:
        AssertionError: If that doesn't happen within the timeout.
    """
    state = "never appeared" if exists else "never went away"
    wait_until(lambda: path.exists() == exists, f"{path} {state}", timeout=timeout)


def wait_until(
    condition: Callable[[], bool],
    failure: str,
    *,
    timeout: float = WATCH_TIMEOUT_SECONDS,
) -> None:
    """Poll until the condition holds.

    Raises:
        AssertionError: With the failure message, if it doesn't hold within the timeout.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(0.05)
    raise AssertionError(failure)


def make_stale(path: Path) -> None:
    """Backdate a heartbeat file so it counts as stale."""
    old = time.time() - 60
    os.utime(path, (old, old))
