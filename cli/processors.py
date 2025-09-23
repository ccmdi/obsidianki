"""
Note processing functions for ObsidianKi.
"""

import concurrent.futures
from typing import List
from cli.config import console
from cli.handlers import approve_note, approve_flashcard
from cli.models import Note, Flashcard


def generate_flashcards_for_note(note: Note, ai, obsidian, config, args, deck_examples, target_cards_per_note):
    from cli.config import DEDUPLICATE_VIA_HISTORY

    # Ensure note has content loaded
    if not note.content:
        note.content = obsidian.get_note_content(note.path)
        if not note.content:
            return None, None, note.path

    # Get previous flashcard fronts for deduplication
    previous_fronts = []
    if DEDUPLICATE_VIA_HISTORY:
        previous_fronts = note.get_previous_flashcard_fronts(config)

    # Generate flashcards
    if args.query:
        flashcards = ai.generate_from_note_query(note.content, note.filename, args.query,
                                                target_cards=target_cards_per_note,
                                                previous_fronts=previous_fronts,
                                                deck_examples=deck_examples)
    else:
        flashcards = ai.generate_flashcards(note.content, note.filename,
                                           target_cards=target_cards_per_note,
                                           previous_fronts=previous_fronts,
                                           deck_examples=deck_examples)

    return flashcards, note.content, note.path


def process_generated_flashcards(note: Note, flashcards: List[Flashcard], anki, config, args, deck_name, note_content):
    """Handle flashcard approval and Anki addition - shared logic between batch and sequential"""
    from cli.config import APPROVE_CARDS, CARD_TYPE

    console.print(f"[green]Generated {len(flashcards)} flashcards for {note.filename}[/green]")

    # Convert AI response dicts to Flashcard objects
    flashcard_objects = [Flashcard.from_ai_response(fc_data, note) for fc_data in flashcards]

    # Flashcard approval
    cards_to_add = flashcard_objects
    if APPROVE_CARDS:
        approved_flashcards = []
        try:
            console.print(f"\n[blue]Reviewing cards for:[/blue] [bold]{note.filename}[/bold]")
            for flashcard in flashcard_objects:
                if approve_flashcard(flashcard, note.filename):
                    approved_flashcards.append(flashcard)
        except KeyboardInterrupt:
            raise

        if not approved_flashcards:
            console.print(f"[yellow]WARNING:[/yellow] No flashcards approved for {note.filename}, skipping")
            return 0

        console.print(f"[cyan]Approved {len(approved_flashcards)}/{len(flashcard_objects)} flashcards[/cyan]")
        cards_to_add = approved_flashcards

    # Add to Anki directly with Flashcard objects
    result = anki.add_flashcards(cards_to_add, deck_name=deck_name, card_type=CARD_TYPE)
    successful_cards = len([r for r in result if r is not None])

    if successful_cards > 0:
        console.print(f"[green]SUCCESS:[/green] Added {successful_cards} cards to Anki for {note.filename}")

        # Record flashcard creation
        flashcard_fronts = [fc.front for fc in cards_to_add[:successful_cards]]
        config.record_flashcards_created(note.path, note.size, successful_cards, flashcard_fronts)
        return successful_cards
    else:
        console.print(f"[red]ERROR:[/red] Failed to add cards to Anki for {note.filename}")
        return 0


