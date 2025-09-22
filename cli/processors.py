"""
Note processing functions for ObsidianKi.
Handles both sequential and batch processing of notes.
"""

import concurrent.futures
from cli.config import console
from cli.handlers import approve_note, approve_flashcard


def generate_flashcards_for_note(note, ai, obsidian, config, args, deck_examples, target_cards_per_note):
    """Extract just the AI generation step - this is what we parallelize in batch mode"""
    from cli.config import DEDUPLICATE_VIA_HISTORY
    
    note_path = note['result']['path']
    note_title = note['result']['filename']

    # Get note content
    note_content = obsidian.get_note_content(note_path)
    if not note_content:
        return None, None, note_path

    # Get previous flashcard fronts for deduplication
    previous_fronts = []
    if DEDUPLICATE_VIA_HISTORY:
        previous_fronts = config.get_flashcard_fronts_for_note(note_path)

    # Generate flashcards
    if args.query:
        flashcards = ai.generate_from_note_query(note_content, note_title, args.query,
                                                target_cards=target_cards_per_note,
                                                previous_fronts=previous_fronts,
                                                deck_examples=deck_examples)
    else:
        flashcards = ai.generate_flashcards(note_content, note_title,
                                           target_cards=target_cards_per_note,
                                           previous_fronts=previous_fronts,
                                           deck_examples=deck_examples)
    
    return flashcards, note_content, note_path


def process_single_note(note, ai, anki, obsidian, config, args, deck_name, target_cards_per_note, total_cards, max_cards):
    """Process a single note and return cards added count"""
    from cli.config import APPROVE_NOTES, USE_DECK_SCHEMA
    
    note_path = note['result']['path']
    note_title = note['result']['filename']

    console.print(f"\n[blue]PROCESSING:[/blue] {note_title}")

    # Note approval
    if APPROVE_NOTES:
        try:
            if not approve_note(note_title, note_path):
                return 0
        except KeyboardInterrupt:
            raise

    # Get deck examples for schema enforcement (needed for AI generation)
    deck_examples = []
    use_schema = args.use_schema if hasattr(args, 'use_schema') else USE_DECK_SCHEMA
    if use_schema:
        deck_examples = anki.get_card_examples(deck_name)
        if deck_examples:
            console.print(f"  [dim]Using {len(deck_examples)} example cards for schema enforcement[/dim]")

    # Generate flashcards using the extracted function
    if args.query:
        console.print(f"  [cyan]Extracting info for query:[/cyan] [bold]{args.query}[/bold]")
    
    flashcards, note_content, _ = generate_flashcards_for_note(note, ai, obsidian, config, args, deck_examples, target_cards_per_note)
    
    if not flashcards or not note_content:
        console.print("  [yellow]WARNING:[/yellow] No flashcards generated, skipping")
        return 0

    # Use shared logic for approval and Anki addition
    return process_generated_flashcards(note, flashcards, anki, config, args, deck_name, note_content)




def process_notes_batch(notes, ai, anki, obsidian, config, args, deck_name, target_cards_per_note):
    """Process multiple notes by parallelizing AI generation with futures, then using sequential pipeline"""
    from cli.config import APPROVE_NOTES, USE_DECK_SCHEMA
    
    console.print(f"[cyan]Batch processing {len(notes)} notes...[/cyan]")

    # Filter notes with approval upfront
    valid_notes = []
    for note in notes:
        note_title = note['result']['filename']
        note_path = note['result']['path']
        
        if APPROVE_NOTES:
            try:
                if not approve_note(note_title, note_path):
                    continue
            except KeyboardInterrupt:
                raise
        valid_notes.append(note)
    
    if not valid_notes:
        console.print("[yellow]WARNING:[/yellow] No notes to process after approval")
        return 0

    console.print(f"[cyan]Parallelizing AI generation for {len(valid_notes)} notes...[/cyan]")

    # Get deck examples once (shared across all notes)
    deck_examples = []
    use_schema = args.use_schema if hasattr(args, 'use_schema') else USE_DECK_SCHEMA
    if use_schema:
        deck_examples = anki.get_card_examples(deck_name)
        if deck_examples:
            console.print(f"[dim]Using {len(deck_examples)} example cards for schema enforcement[/dim]")

    # Parallelize ONLY the AI generation step using futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        # Submit all AI generation tasks
        future_to_note = {
            executor.submit(generate_flashcards_for_note, note, ai, obsidian, config, args, deck_examples, target_cards_per_note): note
            for note in valid_notes
        }
        
        # Process results as they complete
        total_cards = 0
        for future in concurrent.futures.as_completed(future_to_note):
            note = future_to_note[future]
            note_title = note['result']['filename']
            
            try:
                flashcards, note_content, note_path = future.result()
                
                if not flashcards or not note_content:
                    console.print(f"[yellow]WARNING:[/yellow] No flashcards generated for {note_title}")
                    continue
                
                # Now use the EXACT same sequential logic for approval and Anki
                cards_added = process_generated_flashcards(note, flashcards, anki, config, args, deck_name, note_content)
                total_cards += cards_added
                
            except Exception as e:
                console.print(f"[red]ERROR:[/red] Failed to process {note_title}: {e}")
                continue

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
