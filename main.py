import argparse
import os
from pathlib import Path
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.text import Text

from cli.config import console, CONFIG_DIR, ENV_FILE, CONFIG_FILE
from cli.handlers import handle_config_command, handle_tag_command, handle_history_command

def show_main_help():
    """Display the main help screen"""
    console.print(Panel(
        Text("ObsidianKi - Generate flashcards from Obsidian notes", style="bold blue"),
        style="blue"
    ))
    console.print()

    console.print("[bold blue]Usage[/bold blue]")
    console.print("  [cyan]oki[/cyan] [options]")
    console.print("  [cyan]oki[/cyan] <command> [command-options]")
    console.print()

    console.print("[bold blue]Main Options[/bold blue]")
    console.print("  [cyan]-S, --setup[/cyan]           Run interactive setup")
    console.print("  [cyan]-c, --cards <n>[/cyan]       Set target card limit")
    console.print("  [cyan]-n, --notes <patterns>[/cyan] Process specific notes or directory patterns")
    console.print("  [cyan]-q, --query <text>[/cyan]    Generate cards from query, e.g. \"do X\"")
    console.print("  [cyan]-a, --agent <request>[/cyan] Agent mode: natural language note discovery")
    console.print("  [cyan]-d, --deck <name>[/cyan]     Anki deck to add cards to")
    console.print("  [cyan]-s, --sample <n>[/cyan]      Sample N notes (directory patterns only)")
    console.print("  [cyan]-b, --bias <float>[/cyan]    Note density bias (0-1)")
    console.print("  [cyan]-w, --allow <folders>[/cyan] Temporarily expand search to additional folders")
    console.print("  [cyan]-u, --use-schema[/cyan]      Use existing deck cards as formatting examples")
    console.print()

    console.print("[bold blue]Commands[/bold blue]")
    console.print("  [cyan]config[/cyan]                Manage configuration")
    console.print("  [cyan]tag[/cyan]                   Manage tag weights")
    console.print("  [cyan]history[/cyan]               Manage processing history")
    console.print()

