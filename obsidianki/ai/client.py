from __future__ import annotations
from obsidianki.ai.call import completion
from obsidianki.ai.call import ModelResponse

import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Union

from obsidianki.cli.config import console, CONFIG, CONFIG_DIR
from obsidianki.cli.utils import process_code_blocks, strip_html
from obsidianki.cli.models import Note, Flashcard
from obsidianki.ai.models import MODEL_MAP
from obsidianki.ai.prompts import SYSTEM_PROMPT, QUERY_SYSTEM_PROMPT, TARGETED_SYSTEM_PROMPT
from obsidianki.ai.tools import FLASHCARD_TOOL, SUBMIT_FLASHCARDS_TOOL

LOGS_DIR = CONFIG_DIR / "logs"

class FlashcardAI:
    def __init__(self):
        model_name = getattr(CONFIG, 'model', 'Claude Sonnet 4.5')

        model_info = MODEL_MAP[model_name]
        self.provider = model_info["provider"]
        self.model = model_info["model"]

        self._validate_api_key()

    def _validate_api_key(self) -> None:
        """Ensure appropriate API key is available for selected provider"""
        key_map = {model_info["provider"]: model_info["key_name"] for model_info in MODEL_MAP.values()}

        required_key = key_map.get(self.provider)

        import os
        if required_key is not None:
            if required_key not in os.environ:
                raise ValueError(f"{required_key} not found in environment variables for provider {self.provider}")

        if required_key is None:
            raise ValueError(f"{required_key} not found in environment variables for provider {self.provider}")

    def _build_card_instruction(self, target_cards: int) -> str:
        context = f"create approximately {target_cards} flashcards."
        if CONFIG.use_extrapolation:
            context += " IMPORTANT: You are allowed to extrapolate with your pre-existing knowledge somewhat if you feel it is directly relevant to note substance, but is not written in the note itself."
        return context

    def _build_dedup_context(self, previous_fronts: List[str]) -> str:
        if not previous_fronts:
            return ""

        previous_questions = "\n".join([f"- {front}" for front in previous_fronts])
        dedup_context = f"""

            IMPORTANT: We have previously created the following flashcards for this note:
            {previous_questions}

            DO NOT create flashcards that ask similar questions or cover the same concepts as the ones listed above. Focus on different aspects of the content."""

        return dedup_context

    def _build_schema_context(self, deck_examples: List[Dict[str, str]]) -> str:
        """Build schema context from existing deck cards"""
        if not deck_examples:
            return ""

        examples_text = ""
        for i, example in enumerate(deck_examples, 1):
            examples_text += f"Example {i}:\nFront: {example['front']}\nBack: {strip_html(example['back'])}\n\n"

        schema_context = f"""

        IMPORTANT FORMATTING REQUIREMENTS:
        You MUST generate flashcards that strongly mirror the style and formatting of these existing cards from the deck:

        EXISTING CARD EXAMPLES:
        ```
        {examples_text.strip()}
        ```

        Your new flashcards MUST follow the same:
        - Question/answer structure and style
        - Level of detail and complexity
        - Formatting patterns (HTML patterns/link patterns, code blocks, emphasis, etc.)
        - Length and conciseness
        Generate cards that would fit seamlessly with these examples. If multiple schemas exist in the examples, generate cards in the one that is present most often."""

        return schema_context

    def _build_difficulty_context(self) -> str:
        """Build difficulty context based on configured difficulty level"""
        difficulty = CONFIG.difficulty.lower()
        if difficulty == "none":
            return ""

        if difficulty == "easy":
            return """

        DIFFICULTY LEVEL: EASY
        Focus on fundamental, directly stated information. Create flashcards that:
        - Test recall of concrete facts, definitions, and basic concepts
        - Ask straightforward questions with clear, unambiguous answers
        - Avoid requiring multi-step reasoning or complex inference
        - Cover the most essential and foundational information
        - Are suitable for initial exposure to the material

        Avoid obscure details, subtle implications, or questions requiring synthesis across multiple concepts."""

        elif difficulty == "hard":
            return """

        DIFFICULTY LEVEL: HARD
        Focus on deeper understanding and challenging retrieval. Create flashcards that:
        - Test nuanced understanding, subtle distinctions, and edge cases
        - Require synthesis of multiple concepts or ideas from the material
        - Ask about implications, consequences, and non-obvious connections
        - Include challenging technical details and advanced applications
        - Test the ability to apply concepts in novel contexts or identify limitations

        You may include questions about:
        - Why certain approaches are used over alternatives
        - Potential pitfalls or common misconceptions
        - Relationships between different concepts in the material
        - Edge cases and boundary conditions
        - Implications that aren't explicitly stated but follow from the material"""

        else:  # normal (default)
            return """

        DIFFICULTY LEVEL: NORMAL
        Create a balanced mix of flashcards that:
        - Cover both fundamental concepts and deeper understanding
        - Include straightforward recall as well as some application and analysis
        - Test understanding at a standard difficulty level appropriate for active learning
        - Balance between concrete facts and conceptual relationships
        - Are challenging enough to promote retention but not frustratingly obscure"""

        return ""

    def _get_tool_choice(self, function_name: str) -> str:
        return 'required'

    def _call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        tools: List[Dict[str, object]],
        tool_choice: Union[str, Dict[str, object]],
        max_tokens: int = 8000
    ) -> Optional[ModelResponse]:
        """Unified LLM call"""
        try:
            response = completion(model=self.model, messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}], provider=self.provider, tools=tools, tool_choice=tool_choice, max_tokens=max_tokens)
            return response
        except Exception as e:
            console.print(f"[red]ERROR:[/red] LLM call failed: {e}")
            return None

    def _extract_flashcards_from_response(
        self,
        response: Optional[ModelResponse],
        note: Note,
        default_tags: Optional[List[str]] = None
    ) -> List[Flashcard]:
        """Extract and process flashcards from LLM response

        Args:
            response: The LLM response containing tool calls
            note: The note to associate with flashcards
            default_tags: Optional default tags if card doesn't specify any

        Returns:
            List of processed Flashcard objects
        """
        if not response:
            return []

        try:
            message = response.choices[0].message
            if not hasattr(message, 'tool_calls') or not message.tool_calls:
                console.print("[yellow]WARNING:[/yellow] No flashcards generated - unexpected response format")
                return []

            tool_call = message.tool_calls[0]
            arguments = json.loads(tool_call.function.arguments)
            flashcard_dicts = arguments.get('flashcards', [])

            flashcard_objects = []
            for card in flashcard_dicts:
                front_original = card.get('front', '')
                back_original = card.get('back', '')

                # Process code blocks with syntax highlighting
                front_processed = process_code_blocks(front_original, CONFIG.syntax_highlighting)
                back_processed = process_code_blocks(back_original, CONFIG.syntax_highlighting)

                # Determine tags priority: card's tags > default_tags > note's tags
                tags = card.get('tags') or default_tags or note.tags.copy()

                flashcard = Flashcard(
                    front=front_processed,
                    back=back_processed,
                    note=note,
                    tags=tags,
                    front_original=front_original,
                    back_original=back_original
                )
                flashcard_objects.append(flashcard)

            return flashcard_objects

        except Exception as e:
            console.print(f"[red]ERROR:[/red] Failed to parse flashcards: {e}")
            return []

    def _serialize_tool_calls(self, tool_calls) -> Optional[List[Dict]]:
        """Serialize tool calls to JSON-compatible format."""
        if not tool_calls:
            return None
        result = []
        for tc in tool_calls:
            serialized = {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments
                }
            }
            # Preserve provider-specific data (e.g., Gemini thought_signature)
            if hasattr(tc, 'extra') and tc.extra:
                serialized["extra"] = tc.extra
            result.append(serialized)
        return result

    def _log_conversation(
        self,
        messages: List[Dict],
        note: Optional[Note] = None,
        flashcards: Optional[List[Flashcard]] = None,
        mode: str = "generate"
    ) -> None:
        """Log conversation to file for debugging."""
        try:
            LOGS_DIR.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            note_name = note.filename.replace(".md", "") if note else "query"
            safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in note_name)[:30]
            log_file = LOGS_DIR / f"{timestamp}_{safe_name}.json"

            log_data = {
                "timestamp": datetime.now().isoformat(),
                "model": self.model,
                "mode": mode,
                "note": note.path if note else None,
                "messages": messages,
                "result": {
                    "count": len(flashcards) if flashcards else 0,
                    "cards": [
                        {"front": fc.front_original, "back": fc.back_original}
                        for fc in (flashcards or [])
                    ]
                }
            }

            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(log_data, f, indent=2, ensure_ascii=False)

        except Exception as e:
            console.print(f"[dim]Log write failed: {e}[/dim]")

    def _generate_with_vector_feedback(
        self,
        system_prompt: str,
        user_prompt: str,
        note: Note,
        default_tags: Optional[List[str]] = None
    ) -> List[Flashcard]:
        """Generate flashcards with vector similarity feedback loop.

        Multi-turn conversation where:
        1. LLM proposes cards via create_flashcards
        2. System checks against vector DB, returns similarity feedback
        3. LLM can revise or call submit_flashcards to confirm
        """
        from obsidianki.ai.vectors import get_vectors

        vectors = get_vectors()
        threshold = CONFIG.vector_threshold or 0.85
        max_turns = CONFIG.vector_max_turns or 5

        # Show vector index status
        index_count = vectors.count()
        if index_count == 0:
            console.print("[dim]Vector index empty - no similarity checks will match[/dim]")
        # else:
        #     console.print(f"[dim]Vector index: {index_count} cards indexed[/dim]")

        messages: List[Dict[str, object]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        pending_cards: List[Dict] = []

        for turn in range(max_turns):
            try:
                response = completion(
                    model=self.model,
                    messages=messages,
                    provider=self.provider,
                    tools=[FLASHCARD_TOOL, SUBMIT_FLASHCARDS_TOOL],
                    tool_choice="required" if turn == 0 else "auto",
                    max_tokens=8000
                )

                message = response.choices[0].message

                # Add assistant message to history (serialize tool_calls to dict)
                messages.append({
                    "role": "assistant",
                    "content": message.content or "",
                    "tool_calls": self._serialize_tool_calls(message.tool_calls) if hasattr(message, 'tool_calls') else None
                })

                if not hasattr(message, 'tool_calls') or not message.tool_calls:
                    # No tool call - shouldn't happen but handle gracefully
                    if pending_cards:
                        return self._convert_pending_to_flashcards(pending_cards, note, default_tags)
                    break

                tool_call = message.tool_calls[0]
                tool_name = tool_call.function.name

                if tool_name == "create_flashcards":
                    args = json.loads(tool_call.function.arguments)
                    pending_cards = args.get("flashcards", [])

                    # Check each card against vector DB
                    similar_matches = vectors.find_similar_batch(
                        [card.get("front", "") for card in pending_cards],
                        threshold
                    )

                    if similar_matches:
                        # Build feedback message - now handles multiple matches per card
                        feedback_lines = []
                        total_matches = 0
                        high_similarity = False
                        for idx, front, matches in similar_matches:
                            for existing, score in matches:
                                feedback_lines.append(
                                    f"- Card {idx + 1} ({score:.0%} similar): \"{front}\" ≈ \"{existing}\""
                                )
                                total_matches += 1
                                if score >= 0.85:
                                    high_similarity = True

                        if high_similarity:
                            instruction = (
                                "Cards with ≥85% similarity are TOO SIMILAR and should NOT be submitted.\n"
                                "You MUST call create_flashcards again with substantially different questions."
                            )
                        else:
                            instruction = (
                                "You may:\n"
                                "1. Call create_flashcards again with revised cards that explore different angles\n"
                                "2. Call submit_flashcards if you believe these are sufficiently distinct"
                            )

                        feedback = f"Similar existing cards found:\n{chr(10).join(feedback_lines)}\n\n{instruction}"
                        console.print(f"[yellow]Vector feedback:[/yellow] {total_matches} similar match(es) for {len(similar_matches)} card(s)")
                        for line in feedback_lines:
                            console.print(f"[dim]{line}[/dim]")
                    else:
                        feedback = "No similar cards found in the database. Call submit_flashcards to confirm."
                        console.print("[green]Vector check:[/green] No similar cards found")

                    messages.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": tool_name,
                        "content": feedback
                    })

                elif tool_name == "submit_flashcards":
                    # Finalize submission
                    messages.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": tool_name,
                        "content": f"{len(pending_cards)} cards submitted."
                    })
                    console.print(f"[green]Submitted:[/green] {len(pending_cards)} cards")
                    flashcards = self._convert_pending_to_flashcards(pending_cards, note, default_tags)
                    self._log_conversation(messages, note, flashcards, mode="vector_feedback")
                    return flashcards

            except Exception as e:
                console.print(f"[red]ERROR:[/red] Vector feedback loop failed: {e}")
                if pending_cards:
                    flashcards = self._convert_pending_to_flashcards(pending_cards, note, default_tags)
                    self._log_conversation(messages, note, flashcards, mode="vector_feedback_error")
                    return flashcards
                self._log_conversation(messages, note, [], mode="vector_feedback_error")
                return []

        # Max turns reached - return whatever we have
        if pending_cards:
            console.print(f"[yellow]Max turns reached:[/yellow] Submitting {len(pending_cards)} pending cards")
            flashcards = self._convert_pending_to_flashcards(pending_cards, note, default_tags)
            self._log_conversation(messages, note, flashcards, mode="vector_feedback_max_turns")
            return flashcards

        self._log_conversation(messages, note, [], mode="vector_feedback_empty")
        return []

    def _convert_pending_to_flashcards(
        self,
        pending_cards: List[Dict],
        note: Note,
        default_tags: Optional[List[str]] = None
    ) -> List[Flashcard]:
        """Convert pending card dicts to Flashcard objects with processing."""
        flashcard_objects = []
        for card in pending_cards:
            front_original = card.get('front', '')
            back_original = card.get('back', '')

            # Process code blocks with syntax highlighting
            front_processed = process_code_blocks(front_original, CONFIG.syntax_highlighting)
            back_processed = process_code_blocks(back_original, CONFIG.syntax_highlighting)

            # Determine tags priority: card's tags > default_tags > note's tags
            tags = card.get('tags') or default_tags or note.tags.copy()

            flashcard = Flashcard(
                front=front_processed,
                back=back_processed,
                note=note,
                tags=tags,
                front_original=front_original,
                back_original=back_original
            )
            flashcard_objects.append(flashcard)

        return flashcard_objects

    def generate_flashcards(
        self,
        note: Note,
        target_cards: int,
        previous_fronts: List[str] = [],
        deck_examples: List[Dict[str, str]] = []
    ) -> List[Flashcard]:
        """Generate flashcards from a Note object using LLM"""
        card_instruction = self._build_card_instruction(target_cards)
        dedup_context = self._build_dedup_context(previous_fronts)
        schema_context = self._build_schema_context(deck_examples)
        difficulty_context = self._build_difficulty_context()

        user_prompt = f"""Note Title: {note.filename}

        Note Content:
        {note.content}{difficulty_context}{dedup_context}{schema_context}

        Please analyze this note and {card_instruction} for the key information that would be valuable for spaced repetition learning."""

        # Use vector feedback loop if enabled
        if CONFIG.vector_dedup:
            return self._generate_with_vector_feedback(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=user_prompt,
                note=note
            )

        # Original single-shot behavior
        messages: List[Dict[str, object]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ]
        response = self._call_llm(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            tools=[FLASHCARD_TOOL],
            tool_choice=self._get_tool_choice("create_flashcards")
        )

        flashcards = self._extract_flashcards_from_response(response, note)
        if response and response.choices[0].message.tool_calls:
            messages.append({
                "role": "assistant",
                "content": response.choices[0].message.content or "",
                "tool_calls": self._serialize_tool_calls(response.choices[0].message.tool_calls)
            })
        self._log_conversation(messages, note, flashcards, mode="generate")
        return flashcards

    def generate_from_query(
        self,
        query: str,
        target_cards: int,
        previous_fronts: List[str] = [],
        deck_examples: List[Dict[str, str]] = []
    ) -> List[Flashcard]:
        """Generate flashcards based on a user query without source material"""
        card_instruction = self._build_card_instruction(target_cards)
        dedup_context = self._build_dedup_context(previous_fronts)
        schema_context = self._build_schema_context(deck_examples)
        difficulty_context = self._build_difficulty_context()

        user_prompt = f"""User Query: {query}

        Please {card_instruction} to help someone learn about this topic. Focus on the most important concepts, definitions, and practical information related to this query.{difficulty_context}{dedup_context}{schema_context}"""

        # Create virtual Note object for query-based flashcards
        virtual_note = Note(
            path="query",
            filename=f"Query: {query}",
            content=query,
            tags=["query-generated"],
            size=0
        )

        # Use vector feedback loop if enabled
        if CONFIG.vector_dedup:
            return self._generate_with_vector_feedback(
                system_prompt=QUERY_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                note=virtual_note,
                default_tags=["query-generated"]
            )

        # Original single-shot behavior
        messages: List[Dict[str, object]] = [
            {"role": "system", "content": QUERY_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ]
        response = self._call_llm(
            system_prompt=QUERY_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            tools=[FLASHCARD_TOOL],
            tool_choice=self._get_tool_choice("create_flashcards")
        )

        flashcards = self._extract_flashcards_from_response(response, virtual_note, default_tags=["query-generated"])
        if response and response.choices[0].message.tool_calls:
            messages.append({
                "role": "assistant",
                "content": response.choices[0].message.content or "",
                "tool_calls": self._serialize_tool_calls(response.choices[0].message.tool_calls)
            })
        self._log_conversation(messages, virtual_note, flashcards, mode="query")
        return flashcards

    def generate_from_note_query(self, note: Note, query: str, target_cards: int, previous_fronts: List[str] | None = None, deck_examples: List[Dict[str, str]] | None = None) -> List[Flashcard]:
        """Generate flashcards by extracting specific information from a note based on a query"""
        if previous_fronts is None:
            previous_fronts = []
        if deck_examples is None:
            deck_examples = []

        card_instruction = self._build_card_instruction(target_cards)
        dedup_context = self._build_dedup_context(previous_fronts)
        schema_context = self._build_schema_context(deck_examples)
        difficulty_context = self._build_difficulty_context()

        user_prompt = f"""Note Title: {note.filename}
        Query: {query}

        Note Content:
        {note.content}{difficulty_context}{dedup_context}{schema_context}

        Please analyze this note and extract information specifically related to the query "{query}". {card_instruction} only for information in the note that directly addresses or relates to this query."""

        # Use vector feedback loop if enabled
        if CONFIG.vector_dedup:
            return self._generate_with_vector_feedback(
                system_prompt=TARGETED_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                note=note
            )

        # Original single-shot behavior
        messages: List[Dict[str, object]] = [
            {"role": "system", "content": TARGETED_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ]
        response = self._call_llm(
            system_prompt=TARGETED_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            tools=[FLASHCARD_TOOL],
            tool_choice=self._get_tool_choice("create_flashcards")
        )

        flashcards = self._extract_flashcards_from_response(response, note)
        if response and response.choices[0].message.tool_calls:
            messages.append({
                "role": "assistant",
                "content": response.choices[0].message.content or "",
                "tool_calls": self._serialize_tool_calls(response.choices[0].message.tool_calls)
            })
        self._log_conversation(messages, note, flashcards, mode="note_query")
        return flashcards

    def edit_cards(self, cards: List[Dict[str, str]], query: str) -> List[Dict[str, str]]:
        """Edit existing cards based on a query"""
        if not cards:
            return []

        # Build card context
        cards_context = ""
        for i, card in enumerate(cards, 1):
            front_clean = strip_html(card['front'])
            back_clean = strip_html(card['back'])
            cards_context += f"Card {i}:\nFront: {front_clean}\nBack: {back_clean}\n\n"

        edit_system_prompt = """You are a flashcard editor. Your task is to apply specific edits to existing flashcards while maintaining their learning value and structure.

When editing cards:
- Apply the requested changes accurately
- Preserve the intent and learning value of each card
- Keep the same level of detail unless asked to change it
- Maintain consistent formatting across cards
- If a card doesn't need changes based on the instruction, keep it exactly as is
- Use markdown formatting with triple backticks (```) for code blocks
- Do NOT use HTML tags - use markdown instead"""

        edit_prompt = f"""Here are the existing cards (shown in plain text format):
{cards_context}

INSTRUCTION: {query}

Please apply the requested changes to ALL cards and return them using the create_flashcards tool. You must provide exactly {len(cards)} flashcards - one for each original card in order.

IMPORTANT:
- Return ALL {len(cards)} cards in the same order
- Apply the instruction to each card as appropriate
- If a card doesn't need changes, return it unchanged
- Use markdown syntax with triple backticks for code blocks (```language\\ncode\\n```)
- Do NOT use HTML tags like <pre>, <code>, <div>, etc."""

        response = self._call_llm(
            system_prompt=edit_system_prompt,
            user_prompt=edit_prompt,
            tools=[FLASHCARD_TOOL],
            tool_choice=self._get_tool_choice("create_flashcards"),
            max_tokens=4000
        )

        if not response:
            return cards

        try:
            message = response.choices[0].message
            if hasattr(message, 'tool_calls') and message.tool_calls:
                tool_call = message.tool_calls[0]
                flashcard_data = json.loads(tool_call.function.arguments)

                if "flashcards" in flashcard_data:
                    edited_cards = []
                    for flashcard in flashcard_data["flashcards"]:
                        if "front" in flashcard and "back" in flashcard:
                            front_original = flashcard["front"]
                            back_original = flashcard["back"]

                            front_processed = process_code_blocks(front_original, CONFIG.syntax_highlighting)
                            back_processed = process_code_blocks(back_original, CONFIG.syntax_highlighting)

                            edited_cards.append({
                                "front": front_processed,
                                "back": back_processed,
                                "front_original": front_original,
                                "back_original": back_original,
                                "origin": flashcard.get("origin", "")
                            })

                    if len(edited_cards) != len(cards):
                        console.print(f"[yellow]WARNING:[/yellow] Expected {len(cards)} edited cards, got {len(edited_cards)}.")
                        console.print(f"[yellow]AI returned incomplete results. Using original cards.[/yellow]")
                        return cards

                    return edited_cards
        except Exception as e:
            import traceback
            console.print(f"[red]ERROR:[/red] Failed to edit cards: {e}")
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
            return cards

        return cards
