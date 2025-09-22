import requests
import json
from typing import List, Dict
import urllib.parse
from rich.console import Console
from api.base import BaseAPI

console = Console()

ANKI_CUSTOM_MODEL_NAME = "ObsidianKi"
ANKI_DEFAULT_SAMPLE_SIZE = 5

class AnkiAPI(BaseAPI):
    def __init__(self, url: str = "http://127.0.0.1:8765"):
        super().__init__(url)
        self.url = url  # Keep for backward compatibility

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
            error_msg = result['error']
            # Handle duplicate note errors gracefully
            error_str = str(error_msg).lower()
            if 'duplicate' in error_str:
                console.print(f"[yellow]WARNING:[/yellow] Skipping duplicate note")
                return None
            else:
                raise Exception(f"AnkiConnect error: {error_msg}")

        return result.get("result")

    def ensure_deck(self, deck_name: str = "Obsidian") -> None:
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

    def ensure_model(self) -> None:
        """Create custom card model if it doesn't exist"""
        model_names = self._request("modelNames")

        if ANKI_CUSTOM_MODEL_NAME not in model_names:
            # Create custom model with Front, Back, and Origin fields
            model = {
                "modelName": ANKI_CUSTOM_MODEL_NAME,
                "inOrderFields": ["Front", "Back", "Origin"],
                "css": """
                    .card {
                    font-family: arial;
                    font-size: 20px;
                    text-align: center;
                    color: black;
                    background-color: white;
                    }

                    .origin {
                    font-size: 12px;
                    color: #666;
                    text-align: right;
                    margin-top: 20px;
                    }

                    code {
                    display: block;
                    text-align: left;
                    white-space: pre-wrap;
                    font-family: 'Iosevka Nerd Font', monospace;
                    background-color: #2d3748;
                    color: #e2e8f0;
                    padding: 12px 16px;
                    border-radius: 6px;
                    margin: 8px 0;
                    border-left: 4px solid #4a90e2;
                    font-size: 0.9em;
                    line-height: 1.4;
                    }

                    .highlight {
                    display: block;
                    text-align: left;
                    font-family: 'Iosevka Nerd Font', monospace;
                    border-radius: 6px;
                    margin: 8px 0;
                    border-left: 4px solid #4a90e2;
                    font-size: 0.9em;
                    line-height: 1.4;
                    overflow-x: auto;
                    }

                    .highlight pre {
                    margin: 0;
                    padding: 12px 16px;
                    }
                    """,
                "cardTemplates": [
                    {
                        "Name": "Card 1",
                        "Front": "{{Front}}",
                        "Back": "{{Front}}<hr id=\"answer\">{{Back}}<div class=\"origin\">{{Origin}}</div>"
                    }
                ]
            }

            self._request("createModel", model)
            # console.print(f"[green]SUCCESS:[/green] Created custom card model: {CUSTOM_MODEL_NAME}")

    def obsidian_link(self, note_path: str, note_title: str) -> str:
        """Generate Obsidian URI link for a note"""
        encoded_path = urllib.parse.quote(note_path, safe='')
        obsidian_link = f"obsidian://open?file={encoded_path}"
        return f"<a href='{obsidian_link}'>{note_title}</a>"

    def add_flashcards(self, flashcards: List[Dict[str, str]], deck_name: str = "Obsidian",
                      card_type: str = "basic", note_path: str = "", note_title: str = "") -> List[int]:
        """Add multiple flashcards to the specified deck"""
        self.ensure_deck(deck_name)

        if card_type == "custom":
            self.ensure_model()

        notes = []
        for card in flashcards:
            if card_type == "custom":
                origin_link = self.obsidian_link(note_path, note_title)
                note = {
                    "deckName": deck_name,
                    "modelName": ANKI_CUSTOM_MODEL_NAME,
                    "fields": {
                        "Front": card["front"],
                        "Back": card["back"],
                        "Origin": origin_link
                    },
                    "tags": ["obsidian-generated"]
                }
            else:  # basic
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

        result = self._request("addNotes", {"notes": notes})
        return result if result is not None else []

    def get_card_fronts(self, deck_name: str = "Obsidian") -> List[str]:
        """Get all card fronts from a specific deck for deduplication"""
        try:
            # Find all cards in the deck
            card_ids = self._request("findCards", {"query": f"deck:\"{deck_name}\""})

            if not card_ids:
                return []

            # Get card info for all cards
            cards_info = self._request("cardsInfo", {"cards": card_ids})

            if not cards_info:
                return []

            # Extract front field values
            fronts = []
            for card in cards_info:
                fields = card.get("fields", {})
                front = fields.get("Front", {}).get("value", "")
                if front:
                    fronts.append(front)

            return fronts

        except Exception as e:
            console.print(f"[yellow]WARNING:[/yellow] Could not get deck card fronts: {e}")
            return []

    def get_card_examples(self, deck_name: str = "Obsidian", sample_size: int = ANKI_DEFAULT_SAMPLE_SIZE) -> List[Dict[str, str]]:
        """Sample existing cards from deck to use as formatting/style examples"""
        try:
            # important: ignores suspended/buried
            card_ids = self._request("findCards", {"query": f"deck:\"{deck_name}\" -is:suspended -is:buried"})

            if not card_ids:
                return []

            import random
            if len(card_ids) > sample_size:
                card_ids = random.sample(card_ids, sample_size)

            # Get card info for sampled cards
            cards_info = self._request("cardsInfo", {"cards": card_ids})

            if not cards_info:
                return []

            # Extract front and back field values
            examples = []
            for card in cards_info:
                fields = card.get("fields", {})
                front = fields.get("Front", {}).get("value", "")
                back = fields.get("Back", {}).get("value", "")

                if front and back:
                    examples.append({
                        "front": front,
                        "back": back
                    })

            return examples

        except Exception as e:
            console.print(f"[yellow]WARNING:[/yellow] Could not get deck card examples: {e}")
            return []

    def get_decks(self) -> List[str]:
        """Get list of all deck names"""
        try:
            deck_names = self._request("deckNames")
            return deck_names if deck_names else []
        except Exception as e:
            console.print(f"[yellow]WARNING:[/yellow] Could not get deck names: {e}")
            return []

    def get_stats(self, deck_name: str) -> Dict[str, int]:
        """Get statistics for a specific deck"""
        try:
            total_cards = self._request("findCards", {"query": f"deck:\"{deck_name}\""})
            return {"total_cards": len(total_cards) if total_cards else 0}
        except Exception as e:
            console.print(f"[yellow]WARNING:[/yellow] Could not get stats for deck '{deck_name}': {e}")
            return {"total_cards": 0}

    def rename_deck(self, old_name: str, new_name: str) -> bool:
        """Rename a deck"""
        try:
            # Check if old deck exists
            deck_names = self.get_decks()
            if old_name not in deck_names:
                console.print(f"[red]ERROR:[/red] Deck '{old_name}' not found")
                return False

            # Check if new name already exists
            if new_name in deck_names:
                console.print(f"[red]ERROR:[/red] Deck '{new_name}' already exists")
                return False

            # Get all cards in the old deck
            card_ids = self._request("findCards", {"query": f"deck:\"{old_name}\""})

            if not card_ids:
                console.print(f"[yellow]WARNING:[/yellow] Deck '{old_name}' is empty")

            # Create new deck (changeDeck creates it if it doesn't exist)
            if card_ids:
                self._request("changeDeck", {"cards": card_ids, "deck": new_name})
            else:
                # Create empty deck by creating and deleting a temp card
                self.ensure_deck(new_name)

            # Delete old deck (this only works if it's empty)
            self._request("deleteDecks", {"decks": [old_name], "cardsToo": False})

            return True

        except Exception as e:
            console.print(f"[red]ERROR:[/red] Failed to rename deck: {e}")
            return False

    def test_connection(self) -> bool:
        """Test if AnkiConnect is running"""
        try:
            version = self._request("version")
            return version >= 5
        except Exception:
            return False


