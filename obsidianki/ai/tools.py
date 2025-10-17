from anthropic.types import ToolParam

FLASHCARD_TOOL: ToolParam = {
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

# DQL Execution Tool for multi-turn agent
DQL_EXECUTION_TOOL: ToolParam = {
    "name": "execute_dql_query",
    "description": "Execute a DQL query against the Obsidian vault and get results",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The DQL query to execute"
            },
            "reasoning": {
                "type": "string",
                "description": "Brief explanation of what this query is trying to find"
            }
        },
        "required": ["query", "reasoning"]
    }
}

# Final selection tool for multi-turn agent
FINALIZE_SELECTION_TOOL: ToolParam = {
    "name": "finalize_note_selection",
    "description": "Finalize the selection of notes that best match the user's request",
    "input_schema": {
        "type": "object",
        "properties": {
            "selected_paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Array of note paths to process for flashcard generation"
            },
            "reasoning": {
                "type": "string",
                "description": "Brief explanation of why these notes were selected"
            }
        },
        "required": ["selected_paths", "reasoning"]
    }
}