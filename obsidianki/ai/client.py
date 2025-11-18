import os
from typing import List, Dict
import litellm
from litellm import completion

from obsidianki.cli.config import console, CONFIG
from obsidianki.cli.utils import process_code_blocks, strip_html
from obsidianki.cli.models import Note, Flashcard
from obsidianki.ai.models import MODEL_MAP
from obsidianki.ai.prompts import SYSTEM_PROMPT, QUERY_SYSTEM_PROMPT, TARGETED_SYSTEM_PROMPT, MULTI_TURN_DQL_AGENT_PROMPT
from obsidianki.ai.tools import FLASHCARD_TOOL, DQL_EXECUTION_TOOL, FINALIZE_SELECTION_TOOL

AI_RESULT_SET_SIZE = 20

# Suppress litellm logging
litellm.suppress_debug_info = True

class FlashcardAI:
    def __init__(self):
        # Get model name from config
        model_name = getattr(CONFIG, 'model', 'Claude Sonnet 4')

        model_info = MODEL_MAP[model_name]
        self.provider = model_info["provider"]
        self.model = model_info["model"]

        # Backwards compatibility: if ANTHROPIC_API_KEY exists but no config, use anthropic
        if os.getenv("ANTHROPIC_API_KEY") and not os.getenv("OPENAI_API_KEY"):
            self.provider = 'anthropic'
            if self.model == 'claude-sonnet-4-20250514' or not hasattr(CONFIG, 'model'):
                self.model = 'claude-sonnet-4-20250514'

        self._validate_api_key()

    def _validate_api_key(self):
        """Ensure appropriate API key is available for selected provider"""
        key_map = {
            'anthropic': 'ANTHROPIC_API_KEY',
            'openai': 'OPENAI_API_KEY',
            'google': 'GOOGLE_API_KEY',
            'azure': 'AZURE_API_KEY',
            'groq': 'GROQ_API_KEY',
            'cohere': 'COHERE_API_KEY',
            'together': 'TOGETHER_API_KEY',
            'mistral': 'MISTRAL_API_KEY',
        }

        required_key = key_map.get(self.provider, f"{self.provider.upper()}_API_KEY")

        if not os.getenv(required_key):
            # Check for generic LLM_API_KEY fallback
            if not os.getenv("LLM_API_KEY"):
                raise ValueError(f"{required_key} not found in environment variables")

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

    def _call_llm(self, system_prompt: str, user_prompt: str, tools: List[Dict], tool_choice: Dict, max_tokens: int = 8000):
        """Unified LLM call using litellm"""
        try:
            response = completion(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                tools=tools,
                tool_choice=tool_choice,
                max_tokens=max_tokens
            )
            return response
        except Exception as e:
            console.print(f"[red]ERROR:[/red] LLM call failed: {e}")
            return None

    def generate_flashcards(self, note: Note, target_cards: int, previous_fronts: list = [], deck_examples: list = []) -> List[Flashcard]:
        """Generate flashcards from a Note object using LLM"""

        card_instruction = self._build_card_instruction(target_cards)
        dedup_context = self._build_dedup_context(previous_fronts)
        schema_context = self._build_schema_context(deck_examples)
        difficulty_context = self._build_difficulty_context()

        user_prompt = f"""Note Title: {note.filename}

        Note Content:
        {note.content}{difficulty_context}{dedup_context}{schema_context}

        Please analyze this note and {card_instruction} for the key information that would be valuable for spaced repetition learning."""

        response = self._call_llm(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            tools=[FLASHCARD_TOOL],
            tool_choice={"type": "function", "function": {"name": "create_flashcards"}}
        )

        if not response:
            return []

        # Extract flashcards from tool call
        try:
            message = response.choices[0].message
            if hasattr(message, 'tool_calls') and message.tool_calls:
                tool_call = message.tool_calls[0]
                import json
                arguments = json.loads(tool_call.function.arguments)

                # Gemini sometimes returns empty arguments - check for this
                if not arguments or 'flashcards' not in arguments:
                    console.print(f"[yellow]WARNING:[/yellow] Model returned empty or invalid tool arguments: {arguments}")
                    console.print(f"[yellow]This is a known issue with some Gemini models. Try using a different model.[/yellow]")
                    return []

                flashcard_dicts = arguments['flashcards']

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
        except Exception as e:
            print(response)
            console.print(f"[red]ERROR:[/red] Failed to parse flashcards: {e}")
            return []

        console.print("[yellow]WARNING:[/yellow] No flashcards generated - unexpected response format")
        return []

    def generate_from_query(self, query: str, target_cards: int, previous_fronts: list = [], deck_examples: list = []) -> List[Flashcard]:
        """Generate flashcards based on a user query without source material"""

        card_instruction = self._build_card_instruction(target_cards)
        dedup_context = self._build_dedup_context(previous_fronts)
        schema_context = self._build_schema_context(deck_examples)
        difficulty_context = self._build_difficulty_context()

        user_prompt = f"""User Query: {query}

        Please {card_instruction} to help someone learn about this topic. Focus on the most important concepts, definitions, and practical information related to this query.{difficulty_context}{dedup_context}{schema_context}"""

        response = self._call_llm(
            system_prompt=QUERY_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            tools=[FLASHCARD_TOOL],
            tool_choice={"type": "function", "function": {"name": "create_flashcards"}}
        )

        if not response:
            return []

        # Extract flashcards
        try:
            message = response.choices[0].message
            if hasattr(message, 'tool_calls') and message.tool_calls:
                tool_call = message.tool_calls[0]
                import json
                flashcard_dicts = json.loads(tool_call.function.arguments).get("flashcards", [])

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
                    front_original = card.get('front', '')
                    back_original = card.get('back', '')
                    front_processed = process_code_blocks(front_original, CONFIG.syntax_highlighting)
                    back_processed = process_code_blocks(back_original, CONFIG.syntax_highlighting)

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
        except Exception as e:
            console.print(f"[red]ERROR:[/red] Failed to parse flashcards: {e}")
            return []

        console.print("[yellow]WARNING:[/yellow] No flashcards generated - unexpected response format")
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

        response = self._call_llm(
            system_prompt=TARGETED_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            tools=[FLASHCARD_TOOL],
            tool_choice={"type": "function", "function": {"name": "create_flashcards"}}
        )

        if not response:
            return []

        # Extract flashcards
        try:
            message = response.choices[0].message
            if hasattr(message, 'tool_calls') and message.tool_calls:
                tool_call = message.tool_calls[0]
                import json
                flashcard_dicts = json.loads(tool_call.function.arguments).get("flashcards", [])

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
        except Exception as e:
            console.print(f"[red]ERROR:[/red] Failed to parse flashcards: {e}")
            return []

        console.print("[yellow]WARNING:[/yellow] No flashcards generated - unexpected response format")
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
        messages = [
            {"role": "system", "content": MULTI_TURN_DQL_AGENT_PROMPT},
            {"role": "user", "content": user_prompt}
        ]
        max_turns = 8
        selected_notes = []
        last_results = []
        all_results = {}
        has_dql_results = False

        for turn in range(max_turns):
            try:
                # Determine available tools
                if not has_dql_results:
                    available_tools = [DQL_EXECUTION_TOOL]
                    tool_choice = {"type": "function", "function": {"name": "execute_dql_query"}}
                else:
                    available_tools = [DQL_EXECUTION_TOOL, FINALIZE_SELECTION_TOOL]
                    tool_choice = {"type": "auto"}

                response = completion(
                    model=self.model,
                    messages=messages,
                    tools=available_tools,
                    tool_choice=tool_choice,
                    max_tokens=3000
                )

                message = response.choices[0].message
                messages.append({"role": "assistant", "content": message.content or "", "tool_calls": message.tool_calls if hasattr(message, 'tool_calls') else None})

                tool_results = []
                final_selection = None

                if hasattr(message, 'tool_calls') and message.tool_calls:
                    for tool_call in message.tool_calls:
                        tool_name = tool_call.function.name
                        import json
                        tool_input = json.loads(tool_call.function.arguments)

                        if tool_name == "execute_dql_query":
                            dql_query = tool_input["query"]
                            reasoning = tool_input.get("reasoning", "")

                            console.print(f"[cyan]Agent:[/cyan] {reasoning}")
                            console.print(f"[dim]Query:[/dim] {dql_query}")

                            try:
                                from obsidianki.cli.services import OBSIDIAN
                                results = OBSIDIAN.dql(dql_query)

                                if results is None:
                                    results = []

                                # Apply filtering
                                filtered_results = []
                                for result in results:
                                    note_path = result.path
                                    note_tags = result.tags or []

                                    if CONFIG.search_folders:
                                        path_matches = any(note_path.startswith(f"{folder}/") for folder in CONFIG.search_folders)
                                        if not path_matches:
                                            continue

                                    excluded_tags = CONFIG.get_excluded_tags()
                                    if excluded_tags and any(tag in note_tags for tag in excluded_tags):
                                        continue

                                    filtered_results.append(result)

                                results = filtered_results

                                console.print(f"[cyan]Agent:[/cyan] Found {len(results)} notes")
                                last_results = results
                                has_dql_results = True

                                for result in results:
                                    path = result.path if hasattr(result, 'path') else result.get('result', {}).get('path')
                                    if path:
                                        all_results[path] = result

                                # Prepare result summary
                                if len(results) == 0:
                                    result_summary = "No notes found matching this query."
                                elif len(results) <= AI_RESULT_SET_SIZE:
                                    result_list = []
                                    for i, result in enumerate(results[:AI_RESULT_SET_SIZE]):
                                        path = result.path if hasattr(result, 'path') else result.get('result', {}).get('path', 'Unknown')
                                        name = result.filename if hasattr(result, 'filename') else result.get('result', {}).get('name', 'Unknown')
                                        tags = result.tags if hasattr(result, 'tags') else result.get('result', {}).get('tags', [])
                                        size = result.size if hasattr(result, 'size') else result.get('result', {}).get('size', 0)
                                        result_list.append(f"{i+1}. {name} ({path}) - {size} chars, tags: {tags}")
                                    result_summary = f"Found {len(results)} notes:\n" + "\n".join(result_list)
                                else:
                                    result_summary = f"Found {len(results)} notes - this may be too many. Consider refining your query to be more specific."

                                tool_results.append({
                                    "tool_call_id": tool_call.id,
                                    "role": "tool",
                                    "name": tool_name,
                                    "content": result_summary
                                })

                            except Exception as e:
                                error_msg = f"DQL Error: {str(e)}"
                                console.print(f"[yellow]{error_msg}[/yellow]")
                                tool_results.append({
                                    "tool_call_id": tool_call.id,
                                    "role": "tool",
                                    "name": tool_name,
                                    "content": error_msg
                                })

                        elif tool_name == "finalize_note_selection":
                            selected_paths = tool_input["selected_paths"]
                            reasoning = tool_input.get("reasoning", "")

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
                                "tool_call_id": tool_call.id,
                                "role": "tool",
                                "name": tool_name,
                                "content": f"Selection finalized: {len(final_selection)} notes will be processed."
                            })

                # Add tool results to conversation
                if tool_results:
                    messages.extend(tool_results)

                # If agent finalized selection, we're done
                if final_selection is not None:
                    selected_notes = final_selection
                    break

            except Exception as e:
                console.print(f"[red]ERROR:[/red] Agent conversation failed: {e}")
                return []

        # Force finalization if needed
        if not selected_notes and last_results:
            console.print(f"[cyan]Agent:[/cyan] Forcing finalization of {len(last_results)} available notes")
            selected_notes = last_results

        if not selected_notes:
            console.print("[yellow]Agent could not finalize a selection[/yellow]")
            return []

        # Apply sampling if needed
        target_count = sample_size if sample_size else len(selected_notes)
        if target_count < len(selected_notes):
            from obsidianki.cli.services import OBSIDIAN
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
            tool_choice={"type": "function", "function": {"name": "create_flashcards"}},
            max_tokens=4000
        )

        if not response:
            return cards

        try:
            message = response.choices[0].message
            if hasattr(message, 'tool_calls') and message.tool_calls:
                tool_call = message.tool_calls[0]
                import json
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
