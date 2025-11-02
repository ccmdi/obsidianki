import requests
from typing import List, Dict, Any, overload, Literal
import urllib.parse
from rich.console import Console
from obsidianki.api.base import BaseAPI

console = Console()

ANKI_CUSTOM_MODEL_NAME = "ObsidianKi"
ANKI_DEFAULT_SAMPLE_SIZE = 5

class AnkiAPI(BaseAPI):
    def __init__(self, url: str = "http://127.0.0.1:8765"):
        super().__init__(url)
        self.url = url  # Keep for backward compatibility

    @overload
    def _request(self, action: Literal["deckNames"], params: None = None) -> list[str]: ...

    @overload
    def _request(self, action: Literal["modelNames"], params: None = None) -> list[str]: ...

    @overload
    def _request(self, action: Literal["findCards"], params: dict[str, Any]) -> list[int]: ...

    @overload
    def _request(self, action: Literal["cardsInfo"], params: dict[str, Any]) -> list[dict[str, Any]]: ...

    @overload
    def _request(self, action: Literal["addNote"], params: dict[str, Any]) -> int: ...

    @overload
    def _request(self, action: Literal["addNotes"], params: dict[str, Any]) -> list[int]: ...

    @overload
    def _request(self, action: Literal["deleteNotes"], params: dict[str, Any]) -> None: ...

    @overload
    def _request(self, action: Literal["updateNoteFields"], params: dict[str, Any]) -> None: ...

    @overload
    def _request(self, action: Literal["changeDeck"], params: dict[str, Any]) -> None: ...

    @overload
    def _request(self, action: Literal["deleteDecks"], params: dict[str, Any]) -> None: ...

    @overload
    def _request(self, action: Literal["createModel"], params: dict[str, Any]) -> str: ...

    @overload
    def _request(self, action: Literal["version"], params: None = None) -> int: ...

    def _request(self, action: str, params: dict[str, Any] | None = None) -> Any:
        """Make a request to AnkiConnect"""
        payload = {
            "action": action,
            "version": 5,
            "params": params or {}
        }

        response = requests.post(self.url, json=payload)
        response.raise_for_status()
        result = response.json()

        if result.get("error"):
            error_msg = result['error']
            # Handle duplicate note errors gracefully
            error_str = str(error_msg).lower()
            if 'duplicate' in error_str:
                console.print(f"[yellow]WARNING:[/yellow] Skipping duplicate note")
                return []
            else:
                raise Exception(f"AnkiConnect error: {error_msg}")

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

    def ensure_cardmodel_exists(self) -> None:
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

    def add_flashcards(self, flashcards: List, deck_name: str = "Obsidian", card_type: str = "basic") -> List[int]:
        """Add Flashcard objects to the specified deck"""
        self.ensure_deck_exists(deck_name)

        if card_type == "custom":
            self.ensure_cardmodel_exists()

        notes = []
        for card in flashcards:
            if card_type == "custom":
                note = {
                    "deckName": deck_name,
                    "modelName": ANKI_CUSTOM_MODEL_NAME,
                    "fields": {
                        "Front": card.front,
                        "Back": card.back,
                        "Origin": card.note.to_obsidian_link_html()
                    },
                    "tags": card.tags or ["obsidian-generated"]
                }
            else:  # basic
                note = {
                    "deckName": deck_name,
                    "modelName": "Basic",
                    "fields": {
                        "Front": card.front,
                        "Back": card.back
                    },
                    "tags": card.tags or ["obsidian-generated"]
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

    def get_card_examples(self, deck_name: str = "Obsidian", sample_size: int = ANKI_DEFAULT_SAMPLE_SIZE, note_paths: List[str] = []) -> List[Dict[str, str]]:
        """
        Sample existing cards from deck to use as formatting/style examples.

        Args:
            deck_name: Name of the Anki deck
            sample_size: Number of cards to sample
            note_paths: Optional list of note paths to filter cards by origin

        Returns:
            List of card examples with 'front' and 'back' fields
        """
        try:
            # important: ignores suspended/buried
            card_ids = self._request("findCards", {"query": f"deck:\"{deck_name}\" -is:suspended -is:buried"})

            if not card_ids:
                return []

            # Get card info for all cards
            cards_info = self._request("cardsInfo", {"cards": card_ids})

            if not cards_info:
                return []

            # Extract front and back field values
            examples = []
            for card in cards_info:
                fields = card.get("fields", {})
                front = fields.get("Front", {}).get("value", "")
                back = fields.get("Back", {}).get("value", "")
                origin = fields.get("Origin", {}).get("value", "")

                if not (front and back):
                    continue

                if note_paths:
                    matches = False
                    for note_path in note_paths:
                        if note_path in origin:
                            matches = True
                            break

                    if not matches:
                        continue

                examples.append({
                    "front": front,
                    "back": back
                })

            import random
            if len(examples) > sample_size:
                examples = random.sample(examples, sample_size)

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
                self.ensure_deck_exists(new_name)

            # Delete old deck (this only works if it's empty)
            self._request("deleteDecks", {"decks": [old_name], "cardsToo": False})

            return True

        except Exception as e:
            console.print(f"[red]ERROR:[/red] Failed to rename deck: {e}")
            return False

    def get_cards_for_editing(self, deck_name: str = "Obsidian", limit: int = 0) -> List[Dict[str, str]]:
        """Get cards from deck with their note IDs for editing"""
        try:
            query = f"deck:\"{deck_name}\" -is:suspended -is:buried"
            card_ids = self._request("findCards", {"query": query})

            if not card_ids:
                return []

            if limit and len(card_ids) > limit:
                import random
                card_ids = random.sample(card_ids, limit)

            # Get card info including note IDs
            cards_info = self._request("cardsInfo", {"cards": card_ids})

            if not cards_info:
                return []

            # Extract card data with note IDs
            cards = []
            for card in cards_info:
                fields = card.get("fields", {})
                front = fields.get("Front", {}).get("value", "")
                back = fields.get("Back", {}).get("value", "")
                origin = fields.get("Origin", {}).get("value", "")
                note_id = card.get("note")

                if front and back and note_id:
                    cards.append({
                        "noteId": note_id,
                        "front": front,
                        "back": back,
                        "origin": origin
                    })

            return cards

        except Exception as e:
            console.print(f"[yellow]WARNING:[/yellow] Could not get cards for editing: {e}")
            return []

    def update_note(self, note_id: int, front: str, back: str, origin: str = "") -> bool:
        """Update an existing note's fields"""
        try:
            fields = {"Front": front, "Back": back}
            if origin:
                fields["Origin"] = origin

            note_data = {
                "id": note_id,
                "fields": fields
            }

            # console.print(f"[cyan]DEBUG:[/cyan] Front length: {len(front)}, Back length: {len(back)}")
            # console.print(f"[cyan]DEBUG:[/cyan] Front: {repr(front)}")
            # console.print(f"[cyan]DEBUG:[/cyan] Back: {repr(back)}")
            result = self._request("updateNoteFields", {"note": note_data})
            # console.print(f"[cyan]DEBUG:[/cyan] Request result: {result}")
            return result is None

        except Exception as e:
            console.print(f"[red]ERROR:[/red] Failed to update note {note_id}: {e}")
            return False

    def search_cards(self, deck_name: str, query: str, limit: int = 20) -> List[Dict[str, str]]:
        """
        Search for cards in a deck by keyword in front or back.

        Args:
            deck_name: Name of the deck to search in
            query: Search query string
            limit: Maximum number of results to return

        Returns:
            List of matching cards with 'front', 'back', and 'origin' fields
        """
        try:
            # Find all cards in the deck
            card_ids = self._request("findCards", {"query": f"deck:\"{deck_name}\""})

            if not card_ids:
                return []

            # Get card info for all cards
            cards_info = self._request("cardsInfo", {"cards": card_ids})

            if not cards_info:
                return []

            # Search through cards
            query_lower = query.lower()
            matching_cards = []

            for card in cards_info:
                fields = card.get("fields", {})
                front = fields.get("Front", {}).get("value", "")
                back = fields.get("Back", {}).get("value", "")
                origin = fields.get("Origin", {}).get("value", "")

                # Check if query appears in front or back (case-insensitive)
                if query_lower in front.lower() or query_lower in back.lower():
                    matching_cards.append({
                        "front": front,
                        "back": back,
                        "origin": origin
                    })

                    # Stop if we've hit the limit
                    if len(matching_cards) >= limit:
                        break

            return matching_cards

        except Exception as e:
            console.print(f"[yellow]WARNING:[/yellow] Could not search cards: {e}")
            return []

    def test_connection(self) -> bool:
        """Test if AnkiConnect is running"""
        try:
            version = self._request("version")
            if not version:
                return False
            return version >= 5
        except Exception:
            return False