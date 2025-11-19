"""Hidden notes management command handler"""

from pathlib import Path

from obsidianki.cli.config import CONFIG, console
from obsidianki.cli.help_utils import show_simple_help


def setup_parser(subparsers):
    """Setup argparse parser for hide command"""
    hide_parser = subparsers.add_parser('hide', help='Manage hidden notes', add_help=False)
    hide_parser.add_argument("-h", "--help", action="store_true", help="Show help message")
    hide_subparsers = hide_parser.add_subparsers(dest='hide_action', help='Hide actions')

    # hide unhide <note_path>
    unhide_parser = hide_subparsers.add_parser('unhide', help='Unhide a specific note')
    unhide_parser.add_argument('note_path', help='Path to note to unhide')

    return hide_parser


def handle_hide_command(args):
    """Handle hidden notes management commands"""

    if args.help:
        show_simple_help("Hidden Notes Management", {
            "hide": "List all hidden notes",
            "hide unhide <note_path>": "Unhide a specific note"
        })
        return

    if args.hide_action is None:
        # Default action: list hidden notes
        hidden_notes = CONFIG.get_hidden_notes()

        if not hidden_notes:
            console.print("[dim]No hidden notes[/dim]")
            return

        console.print("[bold blue]Hidden Notes[/bold blue]")
        console.print()
        for note_path in sorted(hidden_notes):
            note_name = Path(note_path).name
            console.print(f"  [red]{note_name}[/red]")
            console.print(f"    [dim]{note_path}[/dim]")
        console.print()
        console.print(f"[dim]Total: {len(hidden_notes)} hidden notes[/dim]")
        return

    if args.hide_action == 'unhide':
        note_path = args.note_path

        if CONFIG.unhide_note(note_path):
            console.print(f"[green]✓[/green] Unhidden note: [cyan]{note_path}[/cyan]")
        else:
            console.print(f"[red]Note not found in hidden list:[/red] {note_path}")
        return


# Command registration for main.py
COMMAND = {
    'names': ['hide'],
    'setup_parser': setup_parser,
    'handler': handle_hide_command
}
