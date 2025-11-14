"""Processing history management command handler"""

import json
from pathlib import Path
from rich.prompt import Confirm

from obsidianki.cli.config import CONFIG, console
from obsidianki.cli.help_utils import show_simple_help


def handle_history_command(args):
    """Handle history management commands"""

    # Handle help request
    if args.help:
        show_simple_help("History Management", {
            "history clear": "Clear all processing history",
            "history clear --notes <patterns>": "Clear history for specific notes/patterns only",
            "history stats": "Show flashcard generation statistics"
        })
        return

    if args.history_action is None:
        show_simple_help("History Management", {
            "history clear": "Clear all processing history",
            "history clear --notes <patterns>": "Clear history for specific notes/patterns only",
            "history stats": "Show flashcard generation statistics"
        })
        return

    if args.history_action == 'clear':
        history_file = CONFIG.processing_history_file

        if not history_file.exists():
            console.print("[yellow]No processing history found.[/yellow]")
            return

        # Check if specific notes were requested
        if args.notes:
            # Selective clearing for specific notes
            try:
                with open(history_file, 'r') as f:
                    history_data = json.load(f)

                if not history_data:
                    console.print("[yellow]No processing history found[/yellow]")
                    return

                # Find matching notes
                notes_to_clear = []
                for pattern in args.notes:
                    # Simple pattern matching - if pattern contains *, use substring matching
                    if '*' in pattern:
                        # Convert pattern to substring check
                        pattern_part = pattern.replace('*', '')
                        matching_notes = [note_path for note_path in history_data.keys()
                                        if pattern_part in note_path]
                    else:
                        # Exact or partial name matching
                        matching_notes = [note_path for note_path in history_data.keys()
                                        if pattern in note_path]

                    notes_to_clear.extend(matching_notes)

                # Remove duplicates
                notes_to_clear = list(set(notes_to_clear))

                if not notes_to_clear:
                    console.print(f"[yellow]No notes found matching the patterns: {', '.join(args.notes)}[/yellow]")
                    return

                console.print(f"[cyan]Found {len(notes_to_clear)} notes to clear:[/cyan]")
                for note in notes_to_clear:
                    console.print(f"  [dim]{note}[/dim]")

                if Confirm.ask(f"Clear history for these {len(notes_to_clear)} notes?", default=False):
                    # Remove selected notes from history
                    for note_path in notes_to_clear:
                        if note_path in history_data:
                            del history_data[note_path]

                    # Save updated history
                    with open(history_file, 'w') as f:
                        json.dump(history_data, f, indent=2)

                    console.print(f"[green]✓[/green] Cleared history for {len(notes_to_clear)} notes")
                else:
                    console.print("[yellow]Operation cancelled[/yellow]")

            except json.JSONDecodeError:
                console.print("[red]Invalid history file format[/red]")
            except Exception as e:
                console.print(f"[red]Error processing history: {e}[/red]")
        else:
            # Clear all history (original behavior)
            try:
                if Confirm.ask("Clear all processing history? This will remove deduplication data.", default=False):
                    history_file.unlink()
                    console.print("[green]✓[/green] Processing history cleared")
                else:
                    console.print("[yellow]Operation cancelled[/yellow]")
            except KeyboardInterrupt:
                raise
        return

    if args.history_action == 'stats':
        history_file = CONFIG.processing_history_file

        if not history_file.exists():
            console.print("[yellow]No processing history found[/yellow]")
            console.print("[dim]Generate some flashcards first to see statistics[/dim]")
            return

        try:
            with open(history_file, 'r') as f:
                history_data = json.load(f)

            if not history_data:
                console.print("[yellow]No processing history found[/yellow]")
                return

            # Calculate stats
            total_notes = len(history_data)
            total_flashcards = sum(note_data.get("total_flashcards", 0) for note_data in history_data.values())

            # Sort notes by flashcard count (descending)
            sorted_notes = sorted(
                history_data.items(),
                key=lambda x: x[1].get("total_flashcards", 0),
                reverse=True
            )

            console.print("[bold blue]Flashcard Generation Statistics[/bold blue]")
            console.print()
            console.print(f"  [cyan]Total notes processed:[/cyan] {total_notes}")
            console.print(f"  [cyan]Total flashcards created:[/cyan] {total_flashcards}")
            if total_notes > 0:
                avg_cards = total_flashcards / total_notes
                console.print(f"  [cyan]Average cards per note:[/cyan] {avg_cards:.1f}")
            console.print()

            console.print("[bold blue]Top Notes by Flashcard Count[/bold blue]")

            # Show top 15 notes (or all if fewer than 15)
            top_notes = sorted_notes[:15]
            if not top_notes:
                console.print("[dim]No notes processed yet[/dim]")
                return

            for i, (note_path, note_data) in enumerate(top_notes, 1):
                flashcard_count = note_data.get("total_flashcards", 0)
                note_size = note_data.get("size", 0)

                # Calculate density (flashcards per KB)
                density = (flashcard_count / (note_size / 1000)) if note_size > 0 else 0

                # Extract just filename from path for cleaner display
                note_name = Path(note_path).name

                console.print(f"  [dim]{i:2d}.[/dim] [cyan]{note_name}[/cyan]")
                console.print(f"       [bold]{flashcard_count}[/bold] cards • {note_size:,} chars • {density:.1f} cards/KB")

            if len(sorted_notes) > 15:
                remaining = len(sorted_notes) - 15
                console.print(f"\n[dim]... and {remaining} more notes[/dim]")

            console.print()

        except json.JSONDecodeError:
            console.print("[red]Invalid history file format[/red]")
        except Exception as e:
            console.print(f"[red]Error reading history: {e}[/red]")
        return
