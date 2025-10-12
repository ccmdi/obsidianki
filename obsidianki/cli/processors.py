"""
Note processing functions for ObsidianKi.
"""

import concurrent.futures
from typing import List
from obsidianki.cli.handlers import approve_note, approve_flashcard
from obsidianki.cli.models import Note, Flashcard
from obsidianki.cli.services import OBSIDIAN, AI, ANKI


def process(note: Note, args, deck_examples, target_cards_per_note, previous_fronts) -> List[Flashcard]:
    from obsidianki.cli.config import console
    note.ensure_content()

    # Generate flashcards
    if args.query and note.path == "query":
        # Standalone query mode - use direct query generation
        flashcards = AI.generate_from_query(args.query,
                                           target_cards=target_cards_per_note,
                                           previous_fronts=previous_fronts,
                                           deck_examples=deck_examples)
    elif args.query:
        console.print(f"  [cyan]Extracting info for query:[/cyan] [bold]{args.query}[/bold]")
        flashcards = AI.generate_from_note_query(note, args.query,
                                                target_cards=target_cards_per_note,
                                                previous_fronts=previous_fronts,
                                                deck_examples=deck_examples)
    else:
        flashcards = AI.generate_flashcards(note,
                                           target_cards=target_cards_per_note,
                                           previous_fronts=previous_fronts,
                                           deck_examples=deck_examples)

    return flashcards


def postprocess(note: Note, flashcards: List[Flashcard], deck_name: str):
    """Handle flashcard approval and Anki addition"""
    from obsidianki.cli.config import console, CONFIG

    console.print(f"[green]Generated {len(flashcards)} flashcards for {note.filename}[/green]")

    # Flashcard approval
    cards_to_add = flashcards
    if CONFIG.APPROVE_CARDS or CONFIG.PRINT_CARDS:
        approved_flashcards = []
        try:
            console.print(f"\n[blue]Reviewing cards for:[/blue] [bold]{note.filename}[/bold]")
            for flashcard in flashcards:
                if CONFIG.APPROVE_CARDS and approve_flashcard(flashcard, note):
                    approved_flashcards.append(flashcard)
                elif CONFIG.PRINT_CARDS:
                    console.print(f"   [cyan]Front:[/cyan] {flashcard.front}")
                    console.print(f"   [cyan]Back:[/cyan] {flashcard.back}")
                    console.print()
                    approved_flashcards.append(flashcard)
        except KeyboardInterrupt:
            raise

        if not approved_flashcards:
            console.print(f"[yellow]WARNING:[/yellow] No flashcards approved for {note.filename}, skipping")
            return 0

        cards_to_add = approved_flashcards

    result = ANKI.add_flashcards(cards_to_add, deck_name=deck_name, card_type=CONFIG.CARD_TYPE)
    successful_cards = len([r for r in result if r is not None])

    if successful_cards > 0:
        if note.path != "query": #TODO
            flashcard_fronts = [fc.front for fc in cards_to_add[:successful_cards]]
            CONFIG.record_flashcards_created(note, successful_cards, flashcard_fronts)
        return successful_cards
    else:
        console.print(f"[red]ERROR:[/red] Failed to add cards to Anki for {note.filename}")
        return 0

