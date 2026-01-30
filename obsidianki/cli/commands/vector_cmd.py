"""Vector index management commands."""
import argparse
from obsidianki.cli.config import console, CONFIG


def setup_parser(subparsers):
    """Set up the vector subcommand parser."""
    vector_parser = subparsers.add_parser(
        "vector",
        help="Manage vector index for semantic deduplication"
    )

    vector_subparsers = vector_parser.add_subparsers(dest="vector_action")

    # vector index
    index_parser = vector_subparsers.add_parser(
        "index",
        help="Index existing Anki cards into vector store"
    )
    index_parser.add_argument(
        "--deck",
        type=str,
        default=None,
        help="Anki deck to index (defaults to configured deck)"
    )

    # vector status
    vector_subparsers.add_parser(
        "status",
        help="Show vector index status"
    )

    # vector clear
    vector_subparsers.add_parser(
        "clear",
        help="Clear the vector index"
    )

    # vector check
    check_parser = vector_subparsers.add_parser(
        "check",
        help="Check if a question is similar to existing cards"
    )
    check_parser.add_argument(
        "question",
        type=str,
        help="Question text to check for similarity"
    )
    check_parser.add_argument(
        "-t", "--threshold",
        type=float,
        default=None,
        help="Custom similarity threshold (0-1), overrides config"
    )

    return vector_parser


def handler(args: argparse.Namespace):
    """Handle vector subcommands."""
    if not CONFIG.vector_dedup:
        console.print("[yellow]Vector deduplication is disabled.[/yellow]")
        console.print("Enable with: [cyan]oki config set vector_dedup true[/cyan]")
        return

    action = getattr(args, "vector_action", None)

    if action == "index":
        _handle_index(args)
    elif action == "status":
        _handle_status()
    elif action == "clear":
        _handle_clear()
    elif action == "check":
        _handle_check(args)
    else:
        console.print("Usage: oki vector [index|status|clear|check]")
        console.print("Run 'oki vector --help' for more information")


def _handle_index(args: argparse.Namespace):
    """Index existing Anki cards into vector store."""
    from obsidianki.cli.services import ANKI
    from obsidianki.ai.vectors import get_vectors

    deck = args.deck or CONFIG.deck
    if not deck:
        console.print("[red]ERROR:[/red] No deck specified. Use --deck or set default deck.")
        return

    console.print(f"[cyan]Fetching cards from deck:[/cyan] {deck}")

    try:
        fronts = ANKI.get_card_fronts(deck)
    except Exception as e:
        console.print(f"[red]ERROR:[/red] Failed to fetch cards from Anki: {e}")
        return

    if not fronts:
        console.print("[yellow]No cards found in deck.[/yellow]")
        return

    console.print(f"[cyan]Found {len(fronts)} cards to index[/cyan]")

    vectors = get_vectors()
    existing_count = vectors.count()

    # Index in batches for visibility
    batch_size = 50
    for i in range(0, len(fronts), batch_size):
        batch = fronts[i:i + batch_size]
        vectors.add(batch)
        console.print(f"[dim]Indexed {min(i + batch_size, len(fronts))}/{len(fronts)}[/dim]")

    new_count = vectors.count()
    added = new_count - existing_count
    console.print(f"[green]Done![/green] Added {added} new cards to vector index (total: {new_count})")


def _handle_status():
    """Show vector index status."""
    from obsidianki.ai.vectors import get_vectors

    vectors = get_vectors()
    count = vectors.count()

    console.print(f"[cyan]Vector index status[/cyan]")
    console.print(f"  Cards indexed: {count}")
    console.print(f"  Threshold: {CONFIG.vector_threshold}")
    console.print(f"  Max turns: {CONFIG.vector_max_turns}")


def _handle_clear():
    """Clear the vector index."""
    from obsidianki.ai.vectors import get_vectors

    vectors = get_vectors()
    count = vectors.count()

    if count == 0:
        console.print("[yellow]Vector index is already empty.[/yellow]")
        return

    vectors.clear()
    console.print(f"[green]Cleared {count} cards from vector index.[/green]")


def _handle_check(args: argparse.Namespace):
    """Check if a question is similar to existing cards."""
    from obsidianki.ai.vectors import get_vectors

    vectors = get_vectors()
    question = args.question
    threshold = args.threshold if args.threshold is not None else (CONFIG.vector_threshold or 0.7)

    if vectors.count() == 0:
        console.print("[yellow]Vector index is empty. Run 'oki vector index' first.[/yellow]")
        return

    console.print(f"[cyan]Checking:[/cyan] {question}")
    console.print(f"[dim]Threshold: {threshold:.0%}[/dim]")

    matches = vectors.find_similar(question, threshold)

    if matches:
        console.print(f"\n[yellow]{len(matches)} similar card(s) found:[/yellow]")
        for text, score in matches:
            console.print(f"  [{score:.0%}] {text}")
    else:
        console.print(f"\n[green]No similar cards found above {threshold:.0%} threshold.[/green]")


COMMAND = {
    'names': ['vector'],
    'setup_parser': setup_parser,
    'handler': handler
}
