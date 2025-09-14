import argparse
import os
from pathlib import Path
from rich.console import Console
from rich.text import Text
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from obsidian import ObsidianAPI
from ai import FlashcardAI
from anki import AnkiAPI
from config import ConfigManager, MAX_CARDS, NOTES_TO_SAMPLE, DAYS_OLD, SAMPLING_MODE, CARD_TYPE
from wizard import setup, ENV_FILE, CONFIG_FILE

console = Console()

def main():
    parser = argparse.ArgumentParser(description="Generate flashcards from Obsidian notes")
    parser.add_argument("--setup", action="store_true", help="Run interactive setup to configure API keys")
    parser.add_argument("--cards", type=int, help="Override MAX_CARDS limit")
    parser.add_argument("--notes", nargs='+', help="Process specific notes by name")
    args = parser.parse_args()

    # Check if setup is needed (first run)
    needs_setup = False
    if not ENV_FILE.exists():
        needs_setup = True
    elif not CONFIG_FILE.exists():
        needs_setup = True

    if args.setup or needs_setup:
        if needs_setup and not args.setup:
            console.print("[yellow]First time setup required![/yellow]\n")
        setup()
        return

    # Determine max_cards and notes_to_sample based on arguments
    if args.notes:
        # When --notes is provided, scale cards to 2 * number of notes (unless --cards also provided)
        if args.cards is not None:
            max_cards = args.cards
        else:
            max_cards = len(args.notes) * 2  # Will be updated after we find actual notes
    elif args.cards is not None:
        # When --cards is provided, scale notes to 1/2 of cards
        max_cards = args.cards
        notes_to_sample = max(1, max_cards // 2)
    else:
        # Default behavior - use config values
        max_cards = MAX_CARDS
        notes_to_sample = NOTES_TO_SAMPLE

    console.print(Panel(Text("ObsidianKi - Generating flashcards", style="bold blue"), style="blue"))
    console.print("")

    # Initialize APIs and config
    config = ConfigManager()
    obsidian = ObsidianAPI()
    ai = FlashcardAI()
    anki = AnkiAPI()

    if SAMPLING_MODE == "weighted":
        config.show_current_weights()

    # Test connections
    if not obsidian.test_connection():
        console.print("[red]ERROR:[/red] Cannot connect to Obsidian REST API")
        return

    if not anki.test_connection():
        console.print("[red]ERROR:[/red] Cannot connect to AnkiConnect")
        return

    console.print("[green]SUCCESS:[/green] Connected to Obsidian and Anki\n")

    # Get notes to process
    if args.notes:
        old_notes = []

        for note_name in args.notes:
            specific_note = obsidian.find_note_by_name(note_name)

            if specific_note:
                old_notes.append(specific_note)
            else:
                console.print(f"[red]ERROR:[/red] Not found: '{note_name}'")

        if not old_notes:
            console.print("[red]ERROR:[/red] No notes found")
            return

        # Update max_cards based on actually found notes (if --cards wasn't specified)
        if args.cards is None:
            max_cards = len(old_notes) * 2

        console.print(f"[cyan]INFO:[/cyan] Processing {len(old_notes)} note(s)")
        console.print(f"[cyan]TARGET:[/cyan] {max_cards} flashcards maximum ({max_cards // len(old_notes)} per note average)")
    else:
        old_notes = obsidian.get_random_old_notes(days=DAYS_OLD, limit=notes_to_sample, config_manager=config)

        if not old_notes:
            console.print("[red]ERROR:[/red] No old notes found")
            return

        console.print(f"[green]SUCCESS:[/green] Found {len(old_notes)} notes")
        console.print(f"[cyan]TARGET:[/cyan] {max_cards} flashcards maximum")

    total_cards = 0

    # Process each note
    for i, note in enumerate(old_notes, 1):
        if total_cards >= max_cards:
            break
        note_path = note['result']['path']
        note_title = note['result']['filename']

        console.print(f"\n[yellow]PROCESSING:[/yellow] Note {i}/{len(old_notes)}: [bold]{note_title}[/bold]")

        # Get note content
        note_content = obsidian.get_note_content(note_path)
        if not note_content:
            console.print("  [yellow]WARNING:[/yellow] Empty or inaccessible note, skipping")
            continue

        # Generate flashcards
        flashcards = ai.generate_flashcards(note_content, note_title)
        if not flashcards:
            console.print("  [yellow]WARNING:[/yellow] No flashcards generated, skipping")
            continue

        console.print(f"  [green]Generated {len(flashcards)} flashcards[/green]")

        # Hard limit (disabled)
        # cards_to_add = flashcards[:MAX_CARDS - total_cards]
        # if len(cards_to_add) < len(flashcards):
        #     print(f"  📊 Limiting to {len(cards_to_add)} cards to stay within daily limit")

        # Add to Anki
        result = anki.add_flashcards(flashcards, card_type=CARD_TYPE,
                                   note_path=note_path, note_title=note_title)
        successful_cards = len([r for r in result if r is not None])

        if successful_cards > 0:
            console.print(f"  [green]SUCCESS:[/green] Added {successful_cards} cards to Anki")
            total_cards += successful_cards

            # Record flashcard creation for density tracking
            note_size = len(note_content)
            config.record_flashcards_created(note_path, note_size, successful_cards)
        else:
            console.print("  [red]ERROR:[/red] Failed to add cards to Anki")

    console.print("")
    console.print(Panel(f"[bold green]COMPLETE![/bold green] Added {total_cards}/{max_cards} flashcards to your Obsidian deck", style="green"))


if __name__ == "__main__":
    main()