def main():
    parser = argparse.ArgumentParser(description="Generate flashcards from Obsidian notes", add_help=False)
    parser.add_argument("-h", "--help", action="store_true", help="Show help message")
    parser.add_argument("-S", "--setup", action="store_true", help="Run interactive setup to configure API keys")
    parser.add_argument("-c", "--cards", type=int, help="Override max card limit")
    parser.add_argument("-n", "--notes", nargs='+', help="Process specific notes by name or directory patterns")
    parser.add_argument("-q", "--query", type=str, help="Generate cards from standalone query or extract specific info from notes")
    parser.add_argument("-a", "--agent", type=str, help="Agent mode: natural language note discovery using DQL queries")
    parser.add_argument("-d", "--deck", type=str, help="Anki deck to add cards to")
    parser.add_argument("-s", "--sample", type=int, help="When using directory patterns, randomly sample this many notes from matching directories")
    parser.add_argument("-b", "--bias", type=float, help="Override density bias strength (0=no bias, 1=maximum bias against over-processed notes)")
    parser.add_argument("-w", "--allow", nargs='+', help="Temporarily add folders to SEARCH_FOLDERS for this run")
    parser.add_argument("-u", "--use-schema", action="store_true", help="Sample existing cards from deck to enforce consistent formatting/style")

    # Config management subparser
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    config_parser = subparsers.add_parser('config', help='Manage configuration', add_help=False)
    config_parser.add_argument("-h", "--help", action="store_true", help="Show help message")
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
    history_parser = subparsers.add_parser('history', help='Manage processing history', add_help=False)
    history_parser.add_argument("-h", "--help", action="store_true", help="Show help message")
    history_subparsers = history_parser.add_subparsers(dest='history_action', help='History actions')

    # history clear
    clear_parser = history_subparsers.add_parser('clear', help='Clear processing history')
    clear_parser.add_argument('--notes', nargs='+', help='Clear history for specific notes only (patterns supported)')

    # history stats
    history_subparsers.add_parser('stats', help='Show flashcard generation statistics')

    # Tag management
    tag_parser = subparsers.add_parser('tag', help='Manage tag weights', add_help=False)
    tag_parser.add_argument("-h", "--help", action="store_true", help="Show help message")
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

    # Handle help requests
    if hasattr(args, 'help') and args.help:
        if not args.command:
            show_main_help()
            return
        # For subcommands, pass the help flag through to their handlers
        # The handlers will detect it and show their custom help

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
            from cli.wizard import setup
            setup(force_full_setup=args.setup)
        except KeyboardInterrupt:
            console.print("\n[yellow]Setup cancelled by user[/yellow]")
        return

    # Lazy import heavy dependencies only when needed for flashcard generation
    from api.obsidian import ObsidianAPI
    from ai.client import FlashcardAI
    from api.anki import AnkiAPI
    from cli.config import ConfigManager, MAX_CARDS, NOTES_TO_SAMPLE, DAYS_OLD, SAMPLING_MODE, CARD_TYPE, APPROVE_NOTES, APPROVE_CARDS, DEDUPLICATE_VIA_HISTORY, DEDUPLICATE_VIA_DECK, USE_DECK_SCHEMA, DECK, SEARCH_FOLDERS
    from cli.handlers import approve_note, approve_flashcard

    # Set deck from CLI argument or config default
    deck_name = args.deck if args.deck else DECK

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

    # Initialize APIs and config
    config = ConfigManager()
    obsidian = ObsidianAPI()
    ai = FlashcardAI()
    anki = AnkiAPI()

    # Handle --allow flag: expand SEARCH_FOLDERS for this run
    effective_search_folders = SEARCH_FOLDERS
    if args.allow:
        if effective_search_folders:
            effective_search_folders = list(effective_search_folders) + args.allow
        else:
            effective_search_folders = args.allow
        console.print(f"[dim]Effective search folders:[/dim] {', '.join(effective_search_folders)}")
        console.print()

    if SAMPLING_MODE == "weighted":
        config.show_current_weights()
    
    console.print()

    # Show warning for experimental features
    if args.query and not args.notes and DEDUPLICATE_VIA_DECK:
        console.print("[yellow]WARNING:[/yellow] DEDUPLICATE_VIA_DECK is experimental and may be expensive for large decks\n")

    # Test connections
    if not obsidian.test_connection():
        console.print("[red]ERROR:[/red] Cannot connect to Obsidian REST API")
        return

    if not anki.test_connection():
        console.print("[red]ERROR:[/red] Cannot connect to AnkiConnect")
        return

    # Handle query mode
    if args.query and not args.agent:
        if not args.notes:
            # Standalone query mode - generate cards from query alone
            console.print(f"[cyan]QUERY MODE:[/cyan] [bold]{args.query}[/bold]")

            # Get previous flashcard fronts for deduplication if enabled
            previous_fronts = []
            if DEDUPLICATE_VIA_DECK:
                previous_fronts = anki.get_deck_card_fronts(deck_name)
                if previous_fronts:
                    console.print(f"[dim]Found {len(previous_fronts)} existing cards in deck '{deck_name}' for deduplication[/dim]\n")

            # Get deck examples for schema enforcement if enabled
            deck_examples = []
            use_schema = args.use_schema if hasattr(args, 'use_schema') else USE_DECK_SCHEMA
            if use_schema:
                deck_examples = anki.get_deck_card_examples(deck_name)
                if deck_examples:
                    console.print(f"[dim]Found {len(deck_examples)} example cards from deck '{deck_name}' for schema enforcement[/dim]")
                    # console.print(f"[dim]Example fronts: {[ex['front'][:50] + '...' if len(ex['front']) > 50 else ex['front'] for ex in deck_examples]}[/dim]\n")

            target_cards = args.cards if args.cards else None
            flashcards = ai.generate_flashcards_from_query(args.query, target_cards=target_cards, previous_fronts=previous_fronts, deck_examples=deck_examples)
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
            result = anki.add_flashcards(cards_to_add, deck_name=deck_name, card_type=CARD_TYPE,
                                       note_path="query", note_title=f"Query: {args.query}")
            successful_cards = len([r for r in result if r is not None])

            if successful_cards > 0:
                console.print(f"[green]SUCCESS:[/green] Added {successful_cards} cards to Anki")
            else:
                console.print("[red]ERROR:[/red] Failed to add cards to Anki")

            console.print(f"\n[bold green]COMPLETE![/bold green] Added {successful_cards} flashcards from query")
            return

    # Handle agent mode
    if args.agent:
        console.print(f"[cyan]AGENT MODE:[/cyan] [bold]{args.agent}[/bold]")

        # Use agent to find notes
        agent_notes = ai.find_notes_with_agent(args.agent, obsidian, config_manager=config, sample_size=args.sample or notes_to_sample, bias_strength=args.bias, search_folders=effective_search_folders)

        if not agent_notes:
            console.print("[red]ERROR:[/red] Agent found no matching notes")
            return

        old_notes = agent_notes

        # Update max_cards based on found notes (if --cards wasn't specified)
        if args.cards is None:
            max_cards = len(old_notes) * 2

        if args.query:
            console.print(f"[cyan]TARGETED MODE:[/cyan] Extracting '{args.query}' from {len(old_notes)} AI-discovered note(s)")
            console.print(f"[cyan]TARGET:[/cyan] {max_cards} flashcards maximum")
        else:
            console.print(f"[cyan]INFO:[/cyan] Processing {len(old_notes)} AI-discovered note(s)")
            console.print(f"[cyan]TARGET:[/cyan] {max_cards} flashcards maximum")
        console.print()

    # Get notes to process
    elif args.notes:
        old_notes = []

        for note_pattern in args.notes:
            # Check if this looks like a directory pattern
            if '*' in note_pattern or '/' in note_pattern:
                # Use pattern matching with optional sampling
                pattern_notes = obsidian.find_notes_by_pattern(note_pattern, config_manager=config, sample_size=args.sample, bias_strength=args.bias)

                if pattern_notes:
                    old_notes.extend(pattern_notes)
                    if args.sample and len(pattern_notes) == args.sample:
                        console.print(f"[cyan]INFO:[/cyan] Sampled {len(pattern_notes)} notes from pattern: '{note_pattern}'")
                    else:
                        console.print(f"[cyan]INFO:[/cyan] Found {len(pattern_notes)} notes from pattern: '{note_pattern}'")
                else:
                    console.print(f"[red]ERROR:[/red] No notes found for pattern: '{note_pattern}'")
            else:
                # Use existing single note lookup
                specific_note = obsidian.find_note_by_name(note_pattern, config_manager=config)

                if specific_note:
                    old_notes.append(specific_note)
                else:
                    console.print(f"[red]ERROR:[/red] Not found: '{note_pattern}'")

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
        # For now, --allow only works with agent mode due to obsidian.py global dependencies
        if args.allow:
            console.print("[yellow]Note:[/yellow] --allow flag only works with --agent mode currently")

        old_notes = obsidian.get_random_old_notes(days=DAYS_OLD, limit=notes_to_sample, config_manager=config, bias_strength=args.bias)

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

        # Get deck examples for schema enforcement if enabled
        deck_examples = []
        use_schema = args.use_schema if hasattr(args, 'use_schema') else USE_DECK_SCHEMA
        if use_schema:
            deck_examples = anki.get_deck_card_examples(deck_name)
            if deck_examples:
                console.print(f"  [dim]Using {len(deck_examples)} example cards for schema enforcement[/dim]")
                console.print(f"  [dim]Example fronts: {[ex['front'][:50] + '...' if len(ex['front']) > 50 else ex['front'] for ex in deck_examples]}[/dim]")

        # Generate flashcards
        if args.query:
            # Paired query mode - extract specific info from note based on query
            console.print(f"  [cyan]Extracting info for query:[/cyan] [bold]{args.query}[/bold]")
            flashcards = ai.generate_flashcards_from_note_and_query(note_content, note_title, args.query, target_cards=target_cards_per_note, previous_fronts=previous_fronts, deck_examples=deck_examples)
        else:
            # Normal mode - generate flashcards from note content
            flashcards = ai.generate_flashcards(note_content, note_title, target_cards=target_cards_per_note, previous_fronts=previous_fronts, deck_examples=deck_examples)
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
        result = anki.add_flashcards(cards_to_add, deck_name=deck_name, card_type=CARD_TYPE,
                                   note_path=note_path, note_title=note_title)
        successful_cards = len([r for r in result if r is not None])

        if successful_cards > 0:
            # console.print(f"  [green]SUCCESS:[/green] Added {successful_cards} cards to Anki")
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