import os
import re
from anthropic import Anthropic
from typing import List, Dict
from config import console, SYNTAX_HIGHLIGHTING, SEARCH_FOLDERS

def process_code_blocks(text: str, enable_syntax_highlighting: bool = True) -> str:
    """Convert markdown code blocks to HTML, optionally with syntax highlighting"""
    if not enable_syntax_highlighting:
        # Simple conversion without syntax highlighting
        text = re.sub(r'```([^`]+)```', r'<code>\1</code>', text)
        return text

    try:
        from pygments import highlight
        from pygments.lexers import get_lexer_by_name, ClassNotFound
        from pygments.formatters import HtmlFormatter

        def replace_code_block(match):
            full_content = match.group(1)
            lines = full_content.split('\n')

            # Check if first line is a language identifier
            if lines and lines[0].strip() and not ' ' in lines[0].strip():
                language = lines[0].strip()
                code_content = '\n'.join(lines[1:])
            else:
                language = 'text'
                code_content = full_content

            try:
                lexer = get_lexer_by_name(language)
                formatter = HtmlFormatter(
                    style='monokai',
                    noclasses=True,
                    cssclass='highlight'
                )
                highlighted = highlight(code_content, lexer, formatter)
                return highlighted
            except ClassNotFound:
                # Fallback to simple code tag if language not found
                return f'<code>{code_content}</code>'

        # Replace triple backticks with syntax highlighted HTML
        text = re.sub(r'```([^`]+)```', replace_code_block, text, flags=re.DOTALL)
        return text

    except ImportError:
        # Fallback to simple code tags if Pygments not available
        text = re.sub(r'```([^`]+)```', r'<code>\1</code>', text)
        return text

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
6. Create the number of flashcards requested in the prompt
7. For code-related content, ALWAYS include actual code examples
8. Use markdown code blocks with triple backticks for code formatting

GOOD FLASHCARD EXAMPLES:
- Front: "What is the primary function of mitochondria?" Back: "Generate ATP (energy) for cellular processes"
- Front: "Who developed the concept of 'deliberate practice'?" Back: "Anders Ericsson"
- Front: "What are the three pillars of observability?" Back: "Metrics, logs, and traces"
- Front: "How do you create a list in Python?" Back: "Use square brackets: ```my_list = [1, 2, 3]```"
- Front: "What's the syntax for a JavaScript arrow function?" Back: "```const func = (param) => { return param * 2; }```"

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
5. Create the number of flashcards requested in the prompt
6. For code-related queries, ALWAYS include actual code examples
7. Use markdown code blocks with triple backticks for code formatting

GOOD QUERY FLASHCARD EXAMPLES:
Query: "how to center a div"
- Front: "What CSS properties center a div horizontally using flexbox?" Back: "```display: flex; justify-content: center;```"
- Front: "What CSS technique centers a div both horizontally and vertically?" Back: "```display: flex; justify-content: center; align-items: center;```"

Query: "React fragments"
- Front: "What is a React Fragment used for?" Back: "Grouping multiple elements without adding extra DOM nodes"
- Front: "What are the two ways to write React Fragments?" Back: "```<React.Fragment>``` or shorthand ```<>```"

Query: "Python list comprehension"
- Front: "How do you create a list of squares using list comprehension?" Back: "```[x**2 for x in range(10)]```"
- Front: "What's the syntax for conditional list comprehension?" Back: "```[x for x in list if condition]```"

Generate educational flashcards based on the user's query using the create_flashcards tool."""

# System prompt for targeted extraction from notes
TARGETED_SYSTEM_PROMPT = """You are an expert at extracting specific information from notes to create targeted flashcards. Your job is to analyze the provided note content and create flashcards that specifically address the user's query within the context of that note.

TARGETED EXTRACTION GUIDELINES:
1. Focus ONLY on information in the note that relates to the user's query
2. Extract specific examples, syntax, or concepts that answer the query
3. If the note doesn't contain relevant information, create fewer or no cards
4. Prioritize practical, actionable information over theory
5. Create the number of flashcards requested in the prompt

GOOD TARGETED EXTRACTION EXAMPLES:
Query: "syntax for fragments" + React note content
- Extract specific React Fragment syntax examples from the note
- Focus on practical usage patterns mentioned in the note

Query: "error handling" + JavaScript note content
- Extract specific error handling patterns from the note
- Focus on try-catch examples or error handling strategies mentioned

Analyze the note content and extract information specifically related to the user's query using the create_flashcards tool."""