def process_flashcard_generation(args, config, obsidian, ai, anki, deck_name, max_cards, notes_to_sample):
    """
    CENTRAL AUTHORITY for ALL flashcard processing scenarios.
    All config checks happen here ONCE. No duplication of config logic anywhere.
    """
    from cli.config import (
        MAX_CARDS, NOTES_TO_SAMPLE, DAYS_OLD, SAMPLING_MODE, CARD_TYPE, 
        APPROVE_NOTES, APPROVE_CARDS, DEDUPLICATE_VIA_HISTORY, DEDUPLICATE_VIA_DECK, 
        USE_DECK_SCHEMA, DECK, SEARCH_FOLDERS, UPFRONT_BATCHING, BATCH_SIZE_LIMIT, BATCH_CARD_LIMIT,
        DENSITY_BIAS_STRENGTH
    )
    from rich.panel import Panel

    # CENTRALIZED: Get effective bias strength (CLI override or config default)
    effective_bias_strength = args.bias if args.bias is not None else DENSITY_BIAS_STRENGTH

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
        config.show_weights()
    console.print()

    # CENTRALIZED CONFIG CHECK: Show warning for experimental features
    if args.query and not args.notes and DEDUPLICATE_VIA_DECK:
        console.print("[yellow]WARNING:[/yellow] DEDUPLICATE_VIA_DECK is experimental and may be expensive for large decks\n")

    # Test connections
    if not obsidian.test_connection():
        console.print("[red]ERROR:[/red] Cannot connect to Obsidian REST API")
        return 0

    if not anki.test_connection():
        console.print("[red]ERROR:[/red] Cannot connect to AnkiConnect")
        return 0

    # === STANDALONE QUERY MODE ===
    if args.query and not args.agent and not args.notes:
        console.print(f"[cyan]QUERY MODE:[/cyan] [bold]{args.query}[/bold]")

        # Get previous flashcard fronts for deduplication if enabled
        previous_fronts = []
        if DEDUPLICATE_VIA_DECK:
            previous_fronts = anki.get_card_fronts(deck_name)
            if previous_fronts:
                console.print(f"[dim]Found {len(previous_fronts)} existing cards in deck '{deck_name}' for deduplication[/dim]\n")

        # Get deck examples for schema enforcement if enabled
        deck_examples = []
        use_schema = args.use_schema if hasattr(args, 'use_schema') else USE_DECK_SCHEMA
        if use_schema:
            deck_examples = anki.get_card_examples(deck_name)
            if deck_examples:
                console.print(f"[dim]Found {len(deck_examples)} example cards from deck '{deck_name}' for schema enforcement[/dim]")

        target_cards = args.cards if args.cards else None
        flashcards = ai.generate_from_query(args.query, target_cards=target_cards, previous_fronts=previous_fronts, deck_examples=deck_examples)
        if not flashcards:
            console.print("[red]ERROR:[/red] No flashcards generated from query")
            return 0

        console.print(f"[green]Generated {len(flashcards)} flashcards[/green]")

        # Flashcard approval
        if APPROVE_CARDS:
            approved_flashcards = []
            try:
                for flashcard in flashcards:
                    if approve_flashcard(flashcard, f"Query: {args.query}"):
                        approved_flashcards.append(flashcard)
            except KeyboardInterrupt:
                console.print("\n[yellow]Operation cancelled by user[/yellow]")
                return 0

            if not approved_flashcards:
                console.print("[yellow]WARNING:[/yellow] No flashcards approved")
                return 0

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
        return successful_cards

    # === GET NOTES TO PROCESS ===
    old_notes = None
    
    if args.agent:
        console.print(f"[yellow]WARNING:[/yellow] Agent mode is EXPERIMENTAL and may produce unexpected results")
        console.print(f"[cyan]AGENT MODE:[/cyan] [bold]{args.agent}[/bold]")
        old_notes = ai.find_with_agent(args.agent, obsidian, config_manager=config, sample_size=notes_to_sample, bias_strength=effective_bias_strength, search_folders=effective_search_folders)
        if not old_notes:
            console.print("[red]ERROR:[/red] Agent found no matching notes")
            return 0
        # Update max_cards based on found notes (if --cards wasn't specified)
        if args.cards is None:
            max_cards = len(old_notes) * 2

    elif args.notes:
        # Handle --notes argument parsing
        if len(args.notes) == 1 and args.notes[0].isdigit():
            # User specified a count: --notes 5
            note_count = int(args.notes[0])
            console.print(f"[cyan]INFO:[/cyan] Sampling {note_count} random notes")
            old_notes = obsidian.sample_old_notes(days=DAYS_OLD, limit=note_count, config_manager=config, bias_strength=effective_bias_strength)
        else:
            # User specified note names/patterns: --notes "React" "JS"
            old_notes = []
            for note_pattern in args.notes:
                if '*' in note_pattern or '/' in note_pattern:
                    # Pattern matching with optional sampling
                    sample_size = None
                    if ':' in note_pattern and not note_pattern.endswith('/'):
                        parts = note_pattern.rsplit(':', 1)
                        if parts[1].isdigit():
                            note_pattern = parts[0]
                            sample_size = int(parts[1])
                    
                    pattern_notes = obsidian.find_by_pattern(note_pattern, config_manager=config, sample_size=sample_size, bias_strength=effective_bias_strength)
                    if pattern_notes:
                        old_notes.extend(pattern_notes)
                        if sample_size and len(pattern_notes) == sample_size:
                            console.print(f"[cyan]INFO:[/cyan] Sampled {len(pattern_notes)} notes from pattern: '{note_pattern}'")
                        else:
                            console.print(f"[cyan]INFO:[/cyan] Found {len(pattern_notes)} notes from pattern: '{note_pattern}'")
                    else:
                        console.print(f"[red]ERROR:[/red] No notes found for pattern: '{note_pattern}'")
                else:
                    # Single note lookup
                    specific_note = obsidian.find_by_name(note_pattern, config_manager=config)
                    if specific_note:
                        old_notes.append(specific_note)
                    else:
                        console.print(f"[red]ERROR:[/red] Not found: '{note_pattern}'")
        
        if not old_notes:
            console.print("[red]ERROR:[/red] No notes found")
            return 0
        
        # Update max_cards based on actually found notes (if --cards wasn't specified)
        if args.cards is None:
            max_cards = len(old_notes) * 2
    else:
        # Default sampling
        if args.allow:
            console.print("[yellow]Note:[/yellow] --allow flag only works with --agent mode currently")
        old_notes = obsidian.sample_old_notes(days=DAYS_OLD, limit=notes_to_sample, config_manager=config, bias_strength=effective_bias_strength)
        if not old_notes:
            console.print("[red]ERROR:[/red] No old notes found")
            return 0

    # Show processing info
    if args.query:
        console.print(f"[cyan]TARGETED MODE:[/cyan] Extracting '{args.query}' from {len(old_notes)} note(s)")
    else:
        console.print(f"[cyan]INFO:[/cyan] Processing {len(old_notes)} note(s)")
    console.print(f"[cyan]TARGET:[/cyan] {max_cards} flashcards maximum")
    console.print()

    # === BATCH MODE DECISION ===
    use_batch_mode = UPFRONT_BATCHING and len(old_notes) > 1
    if use_batch_mode:
        if len(old_notes) > BATCH_SIZE_LIMIT:
            console.print(f"[yellow]WARNING:[/yellow] Batch mode disabled - too many notes ({len(old_notes)} > {BATCH_SIZE_LIMIT})")
            console.print(f"[yellow]This could result in expensive API costs. Use fewer notes or disable UPFRONT_BATCHING.[/yellow]")
            use_batch_mode = False
        elif max_cards > BATCH_CARD_LIMIT:
            console.print(f"[yellow]WARNING:[/yellow] Batch mode disabled - too many target cards ({max_cards} > {BATCH_CARD_LIMIT})")
            console.print(f"[yellow]This could result in expensive API costs. Use fewer cards or disable UPFRONT_BATCHING.[/yellow]")
            use_batch_mode = False
        elif use_batch_mode:
            console.print(f"[cyan]BATCH MODE:[/cyan] Processing {len(old_notes)} notes in parallel")
            console.print()

    # Calculate target cards per note
    target_cards_per_note = max(1, max_cards // len(old_notes)) if args.cards else None

    if args.cards and target_cards_per_note > 5:
        console.print(f"[yellow]WARNING:[/yellow] Requesting more than 5 cards per note can decrease quality")
        console.print(f"[yellow]Consider using fewer total cards or more notes for better results[/yellow]\n")

    # === PROCESS NOTES ===
    # Get deck examples once (shared across all notes)
    deck_examples = []
    use_schema = args.use_schema if hasattr(args, 'use_schema') else USE_DECK_SCHEMA
    if use_schema:
        deck_examples = anki.get_card_examples(deck_name)
        if deck_examples:
            console.print(f"[dim]Using {len(deck_examples)} example cards for schema enforcement[/dim]")

    total_cards = 0

    if use_batch_mode:
        # BATCH: Parallelize AI generation, then sequential approval/Anki
        console.print(f"[cyan]Parallelizing AI generation for {len(old_notes)} notes...[/cyan]")

        # Filter notes with approval upfront (old_notes are already Note objects)
        valid_notes = []
        for note in old_notes:
            # Ensure note has content loaded
            if not note.content:
                note.content = obsidian.get_note_content(note.path)
                if not note.content:
                    continue

            if APPROVE_NOTES:
                try:
                    if not approve_note(note.filename, note.path):
                        continue
                except KeyboardInterrupt:
                    raise
            valid_notes.append(note)
        
        if not valid_notes:
            console.print("[yellow]WARNING:[/yellow] No notes to process after approval")
            return 0

        # Parallelize ONLY the AI generation step using futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            future_to_note = {
                executor.submit(generate_flashcards_for_note, note, ai, obsidian, config, args, deck_examples, target_cards_per_note): note
                for note in valid_notes
            }

            # Process results as they complete
            for future in concurrent.futures.as_completed(future_to_note):
                note = future_to_note[future]

                try:
                    flashcards, note_content, note_path = future.result()

                    if not flashcards or not note_content:
                        console.print(f"[yellow]WARNING:[/yellow] No flashcards generated for {note.filename}")
                        continue

                    # Use sequential logic for approval and Anki
                    cards_added = process_generated_flashcards(note, flashcards, anki, config, args, deck_name, note_content)
                    total_cards += cards_added

                except Exception as e:
                    console.print(f"[red]ERROR:[/red] Failed to process {note.filename}: {e}")
                    continue
    else:
        # SEQUENTIAL: Process each note one by one (old_notes are already Note objects)
        for i, note in enumerate(old_notes, 1):
            if total_cards >= max_cards:
                break

            # Ensure note has content loaded
            if not note.content:
                note.content = obsidian.get_note_content(note.path)
                if not note.content:
                    continue

            console.print(f"\n[blue]PROCESSING:[/blue] {note.filename}")

            # Note approval
            if APPROVE_NOTES:
                try:
                    if not approve_note(note.filename, note.path):
                        continue
                except KeyboardInterrupt:
                    console.print("\n[yellow]Operation cancelled by user[/yellow]")
                    return total_cards

            # Generate flashcards
            if args.query:
                console.print(f"  [cyan]Extracting info for query:[/cyan] [bold]{args.query}[/bold]")
            
            try:
                flashcards, note_content, _ = generate_flashcards_for_note(note, ai, obsidian, config, args, deck_examples, target_cards_per_note)
                
                if not flashcards or not note_content:
                    console.print("  [yellow]WARNING:[/yellow] No flashcards generated, skipping")
                    continue

                # Use shared logic for approval and Anki addition
                cards_added = process_generated_flashcards(note, flashcards, anki, config, args, deck_name, note_content)
                total_cards += cards_added
                
            except KeyboardInterrupt:
                console.print("\n[yellow]Operation cancelled by user[/yellow]")
                return total_cards

    console.print("")
    console.print(Panel(f"[bold green]COMPLETE![/bold green] Added {total_cards}/{max_cards} flashcards to your Obsidian deck", style="green"))
    return total_cards
