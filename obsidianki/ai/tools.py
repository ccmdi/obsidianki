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