# DQL Agent System Prompt
DQL_AGENT_PROMPT = """You are an expert at writing Dataview DQL queries for Obsidian vaults. Your job is to translate natural language requests into precise DQL queries that find relevant notes.

KEY DQL CAPABILITIES:
- **Property filtering**: `file.property = value`, `property.field > 5`, `length(attempts) = 0`
- **Tag filtering**: `contains(file.tags, "#tag")`, `contains(tags, "#obj/leetcode")`
- **Date filtering**: `file.mtime > date("2024-08-01")`, `file.ctime < date("2024-12-01")`
- **Content search**: `contains(file.name, "text")`, `contains(content, "keyword")`
- **Size filtering**: `file.size > 1000`, `file.size < 50000`
- **Array operations**: `length(attempts) > 0`, `contains(attempts, "2024-08-15")`
- **Sorting**: `SORT file.mtime ASC`, `SORT difficulty DESC`, `SORT file.name ASC`
- **Regex**: Use `regexmatch(field, "pattern")` for pattern matching

QUERY STRUCTURE:
```
TABLE
    file.name AS "filename",
    file.path AS "path",
    file.mtime AS "mtime",
    file.size AS "size",
    file.tags AS "tags"
    FROM ""
    WHERE [conditions]
    SORT [field] [ASC|DESC]
```

IMPORTANT RULES:
1. Always include the exact TABLE structure shown above
2. Use double quotes for strings: `"React"`, `"#leetcode"`
3. Use date() function for date comparisons: `date("2024-08-01")`
4. Property access: `difficulty` for frontmatter properties
5. Array length: `length(property_array)`
6. Multiple conditions: Use AND/OR with parentheses
7. Case sensitive: file names and tags are case sensitive

THIS IS DQL (Dataview Query Language), so only use functions that are supported by DQL.

EXAMPLE QUERIES:

Natural: "find React notes from last month"
DQL:
```
TABLE
    file.name AS "filename",
    file.path AS "path",
    file.mtime AS "mtime",
    file.size AS "size",
    file.tags AS "tags"
    FROM ""
    WHERE contains(file.name, "React") AND file.mtime > date("2024-08-01")
    SORT file.mtime DESC
```

Natural: "leetcode problems with difficulty 7 or below, not attempted in 2 months"
DQL:
```
TABLE
    file.name AS "filename",
    file.path AS "path",
    file.mtime AS "mtime",
    file.size AS "size",
    file.tags AS "tags"
    FROM ""
    WHERE contains(file.tags, "#obj/leetcode")
    AND difficulty <= 7
    AND (length(attempts) = 0 OR file.mtime < date("2024-07-16"))
    SORT difficulty ASC
```

Natural: "machine learning notes with math tag, larger files"
DQL:
```
TABLE
    file.name AS "filename",
    file.path AS "path",
    file.mtime AS "mtime",
    file.size AS "size",
    file.tags AS "tags"
    FROM ""
    WHERE (contains(file.name, "machine learning") OR contains(content, "machine learning"))
    AND contains(file.tags, "#math")
    AND file.size > 2000
    SORT file.size DESC
```

Write a DQL query that matches the user's natural language request. Output ONLY the DQL query, no explanation."""

# Note Ranking System Prompt
NOTE_RANKING_PROMPT = """You are an expert at analyzing notes and ranking their relevance to a user's request. Your job is to evaluate a list of notes and select the most relevant ones for flashcard generation.

You will receive:
1. The user's original natural language request
2. A list of notes with metadata (filename, path, tags, modification time, size)

Your task:
1. Rank the notes by relevance to the user's request
2. Select the most relevant notes for flashcard generation
3. Consider factors like:
   - Direct relevance to the topic/request
   - Content freshness (newer notes may be more relevant)
   - Note tags that match the request
   - File naming patterns that suggest relevance
   - Note size (very small notes may have minimal content)

Return a JSON array of the selected note paths in order of relevance (most relevant first).

Example:
User request: "React hooks from last month"
Note list: [
  {"path": "Frontend/React-Hooks-Guide.md", "tags": ["#react", "#hooks"], "mtime": "2024-08-15"},
  {"path": "Random/Shopping-List.md", "tags": ["#personal"], "mtime": "2024-08-20"},
  {"path": "Frontend/useState-Examples.md", "tags": ["#react"], "mtime": "2024-08-10"}
]

Response: ["Frontend/React-Hooks-Guide.md", "Frontend/useState-Examples.md"]

Only return the JSON array, no explanation."""

