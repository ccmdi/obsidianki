"""Dummy Anki API implementation"""
from typing import List, Dict


class DummyAnkiAPI:
    """Mock Anki API that returns success responses"""

    def __init__(self):
        self.decks = ["Default", "Test Deck"]
        self.cards = {}  # deck_name -> list of cards

    def test_connection(self) -> bool:
        """Always return success"""
        return True

    def ensure_deck_exists(self, deck_name: str = "Obsidian") -> None:
        """Add deck if not exists"""
        if deck_name not in self.decks:
            self.decks.append(deck_name)

    def ensure_cardmodel_exists(self) -> None:
        """Mock card model creation"""
        pass

    def add_flashcards(
        self, flashcards: List, deck_name: str = "Obsidian", card_type: str = "basic"
    ) -> List[int]:
        """Mock adding flashcards - return success IDs"""
        self.ensure_deck_exists(deck_name)

        if deck_name not in self.cards:
            self.cards[deck_name] = []

        result = []
        for i, card in enumerate(flashcards):
            note_id = len(self.cards[deck_name]) + i + 1
            self.cards[deck_name].append({
                "id": note_id,
                "front": card.front,
                "back": card.back,
                "tags": card.tags
            })
            result.append(note_id)

        return result

    def get_card_fronts(self, deck_name: str = "Obsidian") -> List[str]:
        """Return existing card fronts"""
        if deck_name not in self.cards:
            return []
        return [card["front"] for card in self.cards[deck_name]]

    def get_card_examples(self, deck_name: str = "Obsidian", sample_size: int = 5) -> List[Dict[str, str]]:
        """Return example cards"""
        return [
            {"front": "Example Question 1", "back": "Example Answer 1"},
            {"front": "Example Question 2", "back": "Example Answer 2"},
        ]

    def get_decks(self) -> List[str]:
        """Return list of decks"""
        return self.decks

    def get_stats(self, deck_name: str) -> Dict[str, int]:
        """Return deck stats"""
        card_count = len(self.cards.get(deck_name, []))
        return {"total_cards": card_count}

    def rename_deck(self, old_name: str, new_name: str) -> bool:
        """Rename a deck"""
        if old_name in self.decks:
            idx = self.decks.index(old_name)
            self.decks[idx] = new_name
            if old_name in self.cards:
                self.cards[new_name] = self.cards.pop(old_name)
            return True
        return False

    def get_cards_for_editing(self, deck_name: str = "Obsidian", limit: int = None) -> List[Dict[str, str]]:
        """Get cards for editing"""
        if deck_name not in self.cards:
            return []

        cards = []
        for card in self.cards[deck_name][:limit] if limit else self.cards[deck_name]:
            cards.append({
                "noteId": card["id"],
                "front": card["front"],
                "back": card["back"],
                "origin": ""
            })
        return cards

    def update_note(self, note_id: int, front: str, back: str, origin: str = None) -> bool:
        """Update a note"""
        # Find and update the card
        for deck_cards in self.cards.values():
            for card in deck_cards:
                if card["id"] == note_id:
                    card["front"] = front
                    card["back"] = back
                    return True
        return False

    def obsidian_link(self, note) -> str:
        """Generate mock Obsidian link"""
        return f"<a href='obsidian://open?file={note.path}'>{note.filename}</a>"
