"""Dummy AI implementation that returns static responses"""
from typing import List, Dict
from obsidianki.cli.models import Note, Flashcard


class DummyFlashcardAI:
    """Mock AI that returns static flashcard data"""

    def generate_flashcards(
        self, note: Note, target_cards: int, previous_fronts: list = None, deck_examples: list = None
    ) -> List[Flashcard]:
        """Generate dummy flashcards"""
        flashcards = []
        for i in range(min(target_cards, 3)):  # Generate up to 3 cards
            flashcard = Flashcard(
                front=f"Question {i+1} from {note.filename}",
                back=f"Answer {i+1}",
                note=note,
                tags=note.tags or ["test-generated"],
                front_original=f"Question {i+1} from {note.filename}",
                back_original=f"Answer {i+1}"
            )
            flashcards.append(flashcard)
        return flashcards

    def generate_from_query(
        self, query: str, target_cards: int, previous_fronts: list = None, deck_examples: list = None
    ) -> List[Flashcard]:
        """Generate dummy flashcards from query"""
        # Create virtual note for query
        virtual_note = Note(
            path="query",
            filename=f"Query: {query}",
            content=query,
            tags=["query-generated"],
            size=len(query)
        )

        flashcards = []
        for i in range(min(target_cards, 2)):
            flashcard = Flashcard(
                front=f"Question {i+1} about: {query[:50]}",
                back=f"Answer {i+1}",
                note=virtual_note,
                tags=["query-generated"],
                front_original=f"Question {i+1} about: {query[:50]}",
                back_original=f"Answer {i+1}"
            )
            flashcards.append(flashcard)
        return flashcards

    def generate_from_note_query(
        self, note: Note, query: str, target_cards: int, previous_fronts: list = None, deck_examples: list = None
    ) -> List[Flashcard]:
        """Generate dummy flashcards from note with query"""
        flashcards = []
        for i in range(min(target_cards, 2)):
            flashcard = Flashcard(
                front=f"Question {i+1} about '{query}' in {note.filename}",
                back=f"Answer {i+1}",
                note=note,
                tags=note.tags or ["test-generated"],
                front_original=f"Question {i+1} about '{query}' in {note.filename}",
                back_original=f"Answer {i+1}"
            )
            flashcards.append(flashcard)
        return flashcards

    def edit_cards(self, cards: List[Dict[str, str]], query: str) -> List[Dict[str, str]]:
        """Return cards with minimal edits"""
        edited = []
        for card in cards:
            edited.append({
                "front": card["front"] + " [edited]",
                "back": card["back"] + " [edited]",
                "front_original": card.get("front_original", card["front"]) + " [edited]",
                "back_original": card.get("back_original", card["back"]) + " [edited]",
                "origin": card.get("origin", "")
            })
        return edited
