import os
from dotenv import load_dotenv
from anthropic import Anthropic
from typing import List, Dict, Any
import json
from obsidian import ObsidianAPI

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

            print("No flashcards generated - unexpected response format")
            return []

        except Exception as e:
            print(f"Error generating flashcards: {e}")
            return []

    def test_flashcard_generation(self, note_content: str, note_title: str = "Test Note") -> None:
        """Test flashcard generation and display results"""
        print(f"\n=== Testing Flashcard Generation for: {note_title} ===")
        print(f"Note content length: {len(note_content)} characters")
        print("\n--- Generating flashcards... ---")

        flashcards = self.generate_flashcards(note_content, note_title)

        if flashcards:
            print(f"\n✓ Generated {len(flashcards)} flashcards:")
            for i, card in enumerate(flashcards, 1):
                print(f"\n{i}. Front: {card['front']}")
                print(f"   Back: {card['back']}")
        else:
            print("✗ No flashcards generated")


if __name__ == "__main__":
    try:
        # Initialize both AI and Obsidian clients
        ai = FlashcardAI()
        obsidian = ObsidianAPI()

        print("Testing AI flashcard generation with a random old note...")

        # Get a random old note
        old_notes = obsidian.get_random_old_notes(days=7, limit=1)

        if old_notes:
            note = old_notes[0]
            note_path = note['result']['path']
            note_title = note['result']['filename']

            print(f"Selected note: {note_title}")

            # Get note content
            note_content = obsidian.get_note_content(note_path)

            if note_content:
                # Test flashcard generation
                ai.test_flashcard_generation(note_content, note_title)
            else:
                print("Error: Could not retrieve note content")
        else:
            print("No old notes found to test with")

    except ValueError as e:
        print(f"Configuration error: {e}")
        print("Please ensure both ANTHROPIC_API_KEY and OBSIDIAN_API_KEY are set in your .env file")
    except Exception as e:
        print(f"Error: {e}")