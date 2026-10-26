"""Fixtures for the agent-collab skill's collab.py tests."""

from __future__ import annotations

from collections.abc import Callable, Generator
from pathlib import Path

import pytest

from tests.agent_collab.collab_helpers import CollabRepo, Watcher


@pytest.fixture
def repo(tmp_path: Path) -> CollabRepo:
    """A temp git repo to collaborate in."""
    return CollabRepo.create(tmp_path)


@pytest.fixture
def start_watch(repo: CollabRepo) -> Generator[Callable[..., Watcher], None, None]:
    """Start watchers in the repo, killing any still running at teardown."""
    started: list[Watcher] = []

    def start(name: str, *extra: str) -> Watcher:
        """Start a watcher and remember it for teardown."""
        watcher = repo.start_watch(name, *extra)
        started.append(watcher)
        return watcher

    yield start
    for watcher in started:
        watcher.stop()
