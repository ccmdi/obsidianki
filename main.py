import argparse
import os
from pathlib import Path
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.text import Text

from cli.config import console, CONFIG_DIR, ENV_FILE, CONFIG_FILE
from cli.handlers import handle_config_command, handle_tag_command, handle_history_command, handle_deck_command

def show_main_help():
    """Display the main help screen"""
    console.print(Panel(
        Text("ObsidianKi - Generate flashcards from Obsidian notes", style="bold blue"),
        style="blue"
    ))
    console.print()

    console.print("[bold blue]Usage[/bold blue]")
    console.print("  [cyan]oki[/cyan] [options]")
    console.print("  [cyan]oki[/cyan] <command> [command-options]")
    console.print()

    console.print("[bold blue]Main Options[/bold blue]")
    console.print("  [cyan]-S, --setup[/cyan]            Run interactive setup")
    console.print("  [cyan]-c, --cards <n>[/cyan]        Maximum cards to generate")
    console.print("  [cyan]-n, --notes <args>[/cyan]     Notes to process: count (5), names (\"React\"), or patterns (\"docs/*:3\")")
    console.print("  [cyan]-q, --query <text>[/cyan]     Generate cards from query or extract from notes")
    console.print("  [cyan]-a, --agent <request>[/cyan]  Agent mode: natural language note discovery [yellow](experimental)[/yellow]")
    console.print("  [cyan]-d, --deck <name>[/cyan]      Anki deck to add cards to")
    console.print("  [cyan]-b, --bias <float>[/cyan]     Bias against over-processed notes (0-1)")
    console.print("  [cyan]-w, --allow <folders>[/cyan]  Temporarily expand search to additional folders")
    console.print("  [cyan]-u, --use-schema[/cyan]       Match existing deck card formatting")
    console.print()

    console.print("[bold blue]Commands[/bold blue]")
    console.print("  [cyan]config[/cyan]                Manage configuration")
    console.print("  [cyan]tag[/cyan]                   Manage tag weights")
    console.print("  [cyan]history[/cyan]               Manage processing history")
    console.print("  [cyan]deck[/cyan]                  Manage Anki decks")
    console.print()


