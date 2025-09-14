import json
from pathlib import Path
from rich.console import Console
from rich.text import Text
from rich.panel import Panel

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
        console.print("   Get Obsidian API key from: Obsidian Settings > Community Plugins > REST API > API Key")
        obsidian_key = input("   Enter your Obsidian API key: ").strip()

        console.print("\n   Get Anthropic API key from: https://console.anthropic.com/")
        anthropic_key = input("   Enter your Anthropic API key: ").strip()

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

        try:
            max_cards = int(input("   How many flashcards per session? (default: 6): ").strip() or "6")
        except ValueError:
            max_cards = MAX_CARDS

        try:
            notes_to_sample = int(input("   How many notes to sample? (default: 3): ").strip() or "3")
        except ValueError:
            notes_to_sample = NOTES_TO_SAMPLE

        try:
            days_old = int(input("   Only process notes older than X days? (default: 7): ").strip() or "7")
        except ValueError:
            days_old = DAYS_OLD

        sampling_mode = input("   Sampling mode - 'random' or 'weighted'? (default: random): ").strip().lower()
        if sampling_mode not in ['random', 'weighted']:
            sampling_mode = SAMPLING_MODE

        card_type = input("   Card type - 'basic' or 'cloze'? (default: basic): ").strip().lower()
        if card_type not in ['basic', 'custom']:
            card_type = CARD_TYPE

        # Create config.json with user preferences
        user_config = {
            "MAX_CARDS": max_cards,
            "NOTES_TO_SAMPLE": notes_to_sample,
            "DAYS_OLD": days_old,
            "SAMPLING_MODE": sampling_mode,
            "CARD_TYPE": card_type,
            "SEARCH_FOLDERS": []
        }

        try:
            import json
            with open(CONFIG_FILE, "w") as f:
                json.dump(user_config, f, indent=2)
            console.print("   [green]✓[/green] Configuration saved")
        except Exception as e:
            console.print(f"   [red]ERROR:[/red] Could not create config.json: {e}")
            return
    else:
        console.print("[green]✓[/green] Configuration already exists")

    console.print("\n[green]Setup complete![/green]")
    console.print(f"[cyan]Config location:[/cyan] {CONFIG_DIR}")
    console.print("\nYou can now run 'obsidianki' to generate flashcards, or 'obsidianki --setup' to reconfigure.")