def preprocess(args):
    """
    Entry point for flashcard generation.
    """
    from obsidianki.cli.config import console, CONFIG
    from rich.panel import Panel

    if args.mcp:
        # preprocess
        CONFIG.APPROVE_NOTES = False
        CONFIG.UPFRONT_BATCHING = True

        # postprocess
        CONFIG.APPROVE_CARDS = False
        CONFIG.PRINT_CARDS = True
    else:
        CONFIG.PRINT_CARDS = False

    CONFIG.DECK = args.deck or CONFIG.DECK # --deck
    CONFIG.DENSITY_BIAS_STRENGTH = args.bias or CONFIG.DENSITY_BIAS_STRENGTH # --bias

    if args.notes:
        # When --notes is provided, scale cards to 2 * number of notes (unless --cards also provided)
        if args.cards is not None:
            CONFIG.MAX_CARDS = args.cards
        else:
            CONFIG.MAX_CARDS = len(args.notes) * 2  # Will be updated after we find actual notes
        
        # handle case of --notes <n>
        if len(args.notes) == 1 and args.notes[0].isdigit():
            CONFIG.NOTES_TO_SAMPLE = int(args.notes[0])
    elif args.cards is not None:
        # When --cards is provided, scale notes to 1/2 of cards
        CONFIG.MAX_CARDS = args.cards
        CONFIG.NOTES_TO_SAMPLE = max(1, CONFIG.MAX_CARDS // 2)

    if args.allow:
        CONFIG.SEARCH_FOLDERS = (CONFIG.SEARCH_FOLDERS or []) + args.allow
        console.print(f"[dim]Search folders:[/dim] {', '.join(CONFIG.SEARCH_FOLDERS)}")
        console.print()

    if CONFIG.SAMPLING_MODE == "weighted":
        CONFIG.show_weights()
    console.print()

    if args.query and not args.notes and CONFIG.DEDUPLICATE_VIA_DECK:
        console.print("[yellow]WARNING:[/yellow] DEDUPLICATE_VIA_DECK is experimental and may be expensive for large decks\n")

    # Test connections
    if not OBSIDIAN.test_connection():
        console.print("[red]ERROR:[/red] Cannot connect to Obsidian REST API")
        return 1

    if not ANKI.test_connection():
        console.print("[red]ERROR:[/red] Cannot connect to AnkiConnect")
        return 1

    # === GET NOTES TO PROCESS ===
    notes = None

    if args.query and not args.agent and not args.notes:
        # STANDALONE QUERY MODE - Create synthetic note for main flow
        console.print(f"[cyan]QUERY MODE:[/cyan] [bold]{args.query}[/bold]")
        from obsidianki.cli.models import Note
        query_note = Note(path="query", filename=f"Query: {args.query}", content=args.query, tags=[], size=0)
        notes = [query_note]
        CONFIG.MAX_CARDS = args.cards or CONFIG.MAX_CARDS
        CONFIG.APPROVE_NOTES = False # no need to approve what a user wrote
    elif args.agent:
        console.print(f"[yellow]WARNING:[/yellow] Agent mode is EXPERIMENTAL and may produce unexpected results")
        console.print(f"[cyan]AGENT MODE:[/cyan] [bold]{args.agent}[/bold]")
        notes = AI.find_with_agent(args.agent, sample_size=CONFIG.NOTES_TO_SAMPLE, bias_strength=CONFIG.DENSITY_BIAS_STRENGTH)
        if not notes:
            console.print("[red]ERROR:[/red] Agent found no matching notes")
            return 1

        if args.cards is None:
            CONFIG.MAX_CARDS = len(notes) * 2

    elif args.notes:
        # Handle --notes argument parsing
        if len(args.notes) == 1 and args.notes[0].isdigit():
            # User specified a count: --notes 5
            note_count = int(args.notes[0])
            console.print(f"[cyan]INFO:[/cyan] Sampling {note_count} random notes")
            notes = OBSIDIAN.sample_old_notes(days=CONFIG.DAYS_OLD, limit=note_count, bias_strength=CONFIG.DENSITY_BIAS_STRENGTH, search_folders=CONFIG.SEARCH_FOLDERS)
        else:
            # User specified note names/patterns: --notes "React" "JS"
            notes = []
            for note_pattern in args.notes:
                if '*' in note_pattern or '/' in note_pattern:
                    # Pattern matching with optional sampling
                    sample_size = None
                    if ':' in note_pattern and not note_pattern.endswith('/'):
                        parts = note_pattern.rsplit(':', 1)
                        if parts[1].isdigit():
                            note_pattern = parts[0]
                            sample_size = int(parts[1])
                    
                    pattern_notes = OBSIDIAN.find_by_pattern(note_pattern, sample_size=sample_size, bias_strength=CONFIG.DENSITY_BIAS_STRENGTH, search_folders=CONFIG.SEARCH_FOLDERS)
                    if pattern_notes:
                        notes.extend(pattern_notes)
                        if sample_size and len(pattern_notes) == sample_size:
                            console.print(f"[cyan]INFO:[/cyan] Sampled {len(pattern_notes)} notes from pattern: '{note_pattern}'")
                        else:
                            console.print(f"[cyan]INFO:[/cyan] Found {len(pattern_notes)} notes from pattern: '{note_pattern}'")
                    else:
                        console.print(f"[red]ERROR:[/red] No notes found for pattern: '{note_pattern}'")
                else:
                    specific_note = OBSIDIAN.find_by_name(note_pattern, search_folders=CONFIG.SEARCH_FOLDERS)
                    if specific_note:
                        notes.append(specific_note)
                    else:
                        console.print(f"[red]ERROR:[/red] Not found: '{note_pattern}'")
        
        if not notes:
            console.print("[red]ERROR:[/red] No notes found")
            return 1
    else:
        # Default sampling
        notes = OBSIDIAN.sample_old_notes(days=CONFIG.DAYS_OLD, limit=CONFIG.NOTES_TO_SAMPLE, bias_strength=CONFIG.DENSITY_BIAS_STRENGTH, search_folders=CONFIG.SEARCH_FOLDERS)
        if not notes:
            console.print("[red]ERROR:[/red] No old notes found")
            return 1

    # Show processing info
    if args.query and args.notes:
        console.print(f"[cyan]TARGETED MODE:[/cyan] Extracting '{args.query}' from {len(notes)} note(s)")
    elif not args.query:
        console.print(f"[cyan]INFO:[/cyan] Processing {len(notes)} note(s)")
    console.print(f"[cyan]TARGET:[/cyan] {CONFIG.MAX_CARDS} flashcards maximum")
    console.print()

    # === BATCH MODE DECISION ===
    CONFIG.UPFRONT_BATCHING = CONFIG.UPFRONT_BATCHING and len(notes) > 1
    if CONFIG.UPFRONT_BATCHING:
        if len(notes) > CONFIG.BATCH_SIZE_LIMIT:
            console.print(f"[yellow]WARNING:[/yellow] Batch mode disabled - too many notes ({len(notes)} > {CONFIG.BATCH_SIZE_LIMIT})")
            console.print(f"[yellow]This could result in expensive API costs. Use fewer notes or disable UPFRONT_BATCHING.[/yellow]")
            CONFIG.UPFRONT_BATCHING = False
        elif CONFIG.MAX_CARDS > CONFIG.BATCH_CARD_LIMIT:
            console.print(f"[yellow]WARNING:[/yellow] Batch mode disabled - too many target cards ({CONFIG.MAX_CARDS} > {CONFIG.BATCH_CARD_LIMIT})")
            console.print(f"[yellow]This could result in expensive API costs. Use fewer cards or disable UPFRONT_BATCHING.[/yellow]")
            CONFIG.UPFRONT_BATCHING = False

    target_cards_per_note = max(1, CONFIG.MAX_CARDS // len(notes))

    if args.cards and target_cards_per_note > 5:
        console.print(f"[yellow]WARNING:[/yellow] Requesting more than 5 cards per note can decrease quality")
        console.print(f"[yellow]Consider using fewer total cards or more notes for better results[/yellow]\n")

    # === PROCESS NOTES ===
    deck_examples = []
    CONFIG.USE_DECK_SCHEMA = args.use_schema or CONFIG.USE_DECK_SCHEMA # --use-schema
    if CONFIG.USE_DECK_SCHEMA:
        deck_examples = ANKI.get_card_examples(CONFIG.DECK)
        if deck_examples:
            console.print(f"[dim]Using {len(deck_examples)} example cards for schema enforcement[/dim]")

    previous_fronts = []
    if not args.query and args.notes and CONFIG.DEDUPLICATE_VIA_HISTORY:
        previous_fronts = [note.get_previous_flashcard_fronts() for note in notes]
    elif args.query and not args.notes and CONFIG.DEDUPLICATE_VIA_DECK:
        # For standalone query mode, use deck-based deduplication
        deck_fronts = ANKI.get_card_fronts(CONFIG.DECK)
        if deck_fronts:
            console.print(f"[dim]Found {len(deck_fronts)} existing cards in deck '{CONFIG.DECK}' for deduplication[/dim]")
        previous_fronts = [deck_fronts] * len(notes)  # Same fronts for all notes (just the query note)

    total_cards = 0

    if CONFIG.UPFRONT_BATCHING:
        # PARALLEL MODE
        console.print(f"[cyan]INFO[/cyan]: Batch mode")
        console.print()

        # Filter notes with approval upfront
        valid_notes = []
        for note in notes:
            note.ensure_content()
            console.print(f"\n[blue]PROCESSING:[/blue] {note.filename}")

            if CONFIG.APPROVE_NOTES:
                try:
                    if not approve_note(note):
                        continue
                except KeyboardInterrupt:
                    raise
            valid_notes.append(note)
        
        if not valid_notes:
            console.print("[yellow]WARNING:[/yellow] No notes to process after approval")
            return 0

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            future_to_note: dict[concurrent.futures.Future, Note] = {
                executor.submit(process, note, args, deck_examples, target_cards_per_note, previous_fronts): note
                for note in valid_notes
            }

            for future in concurrent.futures.as_completed(future_to_note):
                note: Note = future_to_note[future]

                try:
                    flashcards = future.result()

                    if not flashcards:
                        console.print(f"[yellow]WARNING:[/yellow] No flashcards generated for {note.filename}")
                        continue

                    cards_added = postprocess(note, flashcards, CONFIG.DECK)
                    total_cards += cards_added

                except Exception as e:
                    console.print(f"[red]ERROR:[/red] Failed to process {note.filename}: {e}")
                    continue
    else:
        # SEQUENTIAL: Process each note one by one
        for i, note in enumerate(notes, 1):
            if total_cards >= CONFIG.MAX_CARDS:
                break

            note.ensure_content()

            console.print(f"\n[blue]PROCESSING:[/blue] {note.filename}")

            if CONFIG.APPROVE_NOTES:
                try:
                    if not approve_note(note):
                        continue
                except KeyboardInterrupt:
                    console.print("\n[yellow]Operation cancelled by user[/yellow]")
                    return 0
            
            try:
                flashcards = process(note, args, deck_examples, target_cards_per_note, previous_fronts)

                if not flashcards:
                    console.print("  [yellow]WARNING:[/yellow] No flashcards generated, skipping")
                    continue

                cards_added = postprocess(note, flashcards, CONFIG.DECK)
                total_cards += cards_added
                
            except KeyboardInterrupt:
                console.print("\n[yellow]Operation cancelled by user[/yellow]")
                return 0

    console.print("")
    console.print(Panel(f"[bold green]COMPLETE![/bold green] Added {total_cards}/{CONFIG.MAX_CARDS} flashcards to deck '{CONFIG.DECK}'", style="green"))
    return 0


