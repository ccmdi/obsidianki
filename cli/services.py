"""
Global service instances to eliminate prop drilling.
"""

from api.obsidian import ObsidianAPI
from ai.client import FlashcardAI
from api.anki import AnkiAPI

OBSIDIAN = ObsidianAPI()
AI = FlashcardAI()
ANKI = AnkiAPI()