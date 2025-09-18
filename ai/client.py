import os
import re
from anthropic import Anthropic
from typing import List, Dict

from cli.config import console, SYNTAX_HIGHLIGHTING, SEARCH_FOLDERS
from cli.utils import process_code_blocks
from ai.prompts import SYSTEM_PROMPT, QUERY_SYSTEM_PROMPT, TARGETED_SYSTEM_PROMPT, NOTE_RANKING_PROMPT, MULTI_TURN_DQL_AGENT_PROMPT
from ai.tools import FLASHCARD_TOOL, DQL_EXECUTION_TOOL, FINALIZE_SELECTION_TOOL

class FlashcardAI:
    def __init__(self):
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

        if not os.getenv("ANTHROPIC_API_KEY"):
            raise ValueError("ANTHROPIC_API_KEY not found in environment variables")

    def _build_schema_context(self, deck_examples: List[Dict[str, str]]) -> str:
        """Build schema context from existing deck cards"""
        if not deck_examples:
            return ""

        schema_context = "\n\nIMPORTANT FORMATTING REQUIREMENTS:"
        schema_context += "\nYou MUST generate flashcards that strongly mirror the style and formatting of these existing cards from the deck:"
        schema_context += "\n\nEXISTING CARD EXAMPLES:"

        for i, example in enumerate(deck_examples, 1):
            schema_context += f"\n\nExample {i}:"
            schema_context += f"\nFront: {example['front']}"
            schema_context += f"\nBack: {example['back']}"

        schema_context += "\n\nYour new flashcards MUST follow the same:"
        schema_context += "\n- Question/answer structure and style"
        schema_context += "\n- Level of detail and complexity"
        schema_context += "\n- Formatting patterns (code blocks, emphasis, etc.)"
        schema_context += "\n- Length and conciseness"
        schema_context += "\nGenerate cards that would fit seamlessly with these examples."

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

        # Add schema context if deck examples provided
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

    def generate_dql_query(self, natural_request: str, search_folders=None, max_attempts: int = 3) -> str:
        """Generate DQL query from natural language with error correction"""

        for attempt in range(max_attempts):
            try:
                console.print(f"[cyan]Agent:[/cyan] Generating DQL query")

                from datetime import datetime
                today = datetime.now()

                date_context = f"""\n\nToday's date is {today.strftime('%Y-%m-%d')}."""

                user_prompt = f"""Natural language request: {natural_request}{date_context}

                Generate a DQL query that finds the requested notes."""

                response = self.client.messages.create(
                    model="claude-4-sonnet-20250514",
                    max_tokens=2000,
                    system=DQL_AGENT_PROMPT,
                    messages=[{"role": "user", "content": user_prompt}]
                )

                if response.content and len(response.content) > 0:
                    dql_query = response.content[0].text.strip()

                    # Clean up the query (remove markdown code blocks if present)
                    if "```" in dql_query:
                        dql_query = re.sub(r'```[a-zA-Z]*\n?', '', dql_query)
                        dql_query = dql_query.replace("```", "").strip()

                    console.print(f"[dim]Generated query:[/dim] {dql_query}")
                    return dql_query

            except Exception as e:
                console.print(f"[red]ERROR:[/red] Failed to generate DQL query (attempt {attempt + 1}): {e}")

        console.print(f"[red]ERROR:[/red] Failed to generate DQL query after {max_attempts} attempts")
        return None

    def rank_notes_by_relevance(self, natural_request: str, notes: List[Dict], target_count: int = None) -> List[str]:
        """Use AI to rank notes by relevance and return the most relevant note paths"""

        if not notes:
            return []

        # Prepare note metadata for AI ranking
        note_metadata = []
        for note in notes:
            result = note.get('result', {})
            metadata = {
                "path": result.get('path', ''),
                "filename": result.get('filename', ''),
                "tags": result.get('tags', []) or [],
                "mtime": result.get('mtime', ''),
                "size": result.get('size', 0)
            }
            note_metadata.append(metadata)

        # console.print(f"[cyan]Agent:[/cyan] Ranking {len(notes)} notes by relevance...")

        user_prompt = f"""Original request: {natural_request}

        Note list: {note_metadata}

        Select and rank the most relevant notes for this request. Return a JSON array of note paths."""

        try:
            response = self.client.messages.create(
                model="claude-4-sonnet-20250514",
                max_tokens=2000,
                system=NOTE_RANKING_PROMPT,
                messages=[{"role": "user", "content": user_prompt}]
            )

            if response.content and len(response.content) > 0:
                ranking_text = response.content[0].text.strip()

                # Extract JSON array from response
                try:
                    import json
                    # Try to parse as JSON directly
                    if ranking_text.startswith('['):
                        ranked_paths = json.loads(ranking_text)
                    else:
                        # Extract JSON from response if it's wrapped in text
                        import re
                        json_match = re.search(r'\[.*?\]', ranking_text, re.DOTALL)
                        if json_match:
                            ranked_paths = json.loads(json_match.group(0))
                        else:
                            raise ValueError("No JSON array found in response")

                    # Apply target count if specified
                    if target_count and len(ranked_paths) > target_count:
                        ranked_paths = ranked_paths[:target_count]

                    console.print(f"[green]Agent:[/green] Selected {len(ranked_paths)} most relevant notes")
                    return ranked_paths

                except json.JSONDecodeError as e:
                    console.print(f"[yellow]Warning:[/yellow] Failed to parse AI ranking: {e}")
                    # Fallback: return all note paths
                    return [note['result'].get('path', '') for note in notes[:target_count] if note['result'].get('path')]

        except Exception as e:
            console.print(f"[yellow]Warning:[/yellow] Error ranking notes: {e}")
            # Fallback: return all note paths
            return [note['result'].get('path', '') for note in notes[:target_count] if note['result'].get('path')]

    def find_notes_with_agent(self, natural_request: str, obsidian_api, config_manager=None, sample_size: int = None, bias_strength: float = None, search_folders=None) -> List[Dict]:
        """Use multi-turn agent with tool calling to find notes via iterative DQL refinement"""

        console.print(f"[cyan]Agent:[/cyan] Starting multi-turn note discovery...")

        # Add current date context
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
        max_turns = 8  # Increased to allow more refinement
        selected_notes = []
        last_results = []  # Keep track of last query results

        for turn in range(max_turns):
            try:
                response = self.client.messages.create(
                    model="claude-4-sonnet-20250514",
                    max_tokens=3000,
                    system=MULTI_TURN_DQL_AGENT_PROMPT,
                    messages=messages,
                    tools=[DQL_EXECUTION_TOOL, FINALIZE_SELECTION_TOOL]
                )

                # Add assistant response to conversation
                messages.append({"role": "assistant", "content": response.content})

                # Process tool calls
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

                                # Prepare result summary for AI
                                if len(results) == 0:
                                    result_summary = "No notes found matching this query."
                                elif len(results) <= 20:
                                    # Show detailed results for small result sets
                                    result_list = []
                                    for i, result in enumerate(results[:20]):
                                        note = result['result']
                                        path = note.get('path', 'Unknown')
                                        name = note.get('name', 'Unknown')
                                        tags = note.get('tags', [])
                                        size = note.get('size', 0)
                                        result_list.append(f"{i+1}. {name} ({path}) - {size} chars, tags: {tags}")
                                    result_summary = f"Found {len(results)} notes:\n" + "\n".join(result_list)

                                    # Encourage finalization for good result sets
                                    if len(results) <= 15:
                                        result_summary += "\n\nThis looks like a good set of results! Consider finalizing your selection if these notes match the request well."
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

                            # Find the corresponding note objects
                            final_selection = []
                            for path in selected_paths:
                                for result in results:  # Use results from last query
                                    if result['result'].get('path') == path:
                                        final_selection.append(result)
                                        break

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
            # If agent didn't finalize but we have good results from last query, use them
            if last_results and len(last_results) <= 25:
                console.print(f"[yellow]Agent reached turn limit, auto-selecting {len(last_results)} notes from last query[/yellow]")
                selected_notes = last_results
            else:
                console.print("[yellow]Agent did not finalize a selection and no suitable results available[/yellow]")
                return []

        # Apply weighted sampling to final selection if needed
        target_count = sample_size if sample_size else len(selected_notes)
        if target_count < len(selected_notes):
            sampled_notes = obsidian_api._weighted_sample(selected_notes, target_count, config_manager, bias_strength)
        else:
            sampled_notes = selected_notes

        console.print()
        return sampled_notes

