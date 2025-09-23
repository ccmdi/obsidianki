"""
Note processing functions for ObsidianKi.
"""

import concurrent.futures
from typing import List
from cli.handlers import approve_note, approve_flashcard
from cli.models import Note, Flashcard
from cli.services import OBSIDIAN, AI, ANKI


def process(note: Note, args, deck_examples, target_cards_per_note, previous_fronts) -> tuple[List[Flashcard], str, str]:
    from cli.config import console
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

    return flashcards, note.content, note.path


def postprocess(note: Note, flashcards: List[Flashcard], deck_name):
    """Handle flashcard approval and Anki addition"""
    from cli.config import console, APPROVE_CARDS, CARD_TYPE, CONFIG_MANAGER

    console.print(f"[green]Generated {len(flashcards)} flashcards for {note.filename}[/green]")

    # Flashcard approval
    cards_to_add = flashcards
    if APPROVE_CARDS:
        approved_flashcards = []
        try:
            console.print(f"\n[blue]Reviewing cards for:[/blue] [bold]{note.filename}[/bold]")
            for flashcard in flashcards:
                if approve_flashcard(flashcard, note):
                    approved_flashcards.append(flashcard)
        except KeyboardInterrupt:
            raise

        if not approved_flashcards:
            console.print(f"[yellow]WARNING:[/yellow] No flashcards approved for {note.filename}, skipping")
            return 0

        console.print(f"[cyan]Approved {len(approved_flashcards)}/{len(flashcards)} flashcards[/cyan]")
        cards_to_add = approved_flashcards

    result = ANKI.add_flashcards(cards_to_add, deck_name=deck_name, card_type=CARD_TYPE)
    successful_cards = len([r for r in result if r is not None])

    if successful_cards > 0:
        if note.path != "query": #TODO
            flashcard_fronts = [fc.front for fc in cards_to_add[:successful_cards]]
            CONFIG_MANAGER.record_flashcards_created(note.path, note.size, successful_cards, flashcard_fronts)
        return successful_cards
    else:
        console.print(f"[red]ERROR:[/red] Failed to add cards to Anki for {note.filename}")
        return 0


