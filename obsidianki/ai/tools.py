FLASHCARD_TOOL: dict = {
    "type": "function",
    "function": {
        "name": "create_flashcards",
        "description": "Propose flashcards from note content. In vector mode, returns similarity feedback before final submission.",
        "parameters": {
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
}

# Submit tool for vector dedup mode - confirms flashcard submission after similarity review
SUBMIT_FLASHCARDS_TOOL: dict = {
    "type": "function",
    "function": {
        "name": "submit_flashcards",
        "description": "Confirm and submit the last proposed flashcards. Call this after reviewing similarity feedback to finalize submission.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
}

# DQL Execution Tool for multi-turn agent
DQL_EXECUTION_TOOL: dict = {
    "type": "function",
    "function": {
        "name": "execute_dql_query",
        "description": "Execute a DQL query against the Obsidian vault and get results",
        "parameters": {
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
}

# Final selection tool for multi-turn agent
FINALIZE_SELECTION_TOOL: dict = {
    "type": "function",
    "function": {
        "name": "finalize_note_selection",
        "description": "Finalize the selection of notes that best match the user's request",
        "parameters": {
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
}