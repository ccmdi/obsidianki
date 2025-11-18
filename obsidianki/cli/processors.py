"""
Note processing functions for ObsidianKi.
"""

import concurrent.futures
import argparse
from typing import List, Dict
from obsidianki.cli.interactive.approval import approve_note, approve_flashcard
from obsidianki.cli.models import Note, Flashcard, NotePattern
from obsidianki.cli.services import OBSIDIAN, AI, ANKI
from obsidianki.cli.utils import encode_path

#TODO
# deck_examples -> List[Flashcard]
# previous_fronts -> List[Flashcard]?
def process(note: Note, args: argparse.Namespace, deck_examples: List[Dict[str, str]], target_cards_per_note: int, previous_fronts: List[str]) -> List[Flashcard]:
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

    # Flashcard approval
    cards_to_add = flashcards
    if CONFIG.approve_cards or CONFIG.print_cards:
        approved_flashcards = []
        try:
            for flashcard in flashcards:
                if CONFIG.approve_cards and approve_flashcard(flashcard):
                    approved_flashcards.append(flashcard)
                elif CONFIG.print_cards:
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

    result = ANKI.add_flashcards(cards_to_add, deck_name=deck_name, card_type=CONFIG.card_type)
    successful_cards = len([r for r in result if r is not None])

    if successful_cards > 0:
        if note.path != "query": #TODO
            flashcard_fronts = [fc.front for fc in cards_to_add[:successful_cards]]
            CONFIG.record_flashcards_created(note, successful_cards, flashcard_fronts)
        return successful_cards
    else:
        console.print(f"[red]ERROR:[/red] Failed to add cards to Anki for {note.filename}")
        return 0