class FlashcardAI:
    def __init__(self):
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

        if not os.getenv("ANTHROPIC_API_KEY"):
            raise ValueError("ANTHROPIC_API_KEY not found in environment variables")

    def generate_flashcards(self, note_content: str, note_title: str = "", target_cards: int = None, previous_fronts: list = None) -> List[Dict[str, str]]:
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

        user_prompt = f"""Note Title: {note_title}

        Note Content:
        {note_content}{dedup_context}

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

    def generate_flashcards_from_query(self, query: str, target_cards: int = None, previous_fronts: list = None) -> List[Dict[str, str]]:
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

                user_prompt = f"""User Query: {query}

        Please {card_instruction} to help someone learn about this topic. Focus on the most important concepts, definitions, and practical information related to this query.{dedup_context}"""

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

    def generate_flashcards_from_note_and_query(self, note_content: str, note_title: str, query: str, target_cards: int = None, previous_fronts: list = None) -> List[Dict[str, str]]:
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

                    user_prompt = f"""Note Title: {note_title}
            Query: {query}

            Note Content:
            {note_content}{dedup_context}

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
        """Use agent to find notes via natural language DQL generation and relevance ranking"""

        # Step 1: Generate DQL query (with retry on syntax errors)
        max_query_attempts = 2
        dql_query = None

        for attempt in range(max_query_attempts):
            dql_query = self.generate_dql_query(natural_request, search_folders)
            if not dql_query:
                return []

            try:
                # Step 2: Execute query to get ALL matching results
                console.print(f"[cyan]Agent:[/cyan] Executing DQL query...")
                results = obsidian_api.search_with_dql(dql_query)

                if results is None or len(results) == 0:
                    if attempt < max_query_attempts - 1:
                        console.print(f"[yellow]No results found, trying alternative query...[/yellow]")
                        continue
                    else:
                        console.print("[yellow]No matching notes found[/yellow]")
                        return []

                console.print(f"[cyan]Agent:[/cyan] Found {len(results)} candidate notes")

                # Check if too many results - force retry with more filtering
                if len(results) >= 100:
                    if attempt < max_query_attempts - 1:
                        console.print(f"[yellow]Too many results ({len(results)}), generating more specific query...[/yellow]")
                        # Mark this attempt as needing more filtering
                        natural_request = f"{natural_request}\n\nIMPORTANT: The previous query returned {len(results)} results which is too many. Please make your query MORE SPECIFIC and FILTERED to return fewer results."
                        continue
                    else:
                        console.print(f"[yellow]WARNING:[/yellow] Query still returned {len(results)} results after retry. Proceeding with ranking...")

                break

            except Exception as e:
                error_msg = str(e)
                console.print(f"[yellow]DQL Error (attempt {attempt + 1}):[/yellow] {error_msg}")

                if attempt < max_query_attempts - 1:
                    # Try to fix the query
                    console.print(f"[cyan]Agent:[/cyan] Fixing query syntax...")
                    # Query will be regenerated in next iteration
                else:
                    console.print(f"[red]ERROR:[/red] Failed to execute DQL query")
                    return []

        # Step 3: Apply basic filtering (folders, excluded tags)
        if config_manager:
            filtered_results = []
            for result in results:
                note_path = result['result'].get('path', '')

                # Apply SEARCH_FOLDERS filtering
                effective_folders = search_folders if search_folders is not None else SEARCH_FOLDERS
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

        if not results:
            console.print("[yellow]No notes remaining after filtering[/yellow]")
            return []

        # Step 4: Use existing weighted sampling logic instead of AI ranking
        # TODO: In future, add processing history context to AI ranking for better selection
        target_count = sample_size if sample_size else len(results)  # Use all results if no sample_size specified

        # Use the existing weighted sampling that considers processing history and tag weights
        sampled_notes = obsidian_api._weighted_sample(results, target_count, config_manager, bias_strength)

        # # Step 4: AI ranking to select most relevant notes (COMMENTED OUT - doesn't use processing history)
        # target_count = sample_size if sample_size else min(10, len(results))  # Default to top 10
        # ranked_paths = self.rank_notes_by_relevance(natural_request, results, target_count)
        #
        # # Step 5: Convert back to note objects in ranked order
        # ranked_notes = []
        # for path in ranked_paths:
        #     for note in results:
        #         if note['result'].get('path') == path:
        #             ranked_notes.append(note)
        #             break
        
        console.print()

        return sampled_notes

