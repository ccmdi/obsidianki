PROVIDER_COLORS = {
    "anthropic": "#D97757",  # Anthropic orange
    "google": "#4285F4",     # Google blue
    "openai": "#10A37F",     # OpenAI green
    "deepseek": "#536DFE",   # DeepSeek purple-blue
}

MODEL_MAP = {
    "Claude Sonnet 4.5": {
        "provider": "anthropic",
        "url": "https://console.anthropic.com/",
        "model": "claude-sonnet-4-5",
        "key_name": "ANTHROPIC_API_KEY"
    },
    "Claude Opus 4.5": {
        "provider": "anthropic",
        "model": "claude-opus-4-5",
        "key_name": "ANTHROPIC_API_KEY",
        "url": "https://console.anthropic.com/"
    },
    "GPT-5": {
        "provider": "openai",
        "model": "gpt-5",
        "key_name": "OPENAI_API_KEY",
        "url": "https://platform.openai.com/api-keys"
    },
    "Gemini 3 Pro": {
        "provider": "google",
        "model": "gemini-3-pro-preview",
        "key_name": "GEMINI_API_KEY",
        "url": "https://makersuite.google.com/app/apikey"
    },
    "GPT-4o": {
        "provider": "openai",
        "model": "gpt-4o",
        "key_name": "OPENAI_API_KEY",
        "url": "https://platform.openai.com/api-keys"
    },
    "GPT-4o Mini": {
        "provider": "openai",
        "model": "gpt-4o-mini",
        "key_name": "OPENAI_API_KEY",
        "url": "https://platform.openai.com/api-keys"
    },
    "Gemini 3 Flash": {
        "provider": "google",
        "model": "gemini-3-flash-preview",
        "key_name": "GEMINI_API_KEY",
        "url": "https://makersuite.google.com/app/apikey"
    },
    "DeepSeek V3.1": {
        "provider": "deepseek",
        "model": "deepseek-chat",
        "key_name": "DEEPSEEK_API_KEY",
        "url": "https://console.deepseek.com/"
    }
}