def preprocess(args):
    """
    Entry point for flashcard generation.
    """
    from cli.config import (
        console, MAX_CARDS, NOTES_TO_SAMPLE, DAYS_OLD, SAMPLING_MODE, CARD_TYPE,
        APPROVE_NOTES, APPROVE_CARDS, DEDUPLICATE_VIA_HISTORY, DEDUPLICATE_VIA_DECK,
        USE_DECK_SCHEMA, DECK, SEARCH_FOLDERS, UPFRONT_BATCHING, BATCH_SIZE_LIMIT, BATCH_CARD_LIMIT,
        DENSITY_BIAS_STRENGTH, CONFIG_MANAGER
    )
    from rich.panel import Panel

    deck_name = args.deck if args.deck else DECK
    notes_to_sample = NOTES_TO_SAMPLE

    if args.notes:
        # When --notes is provided, scale cards to 2 * number of notes (unless --cards also provided)
        if args.cards is not None:
            max_cards = args.cards
        else:
            max_cards = len(args.notes) * 2  # Will be updated after we find actual notes
        # notes_to_sample not used when specific notes are provided
    elif args.cards is not None:
        # When --cards is provided, scale notes to 1/2 of cards
        max_cards = args.cards
        notes_to_sample = max(1, max_cards // 2)
    else:
        # Default behavior - use config values
        max_cards = MAX_CARDS
        notes_to_sample = NOTES_TO_SAMPLE

    # --bias
    effective_bias_strength = args.bias if args.bias is not None else DENSITY_BIAS_STRENGTH

    # Handle search folders - processors.py owns this state
    search_folders = SEARCH_FOLDERS
    if args.allow:
        search_folders = list(SEARCH_FOLDERS) + args.allow if SEARCH_FOLDERS else args.allow
        console.print(f"[dim]Search folders:[/dim] {', '.join(search_folders)}")
        console.print()

    if SAMPLING_MODE == "weighted":
        CONFIG_MANAGER.show_weights()
    console.print()

    if args.query and not args.notes and DEDUPLICATE_VIA_DECK:
        console.print("[yellow]WARNING:[/yellow] DEDUPLICATE_VIA_DECK is experimental and may be expensive for large decks\n")

    # Test connections
    if not OBSIDIAN.test_connection():
        console.print("[red]ERROR:[/red] Cannot connect to Obsidian REST API")
        return 0

    if not ANKI.test_connection():
        console.print("[red]ERROR:[/red] Cannot connect to AnkiConnect")
        return 0

    # === GET NOTES TO PROCESS ===
    notes = None

    if args.query and not args.agent and not args.notes:
        # STANDALONE QUERY MODE - Create synthetic note for main flow
        console.print(f"[cyan]QUERY MODE:[/cyan] [bold]{args.query}[/bold]")
        from cli.models import Note
        query_note = Note(path="query", filename=f"Query: {args.query}", content=args.query, tags=[])
        notes = [query_note]
        max_cards = args.cards if args.cards else max_cards
        APPROVE_NOTES = False # no need to approve what a user wrote
    elif args.agent:
        console.print(f"[yellow]WARNING:[/yellow] Agent mode is EXPERIMENTAL and may produce unexpected results")
        console.print(f"[cyan]AGENT MODE:[/cyan] [bold]{args.agent}[/bold]")
        notes = AI.find_with_agent(args.agent, sample_size=notes_to_sample, bias_strength=effective_bias_strength)
        if not notes:
            console.print("[red]ERROR:[/red] Agent found no matching notes")
            return 0
        # Update max_cards based on found notes (if --cards wasn't specified)
        if args.cards is None:
            max_cards = len(notes) * 2

    elif args.notes:
        # Handle --notes argument parsing
        if len(args.notes) == 1 and args.notes[0].isdigit():
            # User specified a count: --notes 5
            note_count = int(args.notes[0])
            console.print(f"[cyan]INFO:[/cyan] Sampling {note_count} random notes")
            notes = OBSIDIAN.sample_old_notes(days=DAYS_OLD, limit=note_count, bias_strength=effective_bias_strength, search_folders=search_folders)
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
                    
                    pattern_notes = OBSIDIAN.find_by_pattern(note_pattern, sample_size=sample_size, bias_strength=effective_bias_strength, search_folders=search_folders)
                    if pattern_notes:
                        notes.extend(pattern_notes)
                        if sample_size and len(pattern_notes) == sample_size:
                            console.print(f"[cyan]INFO:[/cyan] Sampled {len(pattern_notes)} notes from pattern: '{note_pattern}'")
                        else:
                            console.print(f"[cyan]INFO:[/cyan] Found {len(pattern_notes)} notes from pattern: '{note_pattern}'")
                    else:
                        console.print(f"[red]ERROR:[/red] No notes found for pattern: '{note_pattern}'")
                else:
                    specific_note = OBSIDIAN.find_by_name(note_pattern, search_folders=search_folders)
                    if specific_note:
                        notes.append(specific_note)
                    else:
                        console.print(f"[red]ERROR:[/red] Not found: '{note_pattern}'")
        
        if not notes:
            console.print("[red]ERROR:[/red] No notes found")
            return 0
    else:
        # Default sampling
        notes = OBSIDIAN.sample_old_notes(days=DAYS_OLD, limit=notes_to_sample, bias_strength=effective_bias_strength, search_folders=search_folders)
        if not notes:
            console.print("[red]ERROR:[/red] No old notes found")
            return 0

    # Show processing info
    if args.query and args.notes:
        console.print(f"[cyan]TARGETED MODE:[/cyan] Extracting '{args.query}' from {len(notes)} note(s)")
    elif not args.query:
        console.print(f"[cyan]INFO:[/cyan] Processing {len(notes)} note(s)")
    console.print(f"[cyan]TARGET:[/cyan] {max_cards} flashcards maximum")
    console.print()

    # === BATCH MODE DECISION ===
    use_batch_mode = UPFRONT_BATCHING and len(notes) > 1
    if use_batch_mode:
        if len(notes) > BATCH_SIZE_LIMIT:
            console.print(f"[yellow]WARNING:[/yellow] Batch mode disabled - too many notes ({len(notes)} > {BATCH_SIZE_LIMIT})")
            console.print(f"[yellow]This could result in expensive API costs. Use fewer notes or disable UPFRONT_BATCHING.[/yellow]")
            use_batch_mode = False
        elif max_cards > BATCH_CARD_LIMIT:
            console.print(f"[yellow]WARNING:[/yellow] Batch mode disabled - too many target cards ({max_cards} > {BATCH_CARD_LIMIT})")
            console.print(f"[yellow]This could result in expensive API costs. Use fewer cards or disable UPFRONT_BATCHING.[/yellow]")
            use_batch_mode = False

    target_cards_per_note = max(1, max_cards // len(notes))

    if args.cards and target_cards_per_note > 5:
        console.print(f"[yellow]WARNING:[/yellow] Requesting more than 5 cards per note can decrease quality")
        console.print(f"[yellow]Consider using fewer total cards or more notes for better results[/yellow]\n")

    # === PROCESS NOTES ===
    deck_examples = []
    use_schema = args.use_schema if hasattr(args, 'use_schema') else USE_DECK_SCHEMA
    if use_schema:
        deck_examples = ANKI.get_card_examples(deck_name)
        if deck_examples:
            console.print(f"[dim]Using {len(deck_examples)} example cards for schema enforcement[/dim]")

    previous_fronts = []
    if DEDUPLICATE_VIA_HISTORY:
        previous_fronts = [note.get_previous_flashcard_fronts() for note in notes]
    elif args.query and not args.notes and DEDUPLICATE_VIA_DECK:
        # For standalone query mode, use deck-based deduplication
        deck_fronts = ANKI.get_card_fronts(deck_name)
        if deck_fronts:
            console.print(f"[dim]Found {len(deck_fronts)} existing cards in deck '{deck_name}' for deduplication[/dim]")
        previous_fronts = [deck_fronts] * len(notes)  # Same fronts for all notes (just the query note)

    total_cards = 0

    if use_batch_mode:
        # PARALLEL MODE
        console.print(f"[cyan]INFO[/cyan]: Batch mode")
        console.print()

        # Filter notes with approval upfront
        valid_notes = []
        for note in notes:
            note.ensure_content()
            console.print(f"\n[blue]PROCESSING:[/blue] {note.filename}")

            if APPROVE_NOTES:
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
            future_to_note = {
                executor.submit(process, note, args, deck_examples, target_cards_per_note, previous_fronts): note
                for note in valid_notes
            }

            for future in concurrent.futures.as_completed(future_to_note):
                note = future_to_note[future]

                try:
                    flashcards, note_content, note_path = future.result()

                    if not flashcards or not note_content:
                        console.print(f"[yellow]WARNING:[/yellow] No flashcards generated for {note.filename}")
                        continue

                    cards_added = postprocess(note, flashcards, deck_name)
                    total_cards += cards_added

                except Exception as e:
                    console.print(f"[red]ERROR:[/red] Failed to process {note.filename}: {e}")
                    continue
    else:
        # SEQUENTIAL: Process each note one by one
        for i, note in enumerate(notes, 1):
            if total_cards >= max_cards:
                break

            note.ensure_content()

            console.print(f"\n[blue]PROCESSING:[/blue] {note.filename}")

            if APPROVE_NOTES:
                try:
                    if not approve_note(note):
                        continue
                except KeyboardInterrupt:
                    console.print("\n[yellow]Operation cancelled by user[/yellow]")
                    return total_cards
            
            try:
                flashcards, note_content, _ = process(note, args, deck_examples, target_cards_per_note, previous_fronts)

                if not flashcards or not note_content:
                    console.print("  [yellow]WARNING:[/yellow] No flashcards generated, skipping")
                    continue

                cards_added = postprocess(note, flashcards, deck_name)
                total_cards += cards_added
                
            except KeyboardInterrupt:
                console.print("\n[yellow]Operation cancelled by user[/yellow]")
                return total_cards

    console.print("")
    console.print(Panel(f"[bold green]COMPLETE![/bold green] Added {total_cards}/{max_cards} flashcards to your Obsidian deck", style="green"))
    return total_cards


def _create_card_selector(all_cards):
    """Create a cross-platform interactive card selector"""
    import sys
    import os
    from rich.live import Live
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich.console import Group
    from cli.config import console

    def get_key():
        """Cross-platform key reading with Windows optimization"""
        if os.name == 'nt':  # Windows
            import msvcrt
            import time

            # Non-blocking check with small sleep to reduce CPU usage
            if msvcrt.kbhit():
                key = msvcrt.getch()
                if key == b'\xe0':  # Arrow key prefix
                    key = msvcrt.getch()
                    if key == b'H':  # Up arrow
                        return 'up'
                    elif key == b'P':  # Down arrow
                        return 'down'
                elif key == b' ':  # Space
                    return 'space'
                elif key == b'\r':  # Enter
                    return 'enter'
                elif key == b'\x1b':  # Escape
                    return 'escape'

            # Small sleep to prevent 100% CPU usage
            time.sleep(0.01)
            return None
        else:  # Unix/Linux/Mac
            import tty, termios
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setraw(sys.stdin.fileno())
                key = sys.stdin.read(1)
                if key == '\x1b':  # Escape sequence
                    key += sys.stdin.read(2)
                    if key == '\x1b[A':  # Up arrow
                        return 'up'
                    elif key == '\x1b[B':  # Down arrow
                        return 'down'
                    else:
                        return 'escape'
                elif key == ' ':
                    return 'space'
                elif key == '\r' or key == '\n':
                    return 'enter'
                elif key == '\x1b':
                    return 'escape'
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return None

    selected_indices = set()
    current_index = 0
    page_size = 15
    current_page = 0

    def create_display():
        start_idx = current_page * page_size
        end_idx = min(start_idx + page_size, len(all_cards))

        table = Table(title=f"Select Cards to Edit (Page {current_page + 1})")
        table.add_column("", width=3)
        table.add_column("ID", style="cyan", width=4)
        table.add_column("Front", style="white", width=50)
        table.add_column("Back", style="dim", width=50)

        for i in range(start_idx, end_idx):
            card = all_cards[i]

            # Cursor and selection indicators
            cursor = "→" if i == current_index else " "
            checkbox = "☑" if i in selected_indices else "☐"
            style = "bold cyan" if i == current_index else "white"

            front = card['front'][:47] + "..." if len(card['front']) > 50 else card['front']
            back = card['back'][:47] + "..." if len(card['back']) > 50 else card['back']

            table.add_row(
                f"{cursor} {checkbox}",
                str(i + 1),
                front,
                back,
                style=style
            )

        instructions = Text()
        instructions.append("Controls: ", style="bold cyan")
        instructions.append("↑/↓ Navigate  ", style="white")
        instructions.append("Space Select  ", style="white")
        instructions.append("Enter Confirm  ", style="white")
        instructions.append("Esc Cancel", style="white")

        status = Text()
        if selected_indices:
            status.append(f"Selected: {len(selected_indices)} cards", style="green")
        else:
            status.append("No cards selected", style="yellow")

        return Group(table, "", Panel(instructions, title="Controls"), status)

    try:
        # Windows-optimized display refresh
        refresh_rate = 60 if os.name == 'nt' else 10  # Higher refresh for smoother Windows experience

        with Live(create_display(), refresh_per_second=refresh_rate, screen=True) as live:
            needs_update = True

            while True:
                # Only update display when needed to reduce lag
                if needs_update:
                    live.update(create_display())
                    needs_update = False

                key = get_key()
                if key == 'up':
                    current_index = max(0, current_index - 1)
                    if current_index < current_page * page_size:
                        current_page = max(0, current_page - 1)
                    needs_update = True
                elif key == 'down':
                    current_index = min(len(all_cards) - 1, current_index + 1)
                    if current_index >= (current_page + 1) * page_size:
                        current_page = min((len(all_cards) - 1) // page_size, current_page + 1)
                    needs_update = True
                elif key == 'space':
                    if current_index in selected_indices:
                        selected_indices.remove(current_index)
                    else:
                        selected_indices.add(current_index)
                    needs_update = True
                elif key == 'enter':
                    if selected_indices:
                        return [all_cards[i] for i in sorted(selected_indices)]
                elif key == 'escape':
                    return None

    except Exception as e:
        console.print(f"[red]Error with interactive selector: {e}[/red]")
        return _create_basic_selector(all_cards)


def _create_paginated_selector(all_cards, all_choices):
    """Handle large lists with manual pagination"""
    from cli.config import console
    import inquirer

    selected_indices = set()
    page_size = 15
    current_page = 0
    total_pages = (len(all_choices) - 1) // page_size + 1

    while True:
        start_idx = current_page * page_size
        end_idx = min(start_idx + page_size, len(all_choices))
        page_choices = all_choices[start_idx:end_idx]

        # Add navigation options
        nav_choices = page_choices.copy()
        if current_page > 0:
            nav_choices.insert(0, ("← Previous page", "prev"))
        if current_page < total_pages - 1:
            nav_choices.append(("→ Next page", "next"))
        nav_choices.append(("✓ Done selecting", "done"))

        console.clear()
        console.print(f"[cyan]Page {current_page + 1}/{total_pages} • Selected: {len(selected_indices)} cards[/cyan]")

        questions = [
            inquirer.Checkbox(
                'page_selection',
                message="Select cards (or navigate)",
                choices=nav_choices,
                default=[choice for choice in page_choices if choice[1] in selected_indices]
            ),
        ]

        try:
            answers = inquirer.prompt(questions)
            if not answers:
                return None

            selections = answers.get('page_selection', [])

            if "done" in selections:
                break
            elif "next" in selections and current_page < total_pages - 1:
                current_page += 1
                continue
            elif "prev" in selections and current_page > 0:
                current_page -= 1
                continue
            else:
                # Update selections for this page
                for choice_text, choice_idx in page_choices:
                    if choice_idx in selections:
                        selected_indices.add(choice_idx)
                    else:
                        selected_indices.discard(choice_idx)

        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            return None

    if not selected_indices:
        return None

    return [all_cards[i] for i in sorted(selected_indices)]


def _create_basic_selector(all_cards):
    """Fallback basic selector"""
    from rich.prompt import Confirm
    from rich.table import Table
    from cli.config import console

    # Show cards in a table
    table = Table(title=f"Available Cards ({len(all_cards)} total)")
    table.add_column("ID", style="cyan", width=4)
    table.add_column("Front", style="white", width=50)
    table.add_column("Back", style="dim", width=50)

    for i, card in enumerate(all_cards[:20]):  # Show first 20
        front = card['front'][:47] + "..." if len(card['front']) > 50 else card['front']
        back = card['back'][:47] + "..." if len(card['back']) > 50 else card['back']
        table.add_row(str(i + 1), front, back)

    if len(all_cards) > 20:
        table.add_row("[dim]...", f"[dim]... and {len(all_cards) - 20} more", "[dim]...")

    console.print(table)
    console.print()

    # Simple selection
    try:
        selection = console.input("[cyan]Enter card IDs (e.g., '1,3,5-10') or 'all':[/cyan] ").strip()

        if not selection:
            return None

        if selection.lower() == 'all':
            return list(all_cards)

        selected_cards = []
        parts = [part.strip() for part in selection.split(',')]

        for part in parts:
            if '-' in part:
                start_str, end_str = part.split('-', 1)
                start_idx = int(start_str.strip()) - 1
                end_idx = int(end_str.strip()) - 1
                if 0 <= start_idx <= end_idx < len(all_cards):
                    selected_cards.extend(all_cards[start_idx:end_idx + 1])
            else:
                card_id = int(part) - 1
                if 0 <= card_id < len(all_cards):
                    selected_cards.append(all_cards[card_id])

        return selected_cards if selected_cards else None

    except (ValueError, KeyboardInterrupt):
        return None


def edit_mode(args):
    """
    Entry point for interactive editing of existing flashcards.
    """
    from cli.config import console, DECK, APPROVE_CARDS
    from cli.handlers import approve_flashcard
    from cli.models import Note, Flashcard
    from rich.panel import Panel
    from rich.prompt import Prompt

    deck_name = args.deck if args.deck else DECK

    console.print(Panel("Interactive Card Editing Mode", style="bold blue"))
    console.print(f"[cyan]TARGET DECK:[/cyan] {deck_name}")
    console.print()

    # Test connections
    if not ANKI.test_connection():
        console.print("[red]ERROR:[/red] Cannot connect to AnkiConnect")
        return 0

    # Get all cards from deck
    console.print(f"[cyan]INFO:[/cyan] Retrieving cards from deck '{deck_name}'...")
    all_cards = ANKI.get_cards_for_editing(deck_name)

    if not all_cards:
        console.print(f"[red]ERROR:[/red] No cards found in deck '{deck_name}'")
        return 0

    console.print(f"[cyan]INFO:[/cyan] Found {len(all_cards)} cards in deck")
    console.print()

    # Interactive card selection with arrow keys
    try:
        selected_cards = _create_card_selector(all_cards)

        if selected_cards is None:
            console.print("[yellow]Editing cancelled[/yellow]")
            return 0

        if not selected_cards:
            console.print("[yellow]No cards selected[/yellow]")
            return 0

    except Exception as e:
        console.print(f"[red]Error in card selection: {e}[/red]")
        console.print("[yellow]Falling back to basic interface[/yellow]")
        return 0

    # Get editing instructions
    console.print(f"[green]Selected {len(selected_cards)} cards for editing[/green]")
    console.print()

    try:
        edit_instructions = Prompt.ask("[cyan]Enter your editing instructions[/cyan] (describe what changes you want to make)")

        if not edit_instructions.strip():
            console.print("[yellow]No instructions provided. Editing cancelled.[/yellow]")
            return 0

    except KeyboardInterrupt:
        console.print("\n[yellow]Editing cancelled[/yellow]")
        return 0

    console.print()
    console.print(f"[cyan]INFO:[/cyan] Applying edits: '{edit_instructions}'")

    # Edit selected cards using AI
    edited_cards = AI.edit_cards(selected_cards, edit_instructions)

    if not edited_cards:
        console.print("[red]ERROR:[/red] Failed to edit cards")
        return 0

    # Process each edited card
    total_updated = 0
    for i, (original_card, edited_card) in enumerate(zip(selected_cards, edited_cards)):
        console.print(f"\n[blue]CARD {i+1}:[/blue]")

        # Check if card was actually changed
        if (original_card['front'] == edited_card['front'] and
            original_card['back'] == edited_card['back']):
            console.print("  [dim]No changes needed for this card[/dim]")
            continue

        # Show changes
        console.print(f"  [cyan]Original Front:[/cyan] {original_card['front']}")
        console.print(f"  [cyan]Updated Front:[/cyan] {edited_card['front']}")
        console.print(f"  [cyan]Original Back:[/cyan] {original_card['back']}")
        console.print(f"  [cyan]Updated Back:[/cyan] {edited_card['back']}")
        console.print()

        # Convert to Flashcard object for approval if needed
        if APPROVE_CARDS:
            dummy_note = Note(path="editing", filename="Card Editing", content="", tags=[])
            flashcard = Flashcard(
                front=edited_card['front'],
                back=edited_card['back'],
                origin=edited_card.get('origin', original_card.get('origin', ''))
            )

            if not approve_flashcard(flashcard, dummy_note):
                console.print("  [yellow]Skipping this card[/yellow]")
                continue

        # Update the card in Anki
        if ANKI.update_note(
            original_card['noteId'],
            edited_card['front'],
            edited_card['back'],
            edited_card.get('origin', original_card.get('origin', ''))
        ):
            console.print("  [green]✓ Card updated successfully[/green]")
            total_updated += 1
        else:
            console.print("  [red]✗ Failed to update card[/red]")

    console.print("")
    console.print(Panel(f"[bold green]COMPLETE![/bold green] Updated {total_updated} cards in deck '{deck_name}'", style="green"))
    return total_updated
