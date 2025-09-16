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
    AND (length(attempts) = 0 OR !contains(attempts, date("2024-07-16")))
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
                                card['front'] = process_code_blocks(card['front'], syntax_highlighting)
                            if 'back' in card:
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
                                card['front'] = process_code_blocks(card['front'], syntax_highlighting)
                            if 'back' in card:
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
                                card['front'] = process_code_blocks(card['front'], syntax_highlighting)
                            if 'back' in card:
                                card['back'] = process_code_blocks(card['back'], syntax_highlighting)
                        return flashcards

            console.print("[yellow]WARNING:[/yellow] No flashcards generated - unexpected response format")
            return []

        except Exception as e:
            console.print(f"[red]ERROR:[/red] Error generating targeted flashcards: {e}")
            return []

    def generate_dql_query(self, natural_request: str, max_attempts: int = 3) -> str:
        """Generate DQL query from natural language with error correction"""

        for attempt in range(max_attempts):
            try:
                console.print(f"[cyan]AI Agent:[/cyan] Generating DQL query (attempt {attempt + 1}/{max_attempts})")

                # Add folder context to the request
                folder_context = ""
                if SEARCH_FOLDERS:
                    folder_context = f"\n\nIMPORTANT: Only search in these folders: {SEARCH_FOLDERS}. Add appropriate folder filtering to your WHERE clause using startswith(file.path, \"folder/\")."

                user_prompt = f"""Natural language request: {natural_request}{folder_context}

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

                    console.print(f"[dim]Generated query:[/dim] {dql_query}...")
                    return dql_query

            except Exception as e:
                console.print(f"[red]ERROR:[/red] Failed to generate DQL query (attempt {attempt + 1}): {e}")

        console.print(f"[red]ERROR:[/red] Failed to generate DQL query after {max_attempts} attempts")
        return None

    def find_notes_with_agent(self, natural_request: str, obsidian_api, config_manager=None, sample_size: int = None, bias_strength: float = None) -> List[Dict]:
        """Use AI agent to find notes via natural language DQL generation"""

        max_query_attempts = 3

        for query_attempt in range(max_query_attempts):
            # Generate DQL query
            dql_query = self.generate_dql_query(natural_request)
            if not dql_query:
                return []

            try:
                # Test the query
                console.print(f"[cyan]AI Agent:[/cyan] Executing DQL query...")
                results = obsidian_api.search_with_dql(dql_query)

                if results is None:
                    console.print(f"[yellow]Warning:[/yellow] Query returned no results, trying again...")
                    continue

                # Apply additional filtering (SEARCH_FOLDERS and excluded tags)
                if config_manager:
                    from obsidian import ObsidianAPI
                    filtered_results = []
                    for result in results:
                        note_path = result['result'].get('path', '')

                        # Apply SEARCH_FOLDERS filtering if not already in query
                        if SEARCH_FOLDERS:
                            path_matches = any(note_path.startswith(f"{folder}/") for folder in SEARCH_FOLDERS)
                            if not path_matches:
                                continue

                        # Apply excluded tags filtering
                        note_tags = result['result'].get('tags', []) or []
                        excluded_tags = config_manager.get_excluded_tags()
                        if excluded_tags and any(tag in note_tags for tag in excluded_tags):
                            continue

                        filtered_results.append(result)

                    results = filtered_results

                # Apply sampling if requested
                if sample_size and len(results) > sample_size:
                    if config_manager:
                        results = obsidian_api._weighted_sample(results, sample_size, config_manager, bias_strength)
                    else:
                        import random
                        results = random.sample(results, sample_size)

                console.print(f"[green]AI Agent:[/green] Found {len(results)} matching notes")
                return results

            except Exception as e:
                error_msg = str(e)
                console.print(f"[yellow]DQL Error (attempt {query_attempt + 1}):[/yellow] {error_msg}")

                if query_attempt < max_query_attempts - 1:
                    # Try to fix the query with error feedback
                    console.print(f"[cyan]AI Agent:[/cyan] Attempting to fix query based on error...")

                    fix_prompt = f"""The previous DQL query failed with this error:
{error_msg}

Original request: {natural_request}
Failed query: {dql_query}

Generate a corrected DQL query that fixes this error. Common fixes:
- Check property names (case sensitive)
- Use proper date format: date("YYYY-MM-DD")
- Check tag format: contains(file.tags, "#tagname")
- Verify array operations: length(array_property)
- Use proper string escaping

Output ONLY the corrected DQL query."""

                    try:
                        fix_response = self.client.messages.create(
                            model="claude-4-sonnet-20250514",
                            max_tokens=2000,
                            system=DQL_AGENT_PROMPT,
                            messages=[{"role": "user", "content": fix_prompt}]
                        )

                        if fix_response.content and len(fix_response.content) > 0:
                            dql_query = fix_response.content[0].text.strip()

                            # Clean up the query
                            if "```" in dql_query:
                                dql_query = re.sub(r'```[a-zA-Z]*\n?', '', dql_query)
                                dql_query = dql_query.replace("```", "").strip()

                            console.print(f"[dim]Corrected query:[/dim] {dql_query[:100]}...")
                            continue  # Try the corrected query

                    except Exception as fix_error:
                        console.print(f"[red]Error generating fix:[/red] {fix_error}")

        console.print(f"[red]ERROR:[/red] Failed to execute DQL query after {max_query_attempts} attempts")
        return []

