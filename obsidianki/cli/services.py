"""
Global service instances to eliminate prop drilling.
"""

import os
import shutil

from obsidianki.api.obsidian import ObsidianAPI
from obsidianki.api.obsidian_cli import ObsidianCLIAPI
from obsidianki.ai.client import FlashcardAI
from obsidianki.api.anki import AnkiAPI


def create_obsidian_client():
    """Pick REST API or Obsidian CLI based on ``OBSIDIAN_CLIENT`` and environment."""
    mode = (os.getenv("OBSIDIAN_CLIENT") or "auto").strip().lower()

    if mode == "cli":
        return ObsidianCLIAPI()

    if mode == "rest":
        return ObsidianAPI()

    if os.getenv("OBSIDIAN_API_KEY"):
        return ObsidianAPI()

    if (os.getenv("OBSIDIAN_CLI_PATH") or "").strip():
        cli = ObsidianCLIAPI()
        try:
            if cli.test_connection():
                return cli
        except OSError:
            pass

    return ObsidianAPI()


_obsidian_singleton = None


def _get_obsidian():
    global _obsidian_singleton
    if _obsidian_singleton is None:
        _obsidian_singleton = create_obsidian_client()
    return _obsidian_singleton


class _LazyObsidian:
    """Resolves the real Obsidian client on first use so missing API keys do not break CLI-only setups."""

    def __getattr__(self, name):
        return getattr(_get_obsidian(), name)


OBSIDIAN = _LazyObsidian()
AI = FlashcardAI()
ANKI = AnkiAPI()
