"""
Global service instances to eliminate prop drilling.
"""

from obsidianki.api.obsidian import ObsidianAPI
from obsidianki.ai.client import FlashcardAI
from obsidianki.api.anki import AnkiAPI

OBSIDIAN = ObsidianAPI()
AI = FlashcardAI()
ANKI = AnkiAPI()