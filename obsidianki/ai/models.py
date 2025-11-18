MODEL_MAP = {
    "Claude Sonnet 4": {
        "provider": "anthropic",
        "url": "https://console.anthropic.com/",
        "model": "claude-sonnet-4-20250514",
        "key_name": "ANTHROPIC_API_KEY"
    },
    "Claude Opus 4": {
        "provider": "anthropic",
        "model": "claude-opus-4-20250514"
    },
    "GPT-5": {
        "provider": "openai",
        "model": "gpt-5"
    },
    "Gemini 3": {
        "provider": "google",
        "model": "gemini/gemini-2.5-pro",
        "key_name": "GOOGLE_API_KEY",
        "url": "https://makersuite.google.com/app/apikey"
    },
    "GPT-4o": {
        "provider": "openai",
        "model": "gpt-4o"
    },
    "GPT-4o Mini": {
        "provider": "openai",
        "model": "gpt-4o-mini"
    },
    "Gemini 2.5 Flash": {
        "provider": "google",
        "model": "google/gemini-2.0-flash-exp"
    },
    "DeepSeek V3.1": {
        "provider": "deepseek",
        "model": "deepseek/deepseek-chat"
    }
}