import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from anthropic import Anthropic
from typing import List, Dict, Tuple, Optional

from cli.config import console, SYNTAX_HIGHLIGHTING, SEARCH_FOLDERS, CONFIG_MANAGER
from cli.utils import process_code_blocks, strip_html
from cli.models import Note, Flashcard
from ai.prompts import SYSTEM_PROMPT, QUERY_SYSTEM_PROMPT, TARGETED_SYSTEM_PROMPT, NOTE_RANKING_PROMPT, MULTI_TURN_DQL_AGENT_PROMPT
from ai.tools import FLASHCARD_TOOL, DQL_EXECUTION_TOOL, FINALIZE_SELECTION_TOOL

AI_RESULT_SET_SIZE = 20

class FlashcardAI:
    def __init__(self):
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

        if not os.getenv("ANTHROPIC_API_KEY"):
            raise ValueError("ANTHROPIC_API_KEY not found in environment variables")
    
    def _build_card_instruction(self, target_cards: int) -> str:
        return f"create approximately {target_cards} flashcards"
    
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
            return "None"

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

    def generate_flashcards(self, note: Note, target_cards: int, previous_fronts: list = None, deck_examples: list = None) -> List[Flashcard]:
        """Generate flashcards from a Note object using Claude"""

        card_instruction = self._build_card_instruction(target_cards)
        dedup_context = self._build_dedup_context(previous_fronts)
        schema_context = self._build_schema_context(deck_examples)

        user_prompt = f"""Note Title: {note.filename}

        Note Content:
        {note.content}{dedup_context}{schema_context}

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
                        tool_input = content_block.input
                        flashcard_dicts = tool_input.get("flashcards", [])

                        flashcard_objects = []
                        for card in flashcard_dicts:
                            front_original = card.get('front', '')
                            back_original = card.get('back', '')
                            front_processed = process_code_blocks(front_original, SYNTAX_HIGHLIGHTING)
                            back_processed = process_code_blocks(back_original, SYNTAX_HIGHLIGHTING)

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

    def generate_from_query(self, query: str, target_cards: int, previous_fronts: list = None, deck_examples: list = None) -> List[Flashcard]:
        """Generate flashcards based on a user query without source material"""

        card_instruction = self._build_card_instruction(target_cards)
        dedup_context = self._build_dedup_context(previous_fronts)
        schema_context = self._build_schema_context(deck_examples)

        user_prompt = f"""User Query: {query}

        Please {card_instruction} to help someone learn about this topic. Focus on the most important concepts, definitions, and practical information related to this query.{dedup_context}{schema_context}"""

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
                        tool_input = content_block.input
                        flashcard_dicts = tool_input.get("flashcards", [])

                        # Create virtual Note object for query-based flashcards
                        virtual_note = Note(
                            path="query",
                            filename=f"Query: {query}",
                            content=query,
                            tags=["query-generated"]
                        )

                        flashcard_objects = []
                        for card in flashcard_dicts:
                            # Process the front and back content
                            front_original = card.get('front', '')
                            back_original = card.get('back', '')
                            front_processed = process_code_blocks(front_original, SYNTAX_HIGHLIGHTING)
                            back_processed = process_code_blocks(back_original, SYNTAX_HIGHLIGHTING)

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

    def generate_from_note_query(self, note: Note, query: str, target_cards: int, previous_fronts: list = None, deck_examples: list = None) -> List[Flashcard]:
        """Generate flashcards by extracting specific information from a note based on a query"""

        card_instruction = self._build_card_instruction(target_cards)
        dedup_context = self._build_dedup_context(previous_fronts)
        schema_context = self._build_schema_context(deck_examples)

        user_prompt = f"""Note Title: {note.filename}
        Query: {query}

        Note Content:
        {note.content}{dedup_context}{schema_context}

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
                        tool_input = content_block.input
                        flashcard_dicts = tool_input.get("flashcards", [])

                        flashcard_objects = []
                        for card in flashcard_dicts:
                            # Process the front and back content
                            front_original = card.get('front', '')
                            back_original = card.get('back', '')
                            front_processed = process_code_blocks(front_original, SYNTAX_HIGHLIGHTING)
                            back_processed = process_code_blocks(back_original, SYNTAX_HIGHLIGHTING)

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

    def find_with_agent(self, natural_request: str, sample_size: int = None, bias_strength: float = None) -> List[Note]:
        """Use multi-turn agent with tool calling to find notes via iterative DQL refinement"""
        from datetime import datetime
        today = datetime.now()
        date_context = f"\n\nToday's date is {today.strftime('%Y-%m-%d')}."

        # Add folder context
        folder_context = ""
        if SEARCH_FOLDERS:
            folder_context = f"\n\nIMPORTANT: Only search in these folders: {SEARCH_FOLDERS}. Add appropriate folder filtering to your WHERE clause using startswith(file.path, \"folder/\")."

        user_prompt = f"""Natural language request: {natural_request}{date_context}{folder_context}

        Find the most relevant notes for this request using DQL queries. Start with an initial query, analyze the results, and refine as needed."""

        # Multi-turn conversation with tool calling
        messages = [{"role": "user", "content": user_prompt}]
        max_turns = 8
        selected_notes = []
        last_results = []  # Keep track of last query results
        all_results = {}  # Accumulate all results by path for validation
        has_dql_results = False  # Track if we've gotten at least one DQL result

        for turn in range(max_turns):
            try:
                if not has_dql_results:
                    available_tools = [DQL_EXECUTION_TOOL]
                    tool_choice = {"type": "tool", "name": "execute_dql_query"}
                else:
                    available_tools = [DQL_EXECUTION_TOOL, FINALIZE_SELECTION_TOOL]
                    tool_choice = {"type": "any"}

                response = self.client.messages.create(
                    model="claude-4-sonnet-20250514",
                    max_tokens=3000,
                    system=MULTI_TURN_DQL_AGENT_PROMPT,
                    messages=messages,
                    tools=available_tools,
                    tool_choice=tool_choice
                )

                messages.append({"role": "assistant", "content": response.content})

                tool_results = []
                final_selection = None

                for content_block in response.content:
                    if content_block.type == "tool_use":
                        tool_name = content_block.name
                        tool_input = content_block.input

                        if tool_name == "execute_dql_query":
                            dql_query = tool_input["query"]
                            reasoning = tool_input["reasoning"]

                            console.print(f"[cyan]Agent:[/cyan] {reasoning}")
                            console.print(f"[dim]Query:[/dim] {dql_query}")

                            try:
                                # Execute the DQL query
                                from cli.services import OBSIDIAN
                                results = OBSIDIAN.dql(dql_query)

                                if results is None:
                                    results = []

                                # Apply filtering (folders, excluded tags)
                                filtered_results = []
                                for result in results:
                                    note_path = result['result'].get('path', '')

                                    # Apply SEARCH_FOLDERS filtering
                                    if SEARCH_FOLDERS:
                                        path_matches = any(note_path.startswith(f"{folder}/") for folder in SEARCH_FOLDERS)
                                        if not path_matches:
                                            continue

                                    # Apply excluded tags filtering
                                    note_tags = result['result'].get('tags', []) or []
                                    excluded_tags = CONFIG_MANAGER.get_excluded_tags()
                                    if excluded_tags and any(tag in note_tags for tag in excluded_tags):
                                        continue

                                    filtered_results.append(result)

                                results = filtered_results

                                console.print(f"[cyan]Agent:[/cyan] Found {len(results)} notes")
                                last_results = results  # Store for potential auto-finalization
                                has_dql_results = True  # Mark that we now have DQL results

                                # Accumulate all results by path for validation
                                for result in results:
                                    path = result['result'].get('path')
                                    if path:
                                        all_results[path] = result

                                # Prepare result summary for AI
                                if len(results) == 0:
                                    result_summary = "No notes found matching this query."
                                elif len(results) <= AI_RESULT_SET_SIZE:
                                    # Show detailed results for small result sets
                                    result_list = []
                                    for i, result in enumerate(results[:AI_RESULT_SET_SIZE]):
                                        note = result['result']
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
                            tool_input = content_block.input
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
            sampled_notes = OBSIDIAN._weighted_sample(selected_notes, target_count, bias_strength)
        else:
            sampled_notes = selected_notes

        console.print()
        return sampled_notes

    def generate_batch(self, note_batch: List[Tuple[str, str]], target_cards_per_note: int = None,
                      previous_fronts_batch: List[List[str]] = None,
                      deck_examples: List[Dict[str, str]] = None,
                      query: str = None) -> List[List[Dict[str, str]]]:
        """Generate flashcards for multiple notes in parallel"""

        def generate_single_note(args):
            """Helper function for parallel processing"""
            note_content, note_title, previous_fronts, index = args

            try:
                if query:
                    return self.generate_from_note_query(
                        note_content, note_title, query,
                        target_cards=target_cards_per_note,
                        previous_fronts=previous_fronts,
                        deck_examples=deck_examples
                    )
                else:
                    return self.generate_flashcards(
                        note_content, note_title,
                        target_cards=target_cards_per_note,
                        previous_fronts=previous_fronts,
                        deck_examples=deck_examples
                    )
            except Exception as e:
                console.print(f"[yellow]WARNING:[/yellow] Failed to generate cards for note {index + 1}: {e}")
                return []

        previous_fronts_batch = previous_fronts_batch or [[] for _ in note_batch]
        args_list = [
            (content, title, previous_fronts, i)
            for i, ((content, title), previous_fronts) in enumerate(zip(note_batch, previous_fronts_batch))
        ]

        with ThreadPoolExecutor(max_workers=min(5, len(note_batch))) as executor:
            future_to_index = {executor.submit(generate_single_note, args): i for i, args in enumerate(args_list)}

            completed_results = [None] * len(note_batch)

            for future in as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    result = future.result()
                    completed_results[index] = result
                except Exception as e:
                    console.print(f"[red]ERROR:[/red] Note {index + 1} failed: {e}")
                    completed_results[index] = []
                    
        return completed_results