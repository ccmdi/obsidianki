"""Deck management command handler"""

import re
from rich.markup import escape
from rich.panel import Panel

from obsidianki.cli.config import console
from obsidianki.cli.utils import strip_html
from obsidianki.cli.help_utils import show_simple_help


def setup_parser(subparsers):
    """Setup argparse parser for deck command"""
    deck_parser = subparsers.add_parser('deck', help='Manage Anki decks', add_help=False)
    deck_parser.add_argument("-h", "--help", action="store_true", help="Show help message")
    deck_parser.add_argument("-m", "--metadata", action="store_true", help="Show metadata (card counts)")
    deck_subparsers = deck_parser.add_subparsers(dest='deck_action', help='Deck actions')

    # deck rename <old_name> <new_name>
    rename_parser = deck_subparsers.add_parser('rename', help='Rename a deck')
    rename_parser.add_argument('old_name', help='Current deck name')
    rename_parser.add_argument('new_name', help='New deck name')

    # deck search <deck_name> <query>
    search_parser = deck_subparsers.add_parser('search', help='Search for cards in a deck')
    search_parser.add_argument('deck_name', help='Deck name to search in')
    search_parser.add_argument('query', help='Search query (searches front and back of cards)')
    search_parser.add_argument('-l', '--limit', type=int, default=20, help='Maximum number of results to show (default: 20)')

    return deck_parser


def handle_deck_command(args):
    """Handle deck management commands"""
    from obsidianki.cli.services import ANKI

    # Handle help request
    if args.help:
        show_simple_help("Deck Management", {
            "deck": "List all Anki decks",
            "deck -m": "List all Anki decks with card counts",
            "deck rename <old_name> <new_name>": "Rename a deck",
            "deck search <deck_name> <query>": "Search for cards in a deck by keyword"
        })
        return

    # Test connection first
    if not ANKI.test_connection():
        console.print("[red]ERROR:[/red] Cannot connect to AnkiConnect")
        console.print("[dim]Make sure Anki is running with AnkiConnect add-on installed[/dim]")
        return

    if args.deck_action is None:
        # Default action: list decks
        deck_names = ANKI.get_decks()

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
                stats = ANKI.get_stats(deck_name)
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

        if ANKI.rename_deck(old_name, new_name):
            console.print(f"[green]✓[/green] Successfully renamed deck to '[cyan]{new_name}[/cyan]'")
        else:
            console.print("[red]Failed to rename deck[/red]")

        return

    if args.deck_action == 'search':
        deck_name = args.deck_name
        query = args.query
        limit = args.limit

        # Check if deck exists
        deck_names = ANKI.get_decks()
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
        results = ANKI.search_cards(deck_name, query, limit)

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


# Command registration for main.py
COMMAND = {
    'names': ['deck'],
    'setup_parser': setup_parser,
    'handler': handle_deck_command
}
