import os
from dotenv import load_dotenv
from anthropic import Anthropic
from typing import List, Dict, Any
import json
from obsidian import ObsidianAPI
from rich.console import Console

console = Console()

load_dotenv()

# Flashcard schema for tool calling
FLASHCARD_TOOL = {
    "name": "create_flashcards",
    "description": "Create flashcards from note content with front (question) and back (answer)",
    "input_schema": {
        "type": "object",
        "properties": {
            "flashcards": {
                "type": "array",
                "description": "Array of flashcards extracted from the note",
                "items": {
                    "type": "object",
                    "properties": {
                        "front": {
                            "type": "string",
                            "description": "The question or prompt for the flashcard"
                        },
                        "back": {
                            "type": "string",
                            "description": "The answer or information for the flashcard"
                        }
                    },
                    "required": ["front", "back"]
                }
            }
        },
        "required": ["flashcards"]
    }
}

# System prompt for flashcard generation
SYSTEM_PROMPT = """You are an expert at creating high-quality flashcards for spaced repetition learning. Your job is to analyze note content and extract key information that would be valuable for long-term retention.

FLASHCARD CREATION GUIDELINES:
1. Focus on factual information, definitions, concepts, and relationships
2. Create clear, specific questions that test understanding
3. Keep answers concise but complete
4. Avoid overly obvious or trivial information
5. Look for information that would benefit from spaced repetition
6. Create 1-3 flashcards per note (depending on content richness)

GOOD FLASHCARD EXAMPLES:
- Front: "What is the primary function of mitochondria?" Back: "Generate ATP (energy) for cellular processes"
- Front: "Who developed the concept of 'deliberate practice'?" Back: "Anders Ericsson"
- Front: "What are the three pillars of observability?" Back: "Metrics, logs, and traces"

AVOID:
- Questions with yes/no answers unless conceptually important
- Information that's too specific/detailed to be useful
- Duplicate concepts across multiple cards
- Questions that require external context not in the note

Analyze the provided note content and extract the most valuable information as flashcards using the create_flashcards tool."""

class FlashcardAI:
    def __init__(self):
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

        if not os.getenv("ANTHROPIC_API_KEY"):
            raise ValueError("ANTHROPIC_API_KEY not found in environment variables")

    def generate_flashcards(self, note_content: str, note_title: str = "") -> List[Dict[str, str]]:
        """Generate flashcards from note content using Claude"""

        user_prompt = f"""Note Title: {note_title}

        Note Content:
        {note_content}

        Please analyze this note and create flashcards for the key information that would be valuable for spaced repetition learning."""

        try:
            response = self.client.messages.create(
                model="claude-4-sonnet-20250514",
                max_tokens=8000,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
                tools=[FLASHCARD_TOOL],
                tool_choice={"type": "tool", "name": "create_flashcards"}
            )

            # Extract flashcards from tool call
            if response.content and len(response.content) > 0:
                for content_block in response.content:
                    if content_block.type == "tool_use":
                        tool_input = content_block.input
                        return tool_input.get("flashcards", [])

            console.print("[yellow]WARNING:[/yellow] No flashcards generated - unexpected response format")
            return []

        except Exception as e:
            console.print(f"[red]ERROR:[/red] Error generating flashcards: {e}")
            return []

if __name__ == "__main__":
    ai = FlashcardAI()
    obsidian = ObsidianAPI()

    old_notes = obsidian.get_random_old_notes(days=7, limit=1)
    note = old_notes[0]
    note_content = obsidian.get_note_content(note['result']['path'])

    flashcards = ai.generate_flashcards(note_content, note['result']['filename'])
    for card in flashcards:
        console.print(f"[cyan]Q:[/cyan] {card['front']}")
        console.print(f"[green]A:[/green] {card['back']}\n")