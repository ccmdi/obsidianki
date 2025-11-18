import json
from rich.text import Text
from rich.panel import Panel
from rich.prompt import Prompt, IntPrompt, Confirm

from obsidianki.cli.config import console, CONFIG_DIR, ENV_FILE, CONFIG_FILE

def setup(force_full_setup=False):
    """Interactive setup to configure API keys and preferences"""
    console.print(Panel(Text("ObsidianKi Setup", style="bold blue"), style="blue"))

    step_num = 1

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    if not ENV_FILE.exists() or force_full_setup:
        console.print(f"[cyan]Step {step_num}: API Keys[/cyan]")
        console.print("   Get Obsidian API key from: [blue]Obsidian Settings > Community Plugins > REST API > API Key[/blue]")

        obsidian_key = Prompt.ask("   Enter your Obsidian API key", password=True).strip()
        if not obsidian_key:
            console.print("[red]ERROR:[/red] Obsidian API key is required. Setup aborted.")
            return

        console.print("\n   [cyan]AI Provider Selection[/cyan]")
        console.print("   Choose your AI provider for flashcard generation:")

        ai_provider = Prompt.ask(
            "   Select provider",
            choices=["anthropic", "openai", "google", "groq", "azure", "cohere", "together", "mistral"],
            default="anthropic"
        )

        # Provider-specific instructions and model defaults
        provider_info = {
            "anthropic": {
                "url": "https://console.anthropic.com/",
                "key_name": "ANTHROPIC_API_KEY",
                "default_model": "claude-sonnet-4-20250514"
            },
            "openai": {
                "url": "https://platform.openai.com/api-keys",
                "key_name": "OPENAI_API_KEY",
                "default_model": "gpt-4o"
            },
            "google": {
                "url": "https://makersuite.google.com/app/apikey",
                "key_name": "GOOGLE_API_KEY",
                "default_model": "gemini/gemini-2.0-flash-exp"
            },
            "groq": {
                "url": "https://console.groq.com/keys",
                "key_name": "GROQ_API_KEY",
                "default_model": "groq/llama-3.3-70b-versatile"
            },
            "azure": {
                "url": "https://portal.azure.com/",
                "key_name": "AZURE_API_KEY",
                "default_model": "azure/gpt-4o"
            },
            "cohere": {
                "url": "https://dashboard.cohere.com/api-keys",
                "key_name": "COHERE_API_KEY",
                "default_model": "command-r-plus"
            },
            "together": {
                "url": "https://api.together.xyz/settings/api-keys",
                "key_name": "TOGETHER_API_KEY",
                "default_model": "together_ai/meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo"
            },
            "mistral": {
                "url": "https://console.mistral.ai/api-keys/",
                "key_name": "MISTRAL_API_KEY",
                "default_model": "mistral/mistral-large-latest"
            }
        }

        info = provider_info[ai_provider]
        console.print(f"\n   Get {ai_provider.title()} API key from: [blue]{info['url']}[/blue]")

        ai_key = Prompt.ask(f"   Enter your {ai_provider.title()} API key", password=True).strip()
        if not ai_key:
            console.print(f"[red]ERROR:[/red] {ai_provider.title()} API key is required. Setup aborted.")
            return

        # Optional: let user customize model
        console.print(f"\n   Default model: [green]{info['default_model']}[/green]")
        custom_model = Prompt.ask("   Custom model (press Enter to use default)", default="").strip()
        ai_model = custom_model if custom_model else info['default_model']

        env_content = f"""OBSIDIAN_API_KEY={obsidian_key}
{info['key_name']}={ai_key}
        """

        try:
            with open(ENV_FILE, "w") as f:
                f.write(env_content)
            console.print("   [green]✓[/green] API keys saved")
        except Exception as e:
            console.print(f"   [red]ERROR:[/red] Could not create .env file: {e}")
            return
        step_num += 1
    else:
        console.print("[green]✓[/green] API keys already configured")

    if not CONFIG_FILE.exists() or force_full_setup:
        console.print(f"\n[cyan]Step {step_num}: Preferences[/cyan]")

        from obsidianki.cli.config import CONFIG

        max_cards = IntPrompt.ask("   How many flashcards per session?", default=CONFIG.max_cards)
        notes_to_sample = IntPrompt.ask("   How many notes to sample?", default=CONFIG.notes_to_sample)
        days_old = IntPrompt.ask("   Only process notes older than X days?", default=CONFIG.days_old)

        sampling_mode = Prompt.ask(
            "   Sampling mode",
            choices=["random", "weighted"],
            default=CONFIG.sampling_mode
        )

        card_type = Prompt.ask(
            "   Card type",
            choices=["basic", "custom"],
            default=CONFIG.card_type
        )

        console.print("\n   [cyan]Approval Settings[/cyan]")
        approve_notes = Confirm.ask(
            "   Review each note before AI processing?",
            default=CONFIG.approve_notes
        )

        approve_cards = Confirm.ask(
            "   Review each flashcard before adding to Anki?",
            default=CONFIG.approve_cards
        )

        deduplicate_via_history = Confirm.ask(
            "   Avoid duplicate flashcards using processing history?",
            default=CONFIG.deduplicate_via_history
        )

        syntax_highlighting = Confirm.ask(
            "   Enable syntax highlighting for code blocks in flashcards?",
            default=CONFIG.syntax_highlighting
        )

        # Create config.json with user preferences merged with defaults
        from obsidianki.cli.config import DEFAULT_CONFIG

        user_config = DEFAULT_CONFIG.copy()
        user_config.update({
            "MAX_CARDS": max_cards,
            "NOTES_TO_SAMPLE": notes_to_sample,
            "DAYS_OLD": days_old,
            "SAMPLING_MODE": sampling_mode,
            "CARD_TYPE": card_type,
            "APPROVE_NOTES": approve_notes,
            "APPROVE_CARDS": approve_cards,
            "DEDUPLICATE_VIA_HISTORY": deduplicate_via_history,
            "SYNTAX_HIGHLIGHTING": syntax_highlighting,
            "AI_PROVIDER": ai_provider,
            "AI_MODEL": ai_model,
        })

        try:
            CONFIG.save(user_config)
            console.print("   [green]✓[/green] Configuration saved")

            CONFIG.tag_weights = {"_default": 1.0}
            CONFIG.save_tag_schema()
            console.print("   [green]✓[/green] Default tags schema created")

        except Exception as e:
            console.print(f"   [red]ERROR:[/red] Could not create config files: {e}")
            return
    else:
        console.print("[green]✓[/green] Configuration already exists")

    console.print("\n[green]Setup complete![/green]")
    console.print(f"[cyan]Config location:[/cyan] {CONFIG_DIR}")
    console.print("\nYou can now run 'obsidianki' to generate flashcards, or 'obsidianki --setup' to reconfigure.")