def main():
    parser = argparse.ArgumentParser(description="Generate flashcards from Obsidian notes", add_help=False)
    parser.add_argument("-h", "--help", action="store_true", help="Show help message")
    parser.add_argument("-S", "--setup", action="store_true", help="Run interactive setup to configure API keys")
    parser.add_argument("-c", "--cards", type=int, help="Override max card limit")
    parser.add_argument("-n", "--notes", nargs='+', help="Process specific notes by name/pattern, or specify count (e.g. --notes 5 or --notes \"React\" \"JS\"). For patterns, use format: --notes \"pattern:5\" to sample 5 from pattern")
    parser.add_argument("-q", "--query", type=str, help="Generate cards from standalone query or extract specific info from notes")
    parser.add_argument("-a", "--agent", type=str, help="Agent mode: natural language note discovery using DQL queries (EXPERIMENTAL)")
    parser.add_argument("-d", "--deck", type=str, help="Anki deck to add cards to")
    parser.add_argument("-b", "--bias", type=float, help="Override density bias strength (0=no bias, 1=maximum bias against over-processed notes)")
    parser.add_argument("-w", "--allow", nargs='+', help="Temporarily add folders to SEARCH_FOLDERS for this run")
    parser.add_argument("-u", "--use-schema", action="store_true", help="Sample existing cards from deck to enforce consistent formatting/style")

    # Config management subparser
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    config_parser = subparsers.add_parser('config', help='Manage configuration', add_help=False)
    config_parser.add_argument("-h", "--help", action="store_true", help="Show help message")
    config_subparsers = config_parser.add_subparsers(dest='config_action', help='Config actions')

    # config get <key>
    get_parser = config_subparsers.add_parser('get', help='Get a configuration value')
    get_parser.add_argument('key', help='Configuration key to get')

    # config set <key> <value>
    set_parser = config_subparsers.add_parser('set', help='Set a configuration value')
    set_parser.add_argument('key', help='Configuration key to set')
    set_parser.add_argument('value', help='Value to set')

    # config reset
    config_subparsers.add_parser('reset', help='Reset configuration to defaults')

    # config where
    config_subparsers.add_parser('where', help='Show configuration directory path')

    # History management
    history_parser = subparsers.add_parser('history', help='Manage processing history', add_help=False)
    history_parser.add_argument("-h", "--help", action="store_true", help="Show help message")
    history_subparsers = history_parser.add_subparsers(dest='history_action', help='History actions')

    # history clear
    clear_parser = history_subparsers.add_parser('clear', help='Clear processing history')
    clear_parser.add_argument('--notes', nargs='+', help='Clear history for specific notes only (patterns supported)')

    # history stats
    history_subparsers.add_parser('stats', help='Show flashcard generation statistics')

    # Tag management
    tag_parser = subparsers.add_parser('tag', aliases=['tags'], help='Manage tag weights', add_help=False)
    tag_parser.add_argument("-h", "--help", action="store_true", help="Show help message")
    tag_subparsers = tag_parser.add_subparsers(dest='tag_action', help='Tag actions')

    # tag add <tag> <weight>
    add_parser = tag_subparsers.add_parser('add', help='Add or update a tag weight')
    add_parser.add_argument('tag', help='Tag name')
    add_parser.add_argument('weight', type=float, help='Tag weight')

    # tag remove <tag>
    remove_parser = tag_subparsers.add_parser('remove', help='Remove a tag weight')
    remove_parser.add_argument('tag', help='Tag name to remove')

    # tag exclude <tag>
    exclude_parser = tag_subparsers.add_parser('exclude', help='Add a tag to exclusion list')
    exclude_parser.add_argument('tag', help='Tag name to exclude')

    # tag include <tag>
    include_parser = tag_subparsers.add_parser('include', help='Remove a tag from exclusion list')
    include_parser.add_argument('tag', help='Tag name to include')

    # Deck management
    deck_parser = subparsers.add_parser('deck', help='Manage Anki decks', add_help=False)
    deck_parser.add_argument("-h", "--help", action="store_true", help="Show help message")
    deck_parser.add_argument("-m", "--metadata", action="store_true", help="Show metadata (card counts)")
    deck_subparsers = deck_parser.add_subparsers(dest='deck_action', help='Deck actions')

    # deck rename <old_name> <new_name>
    rename_parser = deck_subparsers.add_parser('rename', help='Rename a deck')
    rename_parser.add_argument('old_name', help='Current deck name')
    rename_parser.add_argument('new_name', help='New deck name')

    args = parser.parse_args()

    if hasattr(args, 'help') and args.help:
        if not args.command:
            show_main_help()
            return 0

    # Handle config, history, and tag management commands
    if args.command == 'config':
        handle_config_command(args)
        return 0
    elif args.command == 'history':
        handle_history_command(args)
        return 0
    elif args.command in ['tag', 'tags']:
        handle_tag_command(args)
        return 0
    elif args.command == 'deck':
        handle_deck_command(args)
        return 0

    needs_setup = False
    if not ENV_FILE.exists():
        needs_setup = True
    elif not CONFIG_FILE.exists():
        needs_setup = True

    if args.setup or needs_setup:
        try:
            from cli.wizard import setup
            setup(force_full_setup=args.setup)
        except KeyboardInterrupt:
            console.print("\n[yellow]Setup cancelled by user[/yellow]")
        return 0

    console.print(Panel(Text("ObsidianKi - Generating flashcards", style="bold blue"), style="blue"))

    # entrypoint for flashcard generation
    from cli.processors import preprocess
    try:
        return preprocess(args)
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
        return 1


if __name__ == "__main__":
    try:
        result = main()
        exit(result if result is not None else 0)
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
        exit(1)
    except Exception as e:
        console.print(f"\n[red]ERROR:[/red] {e}")
        raise
