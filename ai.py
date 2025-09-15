import os
from anthropic import Anthropic
from typing import List, Dict
from config import console

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
6. Create the requested number of flashcards when specified, otherwise 1-3 per note

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

# System prompt for query-based flashcard generation
QUERY_SYSTEM_PROMPT = """You are an expert at creating high-quality flashcards based on user queries. Your job is to generate educational flashcards that help users learn and remember information about their specific query.

QUERY-BASED FLASHCARD GUIDELINES:
1. Create flashcards that directly address the user's query
2. Include fundamental concepts, definitions, and practical examples
3. Break complex topics into digestible pieces
4. Focus on information that benefits from spaced repetition
5. Create the requested number of flashcards when specified, otherwise 2-4 per query

GOOD QUERY FLASHCARD EXAMPLES:
Query: "how to center a div"
- Front: "What CSS property centers a div horizontally using flexbox?" Back: "display: flex; justify-content: center;"
- Front: "What CSS technique centers a div both horizontally and vertically?" Back: "display: flex; justify-content: center; align-items: center;"

Query: "React fragments"
- Front: "What is a React Fragment used for?" Back: "Grouping multiple elements without adding extra DOM nodes"
- Front: "What are the two ways to write React Fragments?" Back: "<React.Fragment> or shorthand <>"

Generate educational flashcards based on the user's query using the create_flashcards tool."""

# System prompt for targeted extraction from notes
TARGETED_SYSTEM_PROMPT = """You are an expert at extracting specific information from notes to create targeted flashcards. Your job is to analyze the provided note content and create flashcards that specifically address the user's query within the context of that note.

TARGETED EXTRACTION GUIDELINES:
1. Focus ONLY on information in the note that relates to the user's query
2. Extract specific examples, syntax, or concepts that answer the query
3. If the note doesn't contain relevant information, create fewer or no cards
4. Prioritize practical, actionable information over theory
5. Create the requested number of flashcards when specified, otherwise 1-3 per note-query pair

GOOD TARGETED EXTRACTION EXAMPLES:
Query: "syntax for fragments" + React note content
- Extract specific React Fragment syntax examples from the note
- Focus on practical usage patterns mentioned in the note

Query: "error handling" + JavaScript note content
- Extract specific error handling patterns from the note
- Focus on try-catch examples or error handling strategies mentioned

Analyze the note content and extract information specifically related to the user's query using the create_flashcards tool."""

class FlashcardAI:
    def __init__(self):
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

        if not os.getenv("ANTHROPIC_API_KEY"):
            raise ValueError("ANTHROPIC_API_KEY not found in environment variables")

    def generate_flashcards(self, note_content: str, note_title: str = "", target_cards: int = None) -> List[Dict[str, str]]:
        """Generate flashcards from note content using Claude"""

        card_instruction = f"Create approximately {target_cards} flashcards" if target_cards else "Create 1-3 flashcards"

        user_prompt = f"""Note Title: {note_title}

        Note Content:
        {note_content}

        Please analyze this note and {card_instruction} for the key information that would be valuable for spaced repetition learning."""

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

    def generate_flashcards_from_query(self, query: str, target_cards: int = None) -> List[Dict[str, str]]:
        """Generate flashcards based on a user query without source material"""

        card_instruction = f"Create approximately {target_cards} flashcards" if target_cards else "Create 2-4 flashcards"

        user_prompt = f"""User Query: {query}

Please {card_instruction} to help someone learn about this topic. Focus on the most important concepts, definitions, and practical information related to this query."""

        try:
            response = self.client.messages.create(
                model="claude-4-sonnet-20250514",
                max_tokens=8000,
                system=QUERY_SYSTEM_PROMPT,
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
            console.print(f"[red]ERROR:[/red] Error generating flashcards from query: {e}")
            return []

    def generate_flashcards_from_note_and_query(self, note_content: str, note_title: str, query: str, target_cards: int = None) -> List[Dict[str, str]]:
        """Generate flashcards by extracting specific information from a note based on a query"""

        card_instruction = f"Create approximately {target_cards} flashcards" if target_cards else "Create 1-3 flashcards"

        user_prompt = f"""Note Title: {note_title}
Query: {query}

Note Content:
{note_content}

Please analyze this note and extract information specifically related to the query "{query}". {card_instruction} only for information in the note that directly addresses or relates to this query."""

        try:
            response = self.client.messages.create(
                model="claude-4-sonnet-20250514",
                max_tokens=8000,
                system=TARGETED_SYSTEM_PROMPT,
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
            console.print(f"[red]ERROR:[/red] Error generating targeted flashcards: {e}")
            return []

