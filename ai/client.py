import os
import re
from anthropic import Anthropic
from typing import List, Dict

from cli.config import console, SYNTAX_HIGHLIGHTING, SEARCH_FOLDERS
from cli.utils import process_code_blocks, strip_html
from ai.prompts import SYSTEM_PROMPT, QUERY_SYSTEM_PROMPT, TARGETED_SYSTEM_PROMPT, NOTE_RANKING_PROMPT, MULTI_TURN_DQL_AGENT_PROMPT
from ai.tools import FLASHCARD_TOOL, DQL_EXECUTION_TOOL, FINALIZE_SELECTION_TOOL

AI_RESULT_SET_SIZE = 20

class FlashcardAI:
    def __init__(self):
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

        if not os.getenv("ANTHROPIC_API_KEY"):
            raise ValueError("ANTHROPIC_API_KEY not found in environment variables")

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

    def generate_flashcards(self, note_content: str, note_title: str = "", target_cards: int = None, previous_fronts: list = None, deck_examples: list = None) -> List[Dict[str, str]]:
        """Generate flashcards from note content using Claude"""

        cards_to_create = target_cards if target_cards else 2
        card_instruction = f"Create approximately {cards_to_create} flashcards"

        # Add deduplication context if previous fronts exist
        dedup_context = ""
        if previous_fronts:
            previous_questions = "\n".join([f"- {front}" for front in previous_fronts])
            dedup_context = f"""

        IMPORTANT: We have previously created the following flashcards for this note:
        {previous_questions}

        DO NOT create flashcards that ask similar questions or cover the same concepts as the ones listed above. Focus on different aspects of the content."""

        schema_context = self._build_schema_context(deck_examples) if deck_examples else ""

        user_prompt = f"""Note Title: {note_title}

        Note Content:
        {note_content}{dedup_context}{schema_context}

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
                        flashcards = tool_input.get("flashcards", [])

                        for card in flashcards:
                            if 'front' in card:
                                card['front_original'] = card['front']  # Save original for terminal display
                                card['front'] = process_code_blocks(card['front'], SYNTAX_HIGHLIGHTING)
                            if 'back' in card:
                                card['back_original'] = card['back']  # Save original for terminal display
                                card['back'] = process_code_blocks(card['back'], SYNTAX_HIGHLIGHTING)
                        return flashcards

            console.print("[yellow]WARNING:[/yellow] No flashcards generated - unexpected response format")
            return []

        except Exception as e:
            console.print(f"[red]ERROR:[/red] Error generating flashcards: {e}")
            return []

    def generate_flashcards_from_query(self, query: str, target_cards: int = None, previous_fronts: list = None, deck_examples: list = None) -> List[Dict[str, str]]:
        """Generate flashcards based on a user query without source material"""

        cards_to_create = target_cards if target_cards else 3
        card_instruction = f"Create approximately {cards_to_create} flashcards"

        # Add deduplication context if previous fronts exist
        dedup_context = ""
        if previous_fronts:
            previous_questions = "\n".join([f"- {front}" for front in previous_fronts])
            dedup_context = f"""

        IMPORTANT: We have previously created the following flashcards for this deck:
        {previous_questions}

        Please ensure your new flashcards cover different aspects and don't duplicate these existing questions."""

        # Add schema context if deck examples provided
        schema_context = self._build_schema_context(deck_examples) if deck_examples else ""

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

            # Extract flashcards from tool call
            if response.content and len(response.content) > 0:
                for content_block in response.content:
                    if content_block.type == "tool_use":
                        tool_input = content_block.input
                        flashcards = tool_input.get("flashcards", [])
                        # Post-process code blocks
                        syntax_highlighting = SYNTAX_HIGHLIGHTING

                        for card in flashcards:
                            if 'front' in card:
                                card['front_original'] = card['front']  # Save original for terminal display
                                card['front'] = process_code_blocks(card['front'], syntax_highlighting)
                            if 'back' in card:
                                card['back_original'] = card['back']  # Save original for terminal display
                                card['back'] = process_code_blocks(card['back'], syntax_highlighting)
                        return flashcards

            console.print("[yellow]WARNING:[/yellow] No flashcards generated - unexpected response format")
            return []

        except Exception as e:
            console.print(f"[red]ERROR:[/red] Error generating flashcards from query: {e}")
            return []

    def generate_flashcards_from_note_and_query(self, note_content: str, note_title: str, query: str, target_cards: int = None, previous_fronts: list = None, deck_examples: list = None) -> List[Dict[str, str]]:
        """Generate flashcards by extracting specific information from a note based on a query"""

        cards_to_create = target_cards if target_cards else 2
        card_instruction = f"Create approximately {cards_to_create} flashcards"

        # Add deduplication context if previous fronts exist
        dedup_context = ""
        if previous_fronts:
            previous_questions = "\n".join([f"- {front}" for front in previous_fronts])
            dedup_context = f"""

            IMPORTANT: We have previously created the following flashcards for this note:
            {previous_questions}

            DO NOT create flashcards that ask similar questions or cover the same concepts as the ones listed above. Focus on different aspects of the content."""

            # Add schema context if deck examples provided
            schema_context = self._build_schema_context(deck_examples) if deck_examples else ""

            user_prompt = f"""Note Title: {note_title}
            Query: {query}

            Note Content:
            {note_content}{dedup_context}{schema_context}

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
                        flashcards = tool_input.get("flashcards", [])
                        # Post-process code blocks
                        syntax_highlighting = SYNTAX_HIGHLIGHTING

                        for card in flashcards:
                            if 'front' in card:
                                card['front_original'] = card['front']  # Save original for terminal display
                                card['front'] = process_code_blocks(card['front'], syntax_highlighting)
                            if 'back' in card:
                                card['back_original'] = card['back']  # Save original for terminal display
                                card['back'] = process_code_blocks(card['back'], syntax_highlighting)
                        return flashcards

            console.print("[yellow]WARNING:[/yellow] No flashcards generated - unexpected response format")
            return []

        except Exception as e:
            console.print(f"[red]ERROR:[/red] Error generating targeted flashcards: {e}")
            return []

    def find_notes_with_agent(self, natural_request: str, obsidian_api, config_manager=None, sample_size: int = None, bias_strength: float = None, search_folders=None) -> List[Dict]:
        """Use multi-turn agent with tool calling to find notes via iterative DQL refinement"""
        from datetime import datetime
        today = datetime.now()
        date_context = f"\n\nToday's date is {today.strftime('%Y-%m-%d')}."

        # Add folder context
        folder_context = ""
        effective_folders = search_folders if search_folders is not None else SEARCH_FOLDERS
        if effective_folders:
            folder_context = f"\n\nIMPORTANT: Only search in these folders: {effective_folders}. Add appropriate folder filtering to your WHERE clause using startswith(file.path, \"folder/\")."

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
                                results = obsidian_api.search_with_dql(dql_query)

                                if results is None:
                                    results = []

                                # Apply filtering (folders, excluded tags)
                                if config_manager:
                                    filtered_results = []
                                    for result in results:
                                        note_path = result['result'].get('path', '')

                                        # Apply SEARCH_FOLDERS filtering
                                        if effective_folders:
                                            path_matches = any(note_path.startswith(f"{folder}/") for folder in effective_folders)
                                            if not path_matches:
                                                continue

                                        # Apply excluded tags filtering
                                        note_tags = result['result'].get('tags', []) or []
                                        excluded_tags = config_manager.get_excluded_tags()
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
            sampled_notes = obsidian_api._weighted_sample(selected_notes, target_count, config_manager, bias_strength)
        else:
            sampled_notes = selected_notes

        console.print()
        return sampled_notes

