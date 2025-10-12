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

        console.print("\n   Get Anthropic API key from: [blue]https://console.anthropic.com/[/blue]")
        anthropic_key = Prompt.ask("   Enter your Anthropic API key", password=True).strip()
        if not anthropic_key:
            console.print("[red]ERROR:[/red] Anthropic API key is required. Setup aborted.")
            return

        env_content = f"""OBSIDIAN_API_KEY={obsidian_key}
ANTHROPIC_API_KEY={anthropic_key}
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