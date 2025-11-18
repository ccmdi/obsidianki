import os
from anthropic import Anthropic
from typing import List, Dict, cast, Any

from obsidianki.cli.config import console, CONFIG
from obsidianki.cli.utils import process_code_blocks, strip_html
from obsidianki.cli.models import Note, Flashcard
from anthropic.types import ToolChoiceParam, MessageParam
from obsidianki.ai.prompts import SYSTEM_PROMPT, QUERY_SYSTEM_PROMPT, TARGETED_SYSTEM_PROMPT, MULTI_TURN_DQL_AGENT_PROMPT
from obsidianki.ai.tools import FLASHCARD_TOOL, DQL_EXECUTION_TOOL, FINALIZE_SELECTION_TOOL

AI_RESULT_SET_SIZE = 20

class FlashcardAI:
    def __init__(self):
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

        if not os.getenv("ANTHROPIC_API_KEY"):
            raise ValueError("ANTHROPIC_API_KEY not found in environment variables")
    
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

    def generate_flashcards(self, note: Note, target_cards: int, previous_fronts: list = [], deck_examples: list = []) -> List[Flashcard]:
        """Generate flashcards from a Note object using Claude"""

        card_instruction = self._build_card_instruction(target_cards)
        dedup_context = self._build_dedup_context(previous_fronts)
        schema_context = self._build_schema_context(deck_examples)
        difficulty_context = self._build_difficulty_context()

        user_prompt = f"""Note Title: {note.filename}

        Note Content:
        {note.content}{difficulty_context}{dedup_context}{schema_context}

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

            # Extract flashcards from tool call and convert to Flashcard objects
            if response.content and len(response.content) > 0:
                for content_block in response.content:
                    if content_block.type == "tool_use":
                        tool_input = cast(Dict[str, Any], content_block.input)
                        flashcard_dicts = tool_input['flashcards']

                        flashcard_objects = []
                        for card in flashcard_dicts:
                            front_original = card.get('front', '')
                            back_original = card.get('back', '')
                            front_processed = process_code_blocks(front_original, CONFIG.syntax_highlighting)
                            back_processed = process_code_blocks(back_original, CONFIG.syntax_highlighting)

                            flashcard = Flashcard(
                                front=front_processed,
                                back=back_processed,
                                note=note,
                                tags=card.get('tags', note.tags.copy()),
                                front_original=front_original,
                                back_original=back_original
                            )
                            flashcard_objects.append(flashcard)

                        return flashcard_objects

            console.print("[yellow]WARNING:[/yellow] No flashcards generated - unexpected response format")
            return []

        except Exception as e:
            console.print(f"[red]ERROR:[/red] Error generating flashcards: {e}")
            return []

    def generate_from_query(self, query: str, target_cards: int, previous_fronts: list = [], deck_examples: list = []) -> List[Flashcard]:
        """Generate flashcards based on a user query without source material"""

        card_instruction = self._build_card_instruction(target_cards)
        dedup_context = self._build_dedup_context(previous_fronts)
        schema_context = self._build_schema_context(deck_examples)
        difficulty_context = self._build_difficulty_context()

        user_prompt = f"""User Query: {query}

        Please {card_instruction} to help someone learn about this topic. Focus on the most important concepts, definitions, and practical information related to this query.{difficulty_context}{dedup_context}{schema_context}"""

        try:
            response = self.client.messages.create(
                model="claude-4-sonnet-20250514",
                max_tokens=8000,
                system=QUERY_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
                tools=[FLASHCARD_TOOL],
                tool_choice={"type": "tool", "name": "create_flashcards"}
            )

            # Extract flashcards from tool call and convert to Flashcard objects
            if response.content and len(response.content) > 0:
                for content_block in response.content:
                    if content_block.type == "tool_use":
                        tool_input = cast(Dict[str, Any], content_block.input)
                        flashcard_dicts = tool_input.get("flashcards", [])

                        # Create virtual Note object for query-based flashcards
                        virtual_note = Note(
                            path="query",
                            filename=f"Query: {query}",
                            content=query,
                            tags=["query-generated"],
                            size=0
                        )

                        flashcard_objects = []
                        for card in flashcard_dicts:
                            # Process the front and back content
                            front_original = card.get('front', '')
                            back_original = card.get('back', '')
                            front_processed = process_code_blocks(front_original, CONFIG.syntax_highlighting)
                            back_processed = process_code_blocks(back_original, CONFIG.syntax_highlighting)

                            # Create Flashcard object
                            flashcard = Flashcard(
                                front=front_processed,
                                back=back_processed,
                                note=virtual_note,
                                tags=card.get('tags', ["query-generated"]),
                                front_original=front_original,
                                back_original=back_original
                            )
                            flashcard_objects.append(flashcard)

                        return flashcard_objects

            console.print("[yellow]WARNING:[/yellow] No flashcards generated - unexpected response format")
            return []

        except Exception as e:
            console.print(f"[red]ERROR:[/red] Error generating flashcards from query: {e}")
            return []

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

        try:
            response = self.client.messages.create(
                model="claude-4-sonnet-20250514",
                max_tokens=8000,
                system=TARGETED_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
                tools=[FLASHCARD_TOOL],
                tool_choice={"type": "tool", "name": "create_flashcards"}
            )

            # Extract flashcards from tool call and convert to Flashcard objects
            if response.content and len(response.content) > 0:
                for content_block in response.content:
                    if content_block.type == "tool_use":
                        tool_input = cast(Dict[str, Any], content_block.input)
                        flashcard_dicts = tool_input.get("flashcards", [])

                        flashcard_objects = []
                        for card in flashcard_dicts:
                            # Process the front and back content
                            front_original = card.get('front', '')
                            back_original = card.get('back', '')
                            front_processed = process_code_blocks(front_original, CONFIG.syntax_highlighting)
                            back_processed = process_code_blocks(back_original, CONFIG.syntax_highlighting)

                            # Create Flashcard object
                            flashcard = Flashcard(
                                front=front_processed,
                                back=back_processed,
                                note=note,
                                tags=card.get('tags', note.tags.copy()),
                                front_original=front_original,
                                back_original=back_original
                            )
                            flashcard_objects.append(flashcard)

                        return flashcard_objects

            console.print("[yellow]WARNING:[/yellow] No flashcards generated - unexpected response format")
            return []

        except Exception as e:
            console.print(f"[red]ERROR:[/red] Error generating targeted flashcards: {e}")
            return []

    def find_with_agent(self, natural_request: str, sample_size: int | None = None, bias_strength: float | None = None) -> List[Note]:
        """Use multi-turn agent with tool calling to find notes via iterative DQL refinement"""
        from datetime import datetime
        today = datetime.now()
        date_context = f"\n\nToday's date is {today.strftime('%Y-%m-%d')}."

        # Add folder context
        folder_context = ""
        if CONFIG.search_folders:
            folder_context = f"\n\nIMPORTANT: Only search in these folders: {CONFIG.search_folders}. Add appropriate folder filtering to your WHERE clause using startswith(file.path, \"folder/\")."

        user_prompt = f"""Natural language request: {natural_request}{date_context}{folder_context}

        Find the most relevant notes for this request using DQL queries. Start with an initial query, analyze the results, and refine as needed."""

        # Multi-turn conversation with tool calling
        messages: List[MessageParam] = [{"role": "user", "content": user_prompt}]
        max_turns = 8
        selected_notes = []
        last_results = []  # Keep track of last query results
        all_results = {}  # Accumulate all results by path for validation
        has_dql_results = False  # Track if we've gotten at least one DQL result

        for _ in range(max_turns):
            try:
                tool_choice_param: ToolChoiceParam
                if not has_dql_results:
                    available_tools = [DQL_EXECUTION_TOOL]
                    tool_choice_param = {"type": "tool", "name": "execute_dql_query"}
                else:
                    available_tools = [DQL_EXECUTION_TOOL, FINALIZE_SELECTION_TOOL]
                    tool_choice_param = {"type": "any"}

                response = self.client.messages.create(
                    model="claude-4-sonnet-20250514",
                    max_tokens=3000,
                    system=MULTI_TURN_DQL_AGENT_PROMPT,
                    messages=messages,
                    tools=available_tools,
                    tool_choice=tool_choice_param
                )

                messages.append({"role": "assistant", "content": response.content})

                tool_results = []
                final_selection = None

                for content_block in response.content:
                    if content_block.type == "tool_use":
                        tool_name = content_block.name
                        tool_input = cast(Dict[str, Any], content_block.input)

                        if tool_name == "execute_dql_query":
                            dql_query = tool_input["query"]
                            reasoning = tool_input["reasoning"]

                            console.print(f"[cyan]Agent:[/cyan] {reasoning}")
                            console.print(f"[dim]Query:[/dim] {dql_query}")

                            try:
                                # Execute the DQL query
                                from obsidianki.cli.services import OBSIDIAN
                                results = OBSIDIAN.dql(dql_query)

                                if results is None:
                                    results = []

                                # Apply filtering (folders, excluded tags)
                                filtered_results = []
                                for result in results:
                                    note_path = result.path
                                    note_tags = result.tags or []

                                    # Apply search_folders filtering
                                    if CONFIG.search_folders:
                                        path_matches = any(note_path.startswith(f"{folder}/") for folder in CONFIG.search_folders)
                                        if not path_matches:
                                            continue

                                    # Apply excluded tags filtering
                                    excluded_tags = CONFIG.get_excluded_tags()
                                    if excluded_tags and any(tag in note_tags for tag in excluded_tags):
                                        continue

                                    filtered_results.append(result)

                                results = filtered_results

                                console.print(f"[cyan]Agent:[/cyan] Found {len(results)} notes")
                                last_results = results  # Store for potential auto-finalization
                                has_dql_results = True  # Mark that we now have DQL results

                                # Accumulate all results by path for validation
                                for result in results:
                                    # Handle Note objects directly
                                    if hasattr(result, 'path'):
                                        path = result.path
                                    else:
                                        # Fallback for dict format
                                        path = result.get('result', {}).get('path')
                                    if path:
                                        all_results[path] = result

                                # Prepare result summary for AI
                                if len(results) == 0:
                                    result_summary = "No notes found matching this query."
                                elif len(results) <= AI_RESULT_SET_SIZE:
                                    # Show detailed results for small result sets
                                    result_list = []
                                    for i, result in enumerate(results[:AI_RESULT_SET_SIZE]):
                                        # Handle Note objects directly
                                        if hasattr(result, 'path'):
                                            path = result.path
                                            name = result.filename
                                            tags = result.tags
                                            size = result.size
                                        else:
                                            # Fallback for dict format
                                            note = result.get('result', {})
                                            path = note.get('path', 'Unknown')
                                            name = note.get('name', 'Unknown')
                                            tags = note.get('tags', [])
                                            size = note.get('size', 0)
                                        result_list.append(f"{i+1}. {name} ({path}) - {size} chars, tags: {tags}")
                                    result_summary = f"Found {len(results)} notes:\n" + "\n".join(result_list)
                                else:
                                    # Show summary for large result sets
                                    result_summary = f"Found {len(results)} notes - this may be too many. Consider refining your query to be more specific."

                                tool_results.append({
                                    "tool_use_id": content_block.id,
                                    "content": result_summary
                                })

                            except Exception as e:
                                error_msg = f"DQL Error: {str(e)}"
                                console.print(f"[yellow]{error_msg}[/yellow]")
                                tool_results.append({
                                    "tool_use_id": content_block.id,
                                    "content": error_msg
                                })

                        elif tool_name == "finalize_note_selection":
                            selected_paths = tool_input["selected_paths"]
                            reasoning = tool_input["reasoning"]

                            console.print(f"[cyan]Agent:[/cyan] {reasoning}")
                            console.print(f"[cyan]Agent:[/cyan] Selected {len(selected_paths)} notes for processing")

                            final_selection = []
                            missing_paths = []
                            for path in selected_paths:
                                if path in all_results:
                                    final_selection.append(all_results[path])
                                else:
                                    missing_paths.append(path)

                            if missing_paths:
                                console.print(f"[yellow]Warning:[/yellow] Agent selected {len(missing_paths)} paths not found in query results: {missing_paths}")
                                console.print(f"[cyan]Agent:[/cyan] Proceeding with {len(final_selection)} valid selections")

                            tool_results.append({
                                "tool_use_id": content_block.id,
                                "content": f"Selection finalized: {len(final_selection)} notes will be processed."
                            })

                # Add tool results to conversation
                if tool_results:
                    for tool_result in tool_results:
                        messages.append({
                            "role": "user",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": tool_result["tool_use_id"],
                                    "content": tool_result["content"]
                                }
                            ]
                        })

                # If agent finalized selection, we're done
                if final_selection is not None:
                    selected_notes = final_selection
                    break

            except Exception as e:
                console.print(f"[red]ERROR:[/red] Agent conversation failed: {e}")
                return []

        if not selected_notes:
            # Force agent to finalize selection if it hasn't already
            if last_results:
                console.print(f"[cyan]Agent:[/cyan] Forcing finalization of {len(last_results)} available notes")

                try:
                    # Send final request forcing finalize_note_selection
                    response = self.client.messages.create(
                        model="claude-4-sonnet-20250514",
                        max_tokens=3000,
                        system=MULTI_TURN_DQL_AGENT_PROMPT,
                        messages=messages + [{"role": "user", "content": "Please finalize your note selection now using the finalize_note_selection tool."}],
                        tools=[FINALIZE_SELECTION_TOOL],
                        tool_choice={"type": "tool", "name": "finalize_note_selection"}
                    )

                    # Process the forced finalization
                    for content_block in response.content:
                        if content_block.type == "tool_use" and content_block.name == "finalize_note_selection":
                            tool_input = cast(Dict[str, Any], content_block.input)
                            selected_paths = tool_input["selected_paths"]
                            reasoning = tool_input["reasoning"]

                            console.print(f"[cyan]Agent:[/cyan] {reasoning}")
                            console.print(f"[cyan]Agent:[/cyan] Selected {len(selected_paths)} notes for processing")

                            # Find the corresponding note objects from all accumulated results
                            final_selection = []
                            missing_paths = []
                            for path in selected_paths:
                                if path in all_results:
                                    final_selection.append(all_results[path])
                                else:
                                    missing_paths.append(path)

                            # Warn about any missing paths
                            if missing_paths:
                                console.print(f"[yellow]Warning:[/yellow] Agent selected {len(missing_paths)} paths not found in query results: {missing_paths}")
                                console.print(f"[cyan]Agent:[/cyan] Proceeding with {len(final_selection)} valid selections")

                            selected_notes = final_selection
                            break

                except Exception as e:
                    console.print(f"[red]ERROR:[/red] Failed to force finalization: {e}")
                    return []

            if not selected_notes:
                console.print("[yellow]Agent could not finalize a selection[/yellow]")
                return []

        # Apply weighted sampling to final selection if needed
        target_count = sample_size if sample_size else len(selected_notes)
        if target_count < len(selected_notes):
            bias = bias_strength if bias_strength is not None else 1.0
            sampled_notes = OBSIDIAN._weighted_sample(selected_notes, target_count, bias)
        else:
            sampled_notes = selected_notes

        console.print()
        return sampled_notes

    def edit_cards(self, cards: List[Dict[str, str]], query: str) -> List[Dict[str, str]]:
        """Edit existing cards based on a query"""
        if not cards:
            return []

        # Build card context using original text (strip HTML for cleaner AI input)
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

        try:
            response = self.client.messages.create(
                model="claude-4-sonnet-20250514",
                max_tokens=4000,
                system=edit_system_prompt,
                messages=[
                    {"role": "user", "content": edit_prompt}
                ],
                tools=[FLASHCARD_TOOL],
                tool_choice={"type": "tool", "name": "create_flashcards"}
            )

            if not response.content:
                console.print("[yellow]WARNING:[/yellow] No response from AI for card editing")
                return cards

            edited_cards = []

            for content_block in response.content:
                if content_block.type == "tool_use" and content_block.name == "create_flashcards":
                    tool_input = cast(Dict[str, Any], content_block.input)
                    if "flashcards" in tool_input:
                        for flashcard_data in tool_input["flashcards"]:
                            if "front" in flashcard_data and "back" in flashcard_data:
                                # Store original text before processing
                                front_original = flashcard_data["front"]
                                back_original = flashcard_data["back"]

                                # Process code blocks like other flashcard generation
                                front_processed = process_code_blocks(front_original, CONFIG.syntax_highlighting)
                                back_processed = process_code_blocks(back_original, CONFIG.syntax_highlighting)

                                edited_cards.append({
                                    "front": front_processed,
                                    "back": back_processed,
                                    "front_original": front_original,
                                    "back_original": back_original,
                                    "origin": flashcard_data.get("origin", "")
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