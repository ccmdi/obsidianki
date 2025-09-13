import requests
import json
from typing import List, Dict

class AnkiAPI:
    def __init__(self, url: str = "http://127.0.0.1:8765"):
        self.url = url

    def _request(self, action: str, params: dict = None) -> dict:
        """Make a request to AnkiConnect"""
        payload = {
            "action": action,
            "version": 5,
            "params": params or {}
        }

        response = requests.post(self.url, json=payload)
        result = response.json()

        if result.get("error"):
            raise Exception(f"AnkiConnect error: {result['error']}")

        return result.get("result")

    def ensure_deck_exists(self, deck_name: str = "Obsidian") -> None:
        """Check if deck exists, create it if it doesn't"""
        deck_names = self._request("deckNames")

        if deck_name not in deck_names:
            # Create deck using changeDeck action which creates deck if it doesn't exist
            # First create a temporary note in Default deck
            temp_note = {
                "deckName": "Default",
                "modelName": "Basic",
                "fields": {"Front": "temp", "Back": "temp"},
                "tags": ["temp"]
            }

            note_id = self._request("addNote", {"note": temp_note})

            # Find the card for this note
            card_ids = self._request("findCards", {"query": f"tag:temp"})

            if card_ids:
                # Move the card to the new deck (this creates the deck)
                self._request("changeDeck", {"cards": card_ids, "deck": deck_name})

                # Delete the temporary note
                self._request("deleteNotes", {"notes": [note_id]})

    def add_flashcards(self, flashcards: List[Dict[str, str]], deck_name: str = "Obsidian") -> List[int]:
        """Add multiple flashcards to the specified deck"""
        self.ensure_deck_exists(deck_name)

        notes = []
        for card in flashcards:
            note = {
                "deckName": deck_name,
                "modelName": "Basic",
                "fields": {
                    "Front": card["front"],
                    "Back": card["back"]
                },
                "tags": ["obsidian-generated"]
            }
            notes.append(note)

        return self._request("addNotes", {"notes": notes})

    def test_connection(self) -> bool:
        """Test if AnkiConnect is running"""
        try:
            version = self._request("version")
            return version >= 5
        except Exception:
            return False


if __name__ == "__main__":
    anki = AnkiAPI()

    if anki.test_connection():
        print("AnkiConnect is running")
        
        # Test with sample flashcards
        test_cards = [
            {"front": "What is the capital of France?", "back": "Paris"},
            {"front": "What is 2 + 2?", "back": "4"}
        ]

        result = anki.add_flashcards(test_cards)
        print(f"Added {len([r for r in result if r is not None])} cards to Obsidian deck")
    else:
        print("AnkiConnect not running on http://127.0.0.1:8765")