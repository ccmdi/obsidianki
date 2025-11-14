"""Deck management command handler"""

import re
from rich.markup import escape
from rich.panel import Panel

from obsidianki.cli.services import ANKI
from obsidianki.cli.config import console
from obsidianki.cli.utils import strip_html
from obsidianki.cli.help_utils import show_simple_help


def handle_deck_command(args):
    """Handle deck management commands"""

    # Handle help request
    if args.help:
        show_simple_help("Deck Management", {
            "deck": "List all Anki decks",
            "deck -m": "List all Anki decks with card counts",
            "deck rename <old_name> <new_name>": "Rename a deck",
            "deck search <deck_name> <query>": "Search for cards in a deck by keyword"
        })
        return

    anki = ANKI

    # Test connection first
    if not anki.test_connection():
        console.print("[red]ERROR:[/red] Cannot connect to AnkiConnect")
        console.print("[dim]Make sure Anki is running with AnkiConnect add-on installed[/dim]")
        return

    if args.deck_action is None:
        # Default action: list decks
        deck_names = anki.get_decks()

        if not deck_names:
            console.print("[yellow]No decks found[/yellow]")
            return

        console.print("[bold blue]Anki Decks[/bold blue]")
        console.print()

        # Check if metadata flag is set
        show_metadata = args.metadata

        if show_metadata:
            console.print(f"[dim]Found {len(deck_names)} decks:[/dim]")
            console.print()
            for deck_name in sorted(deck_names):
                stats = anki.get_stats(deck_name)
                total_cards = stats.get("total_cards", 0)

                console.print(f"  [cyan]{deck_name}[/cyan]")
                console.print(f"    [dim]{total_cards} cards[/dim]")
        else:
            console.print(f"[dim]Found {len(deck_names)} decks:[/dim]")
            console.print()
            for deck_name in sorted(deck_names):
                console.print(f"  [cyan]{deck_name}[/cyan]")

        console.print()
        return

    if args.deck_action == 'rename':
        old_name = args.old_name
        new_name = args.new_name

        console.print(f"[cyan]Renaming deck:[/cyan] [bold]{old_name}[/bold] → [bold]{new_name}[/bold]")

        if anki.rename_deck(old_name, new_name):
            console.print(f"[green]✓[/green] Successfully renamed deck to '[cyan]{new_name}[/cyan]'")
        else:
            console.print("[red]Failed to rename deck[/red]")

        return

    if args.deck_action == 'search':
        deck_name = args.deck_name
        query = args.query
        limit = args.limit

        # Check if deck exists
        deck_names = anki.get_decks()
        if deck_name not in deck_names:
            console.print(f"[red]ERROR:[/red] Deck '[cyan]{deck_name}[/cyan]' not found")
            console.print("\n[dim]Available decks:[/dim]")
            for name in sorted(deck_names):
                console.print(f"  [cyan]{name}[/cyan]")
            return

        console.print(f"[cyan]Searching deck:[/cyan] [bold]{deck_name}[/bold]")
        console.print(f"[cyan]Query:[/cyan] [bold]{query}[/bold]")
        console.print()

        # Search for cards
        results = anki.search_cards(deck_name, query, limit)

        if not results:
            console.print(f"[yellow]No cards found matching '{query}'[/yellow]")
            return

        console.print(f"[green]Found {len(results)} matching card(s)[/green]")
        console.print()

        # Helper function to highlight query in text
        def highlight_query(text, query):
            # Remove HTML tags for cleaner display
            text_clean = strip_html(text)
            # Escape special characters for rich markup
            text_escaped = escape(text_clean)
            # Highlight the query (case-insensitive)
            pattern = re.compile(re.escape(query), re.IGNORECASE)
            highlighted = pattern.sub(lambda m: f"[black on yellow]{m.group()}[/black on yellow]", text_escaped)
            return highlighted

        # Display results
        for i, card in enumerate(results, 1):
            front = card.get("front", "")
            back = card.get("back", "")
            origin = card.get("origin", "")

            # Highlight query in front and back
            front_highlighted = highlight_query(front, query)
            back_highlighted = highlight_query(back, query)

            # Create a nice display
            console.print(f"[bold blue]Card {i}:[/bold blue]")
            console.print(f"  [dim]Front:[/dim] {front_highlighted}")
            console.print(f"  [dim]Back:[/dim] {back_highlighted}")

            # Show origin if available (without highlighting)
            if origin:
                origin_clean = strip_html(origin)
                console.print(f"  [dim]Origin:[/dim] {origin_clean}")

            console.print()

        if len(results) == limit:
            console.print(f"[dim]Showing first {limit} results. Use -l/--limit to show more.[/dim]")

        return
