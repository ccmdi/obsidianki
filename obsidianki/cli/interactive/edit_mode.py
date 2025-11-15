"""Interactive editing mode for existing flashcards"""

from rich.panel import Panel
from rich.prompt import Prompt

from obsidianki.cli.models import Note, Flashcard
from obsidianki.cli.services import ANKI, AI
from obsidianki.cli.config import CONFIG, console
from obsidianki.cli.interactive.approval import approve_flashcard
from obsidianki.cli.interactive.card_selector import create_card_selector


def edit_mode(args):
    """
    Entry point for interactive editing of existing flashcards.
    """
    deck_name = args.deck if args.deck else CONFIG.deck

    console.print(Panel("ObsidianKi - Editing mode", style="bold blue"))
    console.print(f"[cyan]TARGET DECK:[/cyan] {deck_name}")
    console.print()

    if not ANKI.test_connection():
        console.print("[red]ERROR:[/red] Cannot connect to AnkiConnect")
        return 0

    console.print(f"[cyan]INFO:[/cyan] Retrieving cards from deck '{deck_name}'...")
    all_cards = ANKI.get_cards_for_editing(deck_name)

    if not all_cards:
        console.print(f"[red]ERROR:[/red] No cards found in deck '{deck_name}'")
        return 0

    console.print(f"[cyan]INFO:[/cyan] Found {len(all_cards)} cards in deck")
    console.print()

    # Interactive card selection with arrow keys
    try:
        selected_cards = create_card_selector(all_cards)

        if selected_cards is None:
            console.print("[yellow]Editing cancelled[/yellow]")
            return 0

        if not selected_cards:
            console.print("[yellow]No cards selected[/yellow]")
            return 0

    except Exception as e:
        console.print(f"[red]Error in card selection: {e}[/red]")
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
        console.print()
        console.print(f"  [cyan]Original Back:[/cyan] {original_card['back_original']}")
        console.print(f"  [cyan]Updated Back:[/cyan] {edited_card['back_original']}")
        console.print()

        # Convert to Flashcard object for approval if needed
        if CONFIG.approve_cards:
            dummy_note = Note(path="editing", filename="Card Editing", content="", tags=[], size=0)
            flashcard = Flashcard(
                front=edited_card['front'],
                back=edited_card['back'],
                back_original=edited_card['back_original'],
                front_original=edited_card['front_original'],
                note=dummy_note
            )

            if not approve_flashcard(flashcard):
                console.print("  [yellow]Skipping this card[/yellow]")
                continue

        # Update the card in Anki
        if ANKI.update_note(
            original_card['noteId'],
            edited_card['front'],
            edited_card['back'],
            edited_card['origin'] or original_card['origin'] or ''
        ):
            console.print("  [green]✓ Card updated successfully[/green]")
            total_updated += 1
        else:
            console.print("  [red]✗ Failed to update card[/red]")

    console.print("")
    console.print(Panel(f"[bold green]COMPLETE![/bold green] Updated {total_updated} cards in deck '{deck_name}'", style="green"))
    return total_updated