def preprocess(args: argparse.Namespace):
    """
    Entry point for flashcard generation.
    """
    from obsidianki.cli.config import console, CONFIG
    from rich.panel import Panel

    if args.mcp:
        # preprocess
        CONFIG.approve_notes = False
        CONFIG.upfront_batching = True

        # postprocess
        CONFIG.approve_cards = False
        CONFIG.print_cards = True
    else:
        CONFIG.print_cards = False

    CONFIG.deck = args.deck or CONFIG.deck # --deck
    CONFIG.density_bias_strength = args.bias or CONFIG.density_bias_strength # --bias
    CONFIG.use_extrapolation = args.extrapolate # --extrapolate
    CONFIG.difficulty = args.difficulty or CONFIG.difficulty # --difficulty

    if args.notes:
        # When --notes is provided, scale cards to 2 * number of notes (unless --cards also provided)
        if args.cards is not None:
            CONFIG.max_cards = args.cards
        else:
            CONFIG.max_cards = len(args.notes) * 2  # Will be updated after we find actual notes

        # handle case of --notes <n>
        if len(args.notes) == 1 and args.notes[0].isdigit():
            CONFIG.notes_to_sample = int(args.notes[0])
    elif args.cards is not None:
        # When --cards is provided, scale notes to 1/2 of cards
        CONFIG.max_cards = args.cards
        CONFIG.notes_to_sample = max(1, CONFIG.max_cards // 2)

    if args.allow:
        CONFIG.search_folders = (CONFIG.search_folders or []) + args.allow
        console.print(f"[dim]Search folders:[/dim] {', '.join(CONFIG.search_folders)}")
        console.print()

    if CONFIG.sampling_mode == "weighted":
        CONFIG.show_weights()
    console.print()

    if args.query and not args.notes and CONFIG.deduplicate_via_deck:
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
        # STANDALONE QUERY MODE
        console.print(f"[cyan]QUERY MODE:[/cyan] [bold]{args.query}[/bold]")
        from obsidianki.cli.models import Note
        query_note = Note(path="query", filename=f"Query: {args.query}", content=args.query, tags=[], size=0)
        notes = [query_note]

        CONFIG.max_cards = args.cards or CONFIG.max_cards
        CONFIG.approve_notes = False # no need to approve what a user wrote
    elif args.agent:
        console.print(f"[yellow]WARNING:[/yellow] Agent mode is EXPERIMENTAL and may produce unexpected results")
        console.print(f"[cyan]AGENT MODE:[/cyan] [bold]{args.agent}[/bold]")
        notes = AI.find_with_agent(args.agent, sample_size=CONFIG.notes_to_sample, bias_strength=CONFIG.density_bias_strength)
        if not notes:
            console.print("[red]ERROR:[/red] Agent found no matching notes")
            return 1

        CONFIG.max_cards = args.cards or len(notes) * 2

    elif args.notes:
        if len(args.notes) == 1 and args.notes[0].isdigit():
            # User specified a count: --notes 5
            note_count = int(args.notes[0])
            console.print(f"[cyan]INFO:[/cyan] Sampling {note_count} random notes")

        notes = []
        for pattern_str in args.notes:
            pattern = NotePattern(
                pattern_str,
                bias_strength=CONFIG.density_bias_strength,
                search_folders=CONFIG.search_folders
            )
            pattern_notes = pattern.resolve()

            if pattern_notes:
                notes.extend(pattern_notes)

                if pattern.sample_size and len(pattern_notes) == pattern.sample_size:
                    console.print(f"[cyan]INFO:[/cyan] Sampled {len(pattern_notes)} notes from pattern: '{pattern_str}'")
                elif pattern.is_wildcard:
                    console.print(f"[cyan]INFO:[/cyan] Found {len(pattern_notes)} notes from pattern: '{pattern_str}'")
            else:
                console.print(f"[red]ERROR:[/red] No notes found for pattern: '{pattern_str}'")

        if not notes:
            console.print("[red]ERROR:[/red] No notes found")
            return 1
    else:
        # Default sampling
        notes = OBSIDIAN.sample_old_notes(days=CONFIG.days_old, limit=CONFIG.notes_to_sample, bias_strength=CONFIG.density_bias_strength, search_folders=CONFIG.search_folders)
        if not notes:
            console.print("[red]ERROR:[/red] No old notes found")
            return 1

    # Show processing info
    if args.query and args.notes:
        console.print(f"[cyan]TARGETED MODE:[/cyan] Extracting '{args.query}' from {len(notes)} note(s)")
    elif not args.query:
        console.print(f"[cyan]INFO:[/cyan] Processing {len(notes)} note(s)")
    console.print(f"[cyan]TARGET:[/cyan] {CONFIG.max_cards} flashcards maximum")
    console.print()

    # === BATCH MODE DECISION ===
    CONFIG.upfront_batching = CONFIG.upfront_batching and len(notes) > 1
    if CONFIG.upfront_batching:
        if len(notes) > CONFIG.batch_size_limit:
            console.print(f"[yellow]WARNING:[/yellow] Batch mode disabled - too many notes ({len(notes)} > {CONFIG.batch_size_limit})")
            console.print(f"[yellow]This could result in expensive API costs. Use fewer notes or disable UPFRONT_BATCHING.[/yellow]")
            CONFIG.upfront_batching = False
        elif CONFIG.max_cards > CONFIG.batch_card_limit:
            console.print(f"[yellow]WARNING:[/yellow] Batch mode disabled - too many target cards ({CONFIG.max_cards} > {CONFIG.batch_card_limit})")
            console.print(f"[yellow]This could result in expensive API costs. Use fewer cards or disable UPFRONT_BATCHING.[/yellow]")
            CONFIG.upfront_batching = False

    target_cards_per_note = max(1, CONFIG.max_cards // len(notes))

    if args.cards and target_cards_per_note > 5:
        console.print(f"[yellow]WARNING:[/yellow] Requesting more than 5 cards per note can decrease quality")
        console.print(f"[yellow]Consider using fewer total cards or more notes for better results[/yellow]\n")

    # === PROCESS NOTES ===
    deck_examples = []
    use_schema_value = args.use_schema
    CONFIG.use_deck_schema = bool(use_schema_value) or CONFIG.use_deck_schema

    if CONFIG.use_deck_schema:
        # If use_schema is a string (pattern), resolve it to note paths
        note_paths = []
        if isinstance(use_schema_value, str):
            pattern = NotePattern(
                use_schema_value,
                bias_strength=CONFIG.density_bias_strength,
                search_folders=CONFIG.search_folders
            )
            schema_notes = pattern.resolve()
            if schema_notes:
                # we encode because we compare with the messy "origin" field
                note_paths = [encode_path(note.path) for note in schema_notes]
            else:
                console.print(f"[yellow]WARNING:[/yellow] No notes found for schema pattern '{use_schema_value}', using entire deck")

        deck_examples = ANKI.get_card_examples(CONFIG.deck, note_paths=note_paths)
        if deck_examples:
            console.print(f"[dim]Using {len(deck_examples)} example cards for schema enforcement[/dim]")

    previous_fronts = []
    if not args.query and args.notes and CONFIG.deduplicate_via_history:
        previous_fronts = [note.get_previous_flashcard_fronts() for note in notes]
    elif args.query and not args.notes and CONFIG.deduplicate_via_deck:
        # For standalone query mode, use deck-based deduplication
        deck_fronts = ANKI.get_card_fronts(CONFIG.deck)
        if deck_fronts:
            console.print(f"[dim]Found {len(deck_fronts)} existing cards in deck '{CONFIG.deck}' for deduplication[/dim]")
        previous_fronts = [deck_fronts] * len(notes)  # Same fronts for all notes (just the query note)

    total_cards = 0

    if CONFIG.upfront_batching:
        # PARALLEL MODE
        console.print(f"[cyan]INFO[/cyan]: Batch mode")
        console.print()

        valid_notes = []
        for note in notes:
            note.ensure_content()
            console.print(f"\n[blue]PROCESSING:[/blue] {note.filename}")

            if CONFIG.approve_notes:
                try:
                    if not approve_note(note):
                        continue
                except KeyboardInterrupt:
                    raise

            console.print("   ", end="")  # Indent cursor position
            valid_notes.append(note)
        
        if not valid_notes:
            console.print("[yellow]WARNING:[/yellow] No notes to process after approval")
            return 0

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            future_to_note: dict[concurrent.futures.Future, Note] = {
                executor.submit(process, note, args, deck_examples, target_cards_per_note, previous_fronts[i] if previous_fronts else []): note
                for i, note in enumerate(valid_notes)
            }

            for future in concurrent.futures.as_completed(future_to_note):
                note: Note = future_to_note[future]

                try:
                    flashcards = future.result()
                    console.print()  # Clear the indented cursor line

                    if not flashcards:
                        console.print(f"[yellow]WARNING:[/yellow] No flashcards generated for {note.filename}")
                        continue

                    cards_added = postprocess(note, flashcards, CONFIG.deck)
                    total_cards += cards_added

                except Exception as e:
                    console.print(f"[red]ERROR:[/red] Failed to process {note.filename}: {e}")
                    continue
    else:
        # SEQUENTIAL: Process each note one by one
        for i, note in enumerate(notes, 1):
            if total_cards >= CONFIG.max_cards:
                break

            note.ensure_content()

            console.print(f"\n[blue]PROCESSING:[/blue] {note.filename}")

            if CONFIG.approve_notes:
                try:
                    if not approve_note(note):
                        continue
                except KeyboardInterrupt:
                    console.print("\n[yellow]Operation cancelled by user[/yellow]")
                    return 0

            console.print("   ", end="")  # Indent cursor position
            try:
                flashcards = process(note, args, deck_examples, target_cards_per_note, previous_fronts[i-1] if previous_fronts else [])
                console.print()  # Clear the indented cursor line

                if not flashcards:
                    console.print("  [yellow]WARNING:[/yellow] No flashcards generated, skipping")
                    continue

                cards_added = postprocess(note, flashcards, CONFIG.deck)
                total_cards += cards_added

            except KeyboardInterrupt:
                console.print("\n[yellow]Operation cancelled by user[/yellow]")
                return 0

    console.print("")
    console.print(Panel(f"[bold green]COMPLETE![/bold green] Added {total_cards}/{CONFIG.max_cards} flashcards to deck '{CONFIG.deck}'", style="green"))
    return 0


