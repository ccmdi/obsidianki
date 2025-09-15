import argparse
import os
from pathlib import Path
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.text import Text
from obsidian import ObsidianAPI
from ai import FlashcardAI
from anki import AnkiAPI
from config import ConfigManager, MAX_CARDS, NOTES_TO_SAMPLE, DAYS_OLD, SAMPLING_MODE, CARD_TYPE, APPROVE_NOTES, APPROVE_CARDS, console, CONFIG_DIR, ENV_FILE, CONFIG_FILE
from wizard import setup

def approve_note(note_title: str, note_path: str) -> bool:
    """Ask user to approve note processing"""
    console.print(f"   [yellow]Review note:[/yellow] [bold]{note_title}[/bold]")
    console.print(f"   [dim]Path: {note_path}[/dim]")

    from rich.prompt import Confirm
    return Confirm.ask("   Process this note?", default=True)

def approve_flashcard(flashcard: dict, note_title: str) -> bool:
    """Ask user to approve flashcard before adding to Anki"""
    console.print(f"   [cyan]Front:[/cyan] {flashcard.get('front', 'N/A')}")
    console.print(f"   [cyan]Back:[/cyan] {flashcard.get('back', 'N/A')}")

    from rich.prompt import Confirm
    return Confirm.ask("   Add this card to Anki?", default=True)

def main():
    parser = argparse.ArgumentParser(description="Generate flashcards from Obsidian notes")
    parser.add_argument("--setup", action="store_true", help="Run interactive setup to configure API keys")
    parser.add_argument("--cards", type=int, help="Override MAX_CARDS limit")
    parser.add_argument("--notes", nargs='+', help="Process specific notes by name")
    parser.add_argument("-q", "--query", type=str, help="Generate cards from query (standalone) or extract specific info from notes")
    parser.add_argument("--config", action="store_true", help="Show configuration directory path")
    args = parser.parse_args()

    if args.config:
        console.print(str(CONFIG_DIR))
        return

    needs_setup = False
    if not ENV_FILE.exists():
        needs_setup = True
    elif not CONFIG_FILE.exists():
        needs_setup = True

    if args.setup or needs_setup:
        try:
            setup(force_full_setup=args.setup)
        except KeyboardInterrupt:
            console.print("\n[yellow]Setup cancelled by user[/yellow]")
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

    # Handle query mode
    if args.query:
        if not args.notes:
            # Standalone query mode - generate cards from query alone
            console.print(f"[cyan]QUERY MODE:[/cyan] Generating flashcards for: [bold]{args.query}[/bold]")

            target_cards = args.cards if args.cards else None
            flashcards = ai.generate_flashcards_from_query(args.query, target_cards=target_cards)
            if not flashcards:
                console.print("[red]ERROR:[/red] No flashcards generated from query")
                return

            console.print(f"[green]Generated {len(flashcards)} flashcards[/green]")

            # Flashcard approval (before adding to Anki)
            approved_flashcards = []
            if APPROVE_CARDS:
                for flashcard in flashcards:
                    if approve_flashcard(flashcard, f"Query: {args.query}"):
                        approved_flashcards.append(flashcard)

                if not approved_flashcards:
                    console.print("[yellow]WARNING:[/yellow] No flashcards approved")
                    return

                console.print(f"[cyan]Approved {len(approved_flashcards)}/{len(flashcards)} flashcards[/cyan]")
                cards_to_add = approved_flashcards
            else:
                cards_to_add = flashcards

            # Add to Anki
            result = anki.add_flashcards(cards_to_add, card_type=CARD_TYPE,
                                       note_path="query", note_title=f"Query: {args.query}")
            successful_cards = len([r for r in result if r is not None])

            if successful_cards > 0:
                console.print(f"[green]SUCCESS:[/green] Added {successful_cards} cards to Anki")
            else:
                console.print("[red]ERROR:[/red] Failed to add cards to Anki")

            console.print(f"\n[bold green]COMPLETE![/bold green] Added {successful_cards} flashcards from query")
            return

    # Get notes to process
    if args.notes:
        old_notes = []

        for note_name in args.notes:
            specific_note = obsidian.find_note_by_name(note_name, config_manager=config)

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

        if args.query:
            console.print(f"[cyan]TARGETED MODE:[/cyan] Extracting '{args.query}' from {len(old_notes)} note(s)")
            console.print(f"[cyan]TARGET:[/cyan] {max_cards} flashcards maximum ({max_cards // len(old_notes)} per note average)")
        else:
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

    # Calculate target cards per note
    target_cards_per_note = max(1, max_cards // len(old_notes)) if args.cards else None

    # Process each note
    for i, note in enumerate(old_notes, 1):
        if total_cards >= max_cards:
            break
        note_path = note['result']['path']
        note_title = note['result']['filename']

        console.print(f"\n[yellow]PROCESSING:[/yellow] Note {i}/{len(old_notes)}: [bold]{note_title}[/bold]")

        # Note approval (before AI processing)
        if APPROVE_NOTES:
            if not approve_note(note_title, note_path):
                continue

        # Get note content
        note_content = obsidian.get_note_content(note_path)
        if not note_content:
            console.print("  [yellow]WARNING:[/yellow] Empty or inaccessible note, skipping")
            continue

        # Generate flashcards
        if args.query:
            # Paired query mode - extract specific info from note based on query
            console.print(f"  [cyan]Extracting info for query:[/cyan] [bold]{args.query}[/bold]")
            flashcards = ai.generate_flashcards_from_note_and_query(note_content, note_title, args.query, target_cards=target_cards_per_note)
        else:
            # Normal mode - generate flashcards from note content
            flashcards = ai.generate_flashcards(note_content, note_title, target_cards=target_cards_per_note)
        if not flashcards:
            console.print("  [yellow]WARNING:[/yellow] No flashcards generated, skipping")
            continue

        console.print(f"  [green]Generated {len(flashcards)} flashcards[/green]")

        # Flashcard approval (before adding to Anki)
        approved_flashcards = []
        if APPROVE_CARDS:
            for flashcard in flashcards:
                if approve_flashcard(flashcard, note_title):
                    approved_flashcards.append(flashcard)

            if not approved_flashcards:
                console.print("  [yellow]WARNING:[/yellow] No flashcards approved, skipping")
                continue

            console.print(f"  [cyan]Approved {len(approved_flashcards)}/{len(flashcards)} flashcards[/cyan]")
            cards_to_add = approved_flashcards
        else:
            cards_to_add = flashcards

        # Add to Anki
        result = anki.add_flashcards(cards_to_add, card_type=CARD_TYPE,
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
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
    except Exception as e:
        console.print(f"\n[red]ERROR:[/red] {e}")
        raise