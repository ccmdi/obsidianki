"""
Global service instances to eliminate prop drilling.
"""

from api.obsidian import ObsidianAPI
from ai.client import FlashcardAI
from api.anki import AnkiAPI

# Global service instances - initialized once, accessible everywhere
OBSIDIAN = ObsidianAPI()
AI = FlashcardAI()
ANKI = AnkiAPI()