import json
from pathlib import Path
from rich.console import Console
from rich.text import Text
from rich.panel import Panel
from rich.prompt import Prompt, IntPrompt, Confirm
from rich.table import Table

console = Console()

from config import CONFIG_DIR

# Standard config directory location
ENV_FILE = CONFIG_DIR / ".env"
CONFIG_FILE = CONFIG_DIR / "config.json"

def setup():
    """Interactive setup to configure API keys and preferences"""
    console.print(Panel(Text("ObsidianKi Setup", style="bold blue"), style="blue"))

    step_num = 1

    # Ensure config directory exists
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    # Setup API keys only if .env doesn't exist
    if not ENV_FILE.exists():
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

        # Create .env file
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

    if not CONFIG_FILE.exists():
        console.print(f"\n[cyan]Step {step_num}: Preferences[/cyan]")

        # Import config defaults here to avoid circular imports during build
        from config import MAX_CARDS, NOTES_TO_SAMPLE, DAYS_OLD, SAMPLING_MODE, CARD_TYPE

        max_cards = IntPrompt.ask("   How many flashcards per session?", default=MAX_CARDS)
        notes_to_sample = IntPrompt.ask("   How many notes to sample?", default=NOTES_TO_SAMPLE)
        days_old = IntPrompt.ask("   Only process notes older than X days?", default=DAYS_OLD)

        sampling_mode = Prompt.ask(
            "   Sampling mode",
            choices=["random", "weighted"],
            default=SAMPLING_MODE
        )

        card_type = Prompt.ask(
            "   Card type",
            choices=["basic", "custom"],
            default=CARD_TYPE
        )

        # Create config.json with user preferences and defaults
        user_config = {
            "MAX_CARDS": max_cards,
            "NOTES_TO_SAMPLE": notes_to_sample,
            "DAYS_OLD": days_old,
            "SAMPLING_MODE": sampling_mode,
            "CARD_TYPE": card_type,
            "SEARCH_FOLDERS": [],
            "TAG_SCHEMA_FILE": "tags.json",
            "PROCESSING_HISTORY_FILE": "processing_history.json",
            "DENSITY_BIAS_STRENGTH": 0.5
        }

        try:
            import json
            with open(CONFIG_FILE, "w") as f:
                json.dump(user_config, f, indent=2)
            console.print("   [green]✓[/green] Configuration saved")

            # Create default tags.json
            tags_file = CONFIG_DIR / "tags.json"
            default_tags = {"_default": 1.0}
            with open(tags_file, "w") as f:
                json.dump(default_tags, f, indent=2)
            console.print("   [green]✓[/green] Default tags schema created")

        except Exception as e:
            console.print(f"   [red]ERROR:[/red] Could not create config files: {e}")
            return
    else:
        console.print("[green]✓[/green] Configuration already exists")

    console.print("\n[green]Setup complete![/green]")
    console.print(f"[cyan]Config location:[/cyan] {CONFIG_DIR}")
    console.print("\nYou can now run 'obsidianki' to generate flashcards, or 'obsidianki --setup' to reconfigure.")