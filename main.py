import argparse
import os
from pathlib import Path
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.text import Text
from config import console, CONFIG_DIR, ENV_FILE, CONFIG_FILE
from cli_handlers import handle_config_command, handle_tag_command, handle_history_command

def main():
    parser = argparse.ArgumentParser(description="Generate flashcards from Obsidian notes")
    parser.add_argument("--setup", action="store_true", help="Run interactive setup to configure API keys")
    parser.add_argument("--cards", type=int, help="Override MAX_CARDS limit")
    parser.add_argument("--notes", nargs='+', help="Process specific notes by name")
    parser.add_argument("-q", "--query", type=str, help="Generate cards from query (standalone) or extract specific info from notes")

    # Config management subparser
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    config_parser = subparsers.add_parser('config', help='Manage configuration')
    config_subparsers = config_parser.add_subparsers(dest='config_action', help='Config actions')

    # config list
    config_subparsers.add_parser('list', help='List all configuration settings')

    # config get <key>
    get_parser = config_subparsers.add_parser('get', help='Get a configuration value')
    get_parser.add_argument('key', help='Configuration key to get')

    # config set <key> <value>
    set_parser = config_subparsers.add_parser('set', help='Set a configuration value')
    set_parser.add_argument('key', help='Configuration key to set')
    set_parser.add_argument('value', help='Value to set')

    # config reset
    config_subparsers.add_parser('reset', help='Reset configuration to defaults')

    # config where
    config_subparsers.add_parser('where', help='Show configuration directory path')

    # History management
    history_parser = subparsers.add_parser('history', help='Manage processing history')
    history_subparsers = history_parser.add_subparsers(dest='history_action', help='History actions')

    # history clear
    history_subparsers.add_parser('clear', help='Clear processing history')

    # Tag management
    tag_parser = subparsers.add_parser('tag', help='Manage tag weights')
    tag_subparsers = tag_parser.add_subparsers(dest='tag_action', help='Tag actions')

    # tag list
    tag_subparsers.add_parser('list', help='List all tag weights')

    # tag add <tag> <weight>
    add_parser = tag_subparsers.add_parser('add', help='Add or update a tag weight')
    add_parser.add_argument('tag', help='Tag name')
    add_parser.add_argument('weight', type=float, help='Tag weight')

    # tag remove <tag>
    remove_parser = tag_subparsers.add_parser('remove', help='Remove a tag weight')
    remove_parser.add_argument('tag', help='Tag name to remove')

    # tag exclude <tag>
    exclude_parser = tag_subparsers.add_parser('exclude', help='Add a tag to exclusion list')
    exclude_parser.add_argument('tag', help='Tag name to exclude')

    # tag include <tag>
    include_parser = tag_subparsers.add_parser('include', help='Remove a tag from exclusion list')
    include_parser.add_argument('tag', help='Tag name to include')
    args = parser.parse_args()

    # Handle config, history, and tag management commands
    if args.command == 'config':
        handle_config_command(args)
        return
    elif args.command == 'history':
        handle_history_command(args)
        return
    elif args.command == 'tag':
        handle_tag_command(args)
        return

    needs_setup = False
    if not ENV_FILE.exists():
        needs_setup = True
    elif not CONFIG_FILE.exists():
        needs_setup = True

    if args.setup or needs_setup:
        try:
            # Lazy import setup wizard
            from wizard import setup
            setup(force_full_setup=args.setup)
        except KeyboardInterrupt:
            console.print("\n[yellow]Setup cancelled by user[/yellow]")
        return

    # Lazy import heavy dependencies only when needed for flashcard generation
    from obsidian import ObsidianAPI
    from ai import FlashcardAI
    from anki import AnkiAPI
    from config import ConfigManager, MAX_CARDS, NOTES_TO_SAMPLE, DAYS_OLD, SAMPLING_MODE, CARD_TYPE, APPROVE_NOTES, APPROVE_CARDS, DEDUPLICATE_VIA_HISTORY
    from cli_handlers import approve_note, approve_flashcard

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

    # Handle query mode
    if args.query:
        if not args.notes:
            # Standalone query mode - generate cards from query alone
            console.print(f"[cyan]QUERY MODE:[/cyan] [bold]{args.query}[/bold]")

            target_cards = args.cards if args.cards else None
            flashcards = ai.generate_flashcards_from_query(args.query, target_cards=target_cards)
            if not flashcards:
                console.print("[red]ERROR:[/red] No flashcards generated from query")
                return

            console.print(f"[green]Generated {len(flashcards)} flashcards[/green]")

            # Flashcard approval (before adding to Anki)
            approved_flashcards = []
            if APPROVE_CARDS:
                try:
                    for flashcard in flashcards:
                        if approve_flashcard(flashcard, f"Query: {args.query}"):
                            approved_flashcards.append(flashcard)
                except KeyboardInterrupt:
                    console.print("\n[yellow]Operation cancelled by user[/yellow]")
                    return

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
            console.print(f"[cyan]TARGET:[/cyan] {max_cards} flashcards maximum")
        else:
            console.print(f"[cyan]INFO:[/cyan] Processing {len(old_notes)} note(s)")
            console.print(f"[cyan]TARGET:[/cyan] {max_cards} flashcards maximum")
        console.print()
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

    if args.cards and target_cards_per_note > 5:
        console.print(f"[yellow]WARNING:[/yellow] Requesting more than 5 cards per note can decrease quality")
        console.print(f"[yellow]Consider using fewer total cards or more notes for better results[/yellow]\n")

    # Process each note
    for i, note in enumerate(old_notes, 1):
        if total_cards >= max_cards:
            break
        note_path = note['result']['path']
        note_title = note['result']['filename']

        console.print(f"\n[blue]PROCESSING:[/blue] Note {i}/{len(old_notes)}: [bold]{note_title}[/bold]")

        # Note approval (before AI processing)
        if APPROVE_NOTES:
            try:
                if not approve_note(note_title, note_path):
                    continue
            except KeyboardInterrupt:
                console.print("\n[yellow]Operation cancelled by user[/yellow]")
                return

        # Get note content
        note_content = obsidian.get_note_content(note_path)
        if not note_content:
            console.print("  [yellow]WARNING:[/yellow] Empty or inaccessible note, skipping")
            continue

        # Get previous flashcard fronts for deduplication if enabled
        previous_fronts = []
        if DEDUPLICATE_VIA_HISTORY:
            previous_fronts = config.get_flashcard_fronts_for_note(note_path)
            if previous_fronts:
                console.print(f"  [dim]Found {len(previous_fronts)} previous flashcards for deduplication[/dim]")

        # Generate flashcards
        if args.query:
            # Paired query mode - extract specific info from note based on query
            console.print(f"  [cyan]Extracting info for query:[/cyan] [bold]{args.query}[/bold]")
            flashcards = ai.generate_flashcards_from_note_and_query(note_content, note_title, args.query, target_cards=target_cards_per_note, previous_fronts=previous_fronts)
        else:
            # Normal mode - generate flashcards from note content
            flashcards = ai.generate_flashcards(note_content, note_title, target_cards=target_cards_per_note, previous_fronts=previous_fronts)
        if not flashcards:
            console.print("  [yellow]WARNING:[/yellow] No flashcards generated, skipping")
            continue

        console.print(f"  [green]Generated {len(flashcards)} flashcards[/green]")

        # Flashcard approval (before adding to Anki)
        approved_flashcards = []
        if APPROVE_CARDS:
            try:
                for flashcard in flashcards:
                    if approve_flashcard(flashcard, note_title):
                        approved_flashcards.append(flashcard)
            except KeyboardInterrupt:
                console.print("\n[yellow]Operation cancelled by user[/yellow]")
                return

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

            # Record flashcard creation for density tracking and deduplication
            note_size = len(note_content)
            # Extract fronts from successfully added cards for deduplication
            flashcard_fronts = [card.get('front', '') for card in cards_to_add[:successful_cards] if card.get('front')]
            config.record_flashcards_created(note_path, note_size, successful_cards, flashcard_fronts)
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