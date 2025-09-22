"""
Note processing functions for ObsidianKi.
Handles both sequential and batch processing of notes.
"""

from cli.config import console
from cli.handlers import approve_note, approve_flashcard


def process_single_note(note, ai, anki, obsidian, config, args, deck_name, target_cards_per_note, total_cards, max_cards):
    """Process a single note and return cards added count"""
    note_path = note['result']['path']
    note_title = note['result']['filename']

    console.print(f"\n[blue]PROCESSING:[/blue] {note_title}")

    # Note approval
    from cli.config import APPROVE_NOTES, DEDUPLICATE_VIA_HISTORY, USE_DECK_SCHEMA
    if APPROVE_NOTES:
        try:
            if not approve_note(note_title, note_path):
                return 0
        except KeyboardInterrupt:
            raise

    # Get note content
    note_content = obsidian.get_note_content(note_path)
    if not note_content:
        console.print("  [yellow]WARNING:[/yellow] Empty or inaccessible note, skipping")
        return 0

    # Get previous flashcard fronts for deduplication
    previous_fronts = []
    if DEDUPLICATE_VIA_HISTORY:
        previous_fronts = config.get_flashcard_fronts_for_note(note_path)
        if previous_fronts:
            console.print(f"  [dim]Found {len(previous_fronts)} previous flashcards for deduplication[/dim]")

    # Get deck examples for schema enforcement
    deck_examples = []
    use_schema = args.use_schema if hasattr(args, 'use_schema') else USE_DECK_SCHEMA
    if use_schema:
        deck_examples = anki.get_card_examples(deck_name)
        if deck_examples:
            console.print(f"  [dim]Using {len(deck_examples)} example cards for schema enforcement[/dim]")

    # Generate flashcards
    if args.query:
        console.print(f"  [cyan]Extracting info for query:[/cyan] [bold]{args.query}[/bold]")
        flashcards = ai.generate_from_note_query(note_content, note_title, args.query,
                                                target_cards=target_cards_per_note,
                                                previous_fronts=previous_fronts,
                                                deck_examples=deck_examples)
    else:
        flashcards = ai.generate_flashcards(note_content, note_title,
                                           target_cards=target_cards_per_note,
                                           previous_fronts=previous_fronts,
                                           deck_examples=deck_examples)
    if not flashcards:
        console.print("  [yellow]WARNING:[/yellow] No flashcards generated, skipping")
        return 0

    # Use shared logic for approval and Anki addition
    return process_generated_flashcards(note, flashcards, anki, config, args, deck_name, note_content)


def prepare_batch_data(notes, obsidian, config, args):
    """Prepare note data for batch processing, handling approvals and content loading"""
    from cli.config import APPROVE_NOTES, DEDUPLICATE_VIA_HISTORY
    
    note_batch = []
    previous_fronts_batch = []
    note_metadata = []  # Store (note_path, note_title, note_content) for later use

    for note in notes:
        note_path = note['result']['path']
        note_title = note['result']['filename']

        # Note approval
        if APPROVE_NOTES:
            try:
                if not approve_note(note_title, note_path):
                    continue
            except KeyboardInterrupt:
                raise

        note_content = obsidian.get_note_content(note_path)
        if not note_content:
            console.print(f"[yellow]WARNING:[/yellow] Skipping empty note: {note_title}")
            continue

        note_batch.append((note_content, note_title))
        note_metadata.append((note_path, note_title, note_content))

        # Get previous flashcard fronts
        previous_fronts = []
        if DEDUPLICATE_VIA_HISTORY:
            previous_fronts = config.get_flashcard_fronts_for_note(note_path)
        previous_fronts_batch.append(previous_fronts)

    return note_batch, previous_fronts_batch, note_metadata


def process_notes_batch(notes, ai, anki, obsidian, config, args, deck_name, target_cards_per_note):
    """Process multiple notes in parallel using AI batch processing, then apply sequential logic"""
    from cli.config import USE_DECK_SCHEMA
    
    console.print(f"[cyan]Preparing batch of {len(notes)} notes...[/cyan]")

    # Prepare batch data (handles note approval, content loading, deduplication prep)
    note_batch, previous_fronts_batch, note_metadata = prepare_batch_data(notes, obsidian, config, args)
    
    if not note_batch:
        console.print("[yellow]WARNING:[/yellow] No notes to process after filtering")
        return 0

    # Get deck examples for schema enforcement
    deck_examples = []
    use_schema = args.use_schema if hasattr(args, 'use_schema') else USE_DECK_SCHEMA
    if use_schema:
        deck_examples = anki.get_card_examples(deck_name)

    # Process batch in parallel (AI generation only)
    if args.query:
        batch_results = ai.generate_batch(note_batch, target_cards_per_note,
                                        previous_fronts_batch, deck_examples, args.query)
    else:
        batch_results = ai.generate_batch(note_batch, target_cards_per_note,
                                        previous_fronts_batch, deck_examples)

    # Now use the sequential logic for approval and Anki addition
    total_cards = 0
    console.print(f"[cyan]Adding cards to Anki...[/cyan]")

    for flashcards, (note_path, note_title, note_content) in zip(batch_results, note_metadata):
        if not flashcards:
            console.print(f"[yellow]WARNING:[/yellow] No flashcards generated for {note_title}")
            continue

        # Create a mock note object for the sequential processor
        mock_note = {
            'result': {
                'path': note_path,
                'filename': note_title
            }
        }

        # Reuse sequential logic for approval and Anki operations
        # But skip the AI generation part since we already have flashcards
        cards_added = process_generated_flashcards(mock_note, flashcards, anki, config, args, deck_name, note_content)
        total_cards += cards_added

    return total_cards


def process_generated_flashcards(note, flashcards, anki, config, args, deck_name, note_content):
    """Handle flashcard approval and Anki addition - shared logic between batch and sequential"""
    from cli.config import APPROVE_CARDS, CARD_TYPE
    
    note_path = note['result']['path']
    note_title = note['result']['filename']
    
    console.print(f"[green]Generated {len(flashcards)} flashcards for {note_title}[/green]")

    # Flashcard approval
    cards_to_add = flashcards
    if APPROVE_CARDS:
        approved_flashcards = []
        try:
            console.print(f"\n[blue]Reviewing cards for:[/blue] [bold]{note_title}[/bold]")
            for flashcard in flashcards:
                if approve_flashcard(flashcard, note_title):
                    approved_flashcards.append(flashcard)
        except KeyboardInterrupt:
            raise

        if not approved_flashcards:
            console.print(f"[yellow]WARNING:[/yellow] No flashcards approved for {note_title}, skipping")
            return 0

        console.print(f"[cyan]Approved {len(approved_flashcards)}/{len(flashcards)} flashcards[/cyan]")
        cards_to_add = approved_flashcards

    # Add to Anki
    result = anki.add_flashcards(cards_to_add, deck_name=deck_name, card_type=CARD_TYPE,
                               note_path=note_path, note_title=note_title)
    successful_cards = len([r for r in result if r is not None])

    if successful_cards > 0:
        console.print(f"[green]SUCCESS:[/green] Added {successful_cards} cards to Anki for {note_title}")

        # Record flashcard creation
        note_size = len(note_content)
        flashcard_fronts = [card.get('front', '') for card in cards_to_add[:successful_cards] if card.get('front')]
        config.record_flashcards_created(note_path, note_size, successful_cards, flashcard_fronts)
        return successful_cards
    else:
        console.print(f"[red]ERROR:[/red] Failed to add cards to Anki for {note_title}")
        return 0
