import argparse
import sys

def _excepthook(exc_type, exc_value, exc_traceback):
    """Fallback traceback handler"""
    if exc_type is KeyboardInterrupt:
        sys.exit(130)
    else:
        console.print(f"[red]ERROR:[/red] {exc_value}")
        sys.exit(1)
sys.excepthook = _excepthook

from rich.panel import Panel
from rich.text import Text

from obsidianki.cli.config import console, ENV_FILE, CONFIG_FILE
from obsidianki.cli.commands import ALL_COMMANDS

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

    console.print("[bold blue]Main options[/bold blue]")
    console.print("  [cyan]-S, --setup[/cyan]               Run interactive setup")
    console.print("  [cyan]-c, --cards <n>[/cyan]           Maximum cards to generate")
    console.print("  [cyan]-n, --notes <args>[/cyan]        Notes to process: count (5), names (\"React\"), or patterns (\"docs/*:3\")")
    console.print("  [cyan]-q, --query <text>[/cyan]        Generate cards from query or extract from notes")
    # console.print("  [cyan]-a, --agent <request>[/cyan]  Agent mode: natural language note discovery [yellow](experimental)[/yellow]")
    console.print("  [cyan]-d, --deck <name>[/cyan]         Anki deck to add cards to")
    console.print("  [cyan]-b, --bias <float>[/cyan]        Bias against over-processed notes (0-1)")
    console.print("  [cyan]-w, --allow <folders>[/cyan]     Temporarily expand search to additional folders")
    console.print("  [cyan]-u, --use-schema [/cyan]         Match existing deck card formatting (optionally from specific notes)")
    console.print()

    console.print("[bold blue]Instruction templates[/bold blue]")
    console.print("  [cyan]-x, --extrapolate[/cyan]         Allow the model to extrapolate with its pre-existing knowledge")
    console.print("  [cyan]-D, --difficulty <level>[/cyan]  Flashcard difficulty level: [bold green]easy[/bold green], [bold green]normal[/bold green], [bold green]hard[/bold green], \\[[bold green]none[/bold green]]")
    console.print()

    console.print("[bold blue]Commands[/bold blue]")
    console.print("  [cyan]config[/cyan]                Manage configuration")
    console.print("  [cyan]tag[/cyan]                   Manage tag weights")
    console.print("  [cyan]history[/cyan]               Manage processing history")
    console.print("  [cyan]deck[/cyan]                  Manage Anki decks")
    console.print("  [cyan]template[/cyan]              Manage command templates")
    console.print("  [cyan]hide[/cyan]                  Manage hidden notes")
    console.print("  [cyan]edit \\[<deck>][/cyan]         Edit existing cards")
    console.print()


def main():
    parser = argparse.ArgumentParser(description="Generate flashcards from Obsidian notes", add_help=False)
    parser.add_argument("-h", "--help", action="store_true", help="Show help message")
    parser.add_argument("-S", "--setup", action="store_true", help="Run interactive setup to configure API keys")
    parser.add_argument("-c", "--cards", "--card", type=int, help="Override max card limit")
    parser.add_argument("-n", "--notes", "--note",  nargs='+', help="Process specific notes by name/pattern, or specify count (e.g. --notes 5 or --notes \"React\" \"JS\"). For patterns, use format: --notes \"pattern:5\" to sample 5 from pattern")
    parser.add_argument("-q", "--query", type=str, help="Generate cards from standalone query or extract specific info from notes")
    parser.add_argument("-a", "--agent", type=str, help="Agent mode: natural language note discovery using DQL queries (EXPERIMENTAL)")
    parser.add_argument("-d", "--deck", type=str, help="Anki deck to add cards to")
    parser.add_argument("-D", "--difficulty", choices=['easy', 'normal', 'hard', 'none'], help="Flashcard difficulty level: easy, normal, hard, none")
    parser.add_argument("-b", "--bias", type=float, help="Override density bias strength (0=no bias, 1=maximum bias against over-processed notes)")
    parser.add_argument("-w", "--allow", nargs='+', help="Temporarily add folders to SEARCH_FOLDERS for this run")
    parser.add_argument("-u", "--use-schema", nargs='?', const=True, default=False, metavar="PATTERN", help="Sample existing cards from deck to enforce consistent formatting/style. Optionally provide a note pattern to filter cards (e.g., --use-schema \"docs/*\")")
    parser.add_argument("-x", "--extrapolate", action="store_true", help="Allow extrapolation of knowledge from pre-existing notes")

    # hidden flags
    parser.add_argument("--mcp", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--json", action="store_true", help=argparse.SUPPRESS)

    subparsers = parser.add_subparsers(dest='command', help='Commands')
    for command in ALL_COMMANDS:
        command['setup_parser'](subparsers)

    args = parser.parse_args()

    if args.json:
        from obsidianki.cli.utils import exec_json_mode
        exec_json_mode()

    if args.help and not args.command:
        show_main_help()
        return 0

    for command in ALL_COMMANDS:
        if args.command in command['names']:
            return command['handler'](args) or 0

    needs_setup = False
    if not ENV_FILE.exists():
        needs_setup = True
    elif not CONFIG_FILE.exists():
        needs_setup = True

    if args.setup or needs_setup:
        try:
            from obsidianki.cli.wizard import setup
            setup(force_full_setup=args.setup)
        except KeyboardInterrupt:
            console.print("\n[yellow]Setup cancelled by user[/yellow]")
        return 0

    console.print(Panel(Text("ObsidianKi - Generating flashcards", style="bold blue"), style="blue"))


    # entrypoint for flashcard generation
    from obsidianki.cli.processors import preprocess
    try:
        return preprocess(args)
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
        return 1
    except Exception as e:
        console.print(f"\n[red]ERROR:[/red] {e}")
        exit(1)


if __name__ == "__main__":
    try:
        result = main()
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
        exit(1)
    except Exception as e:
        console.print(f"\n[red]ERROR:[/red] {e}")
        exit(1)
