"""Hidden notes management command handler"""

from pathlib import Path

from obsidianki.cli.config import CONFIG, console
from obsidianki.cli.help_utils import show_simple_help


def handle_hide_command(args):
    """Handle hidden notes management commands"""

    # Handle help request
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
