"""Command-line configuration and tag management"""

import json
from rich.prompt import Confirm
from rich.panel import Panel
from rich.text import Text
from obsidianki.cli.models import Note, Flashcard
from obsidianki.cli.utils import create_obsidian_link

from obsidianki.cli.config import CONFIG_FILE, CONFIG_DIR, console, CONFIG

def show_command_help(title: str, commands: dict, command_prefix: str = "oki"):
    """Display help for a command group in consistent style"""
    console.print(Panel(
        Text(title, style="bold blue"),
        style="blue",
        padding=(0, 1)
    ))
    console.print()

    for cmd, desc in commands.items():
        console.print(f"  [cyan]{command_prefix} {cmd}[/cyan]")
        console.print(f"    {desc}")
        console.print()

def show_simple_help(title: str, commands: dict):
    """Display simple help without panels for inline commands"""
    console.print(f"[bold blue]{title}[/bold blue]")
    console.print()

    for cmd, desc in commands.items():
        console.print(f"  [cyan]oki {cmd}[/cyan] - {desc}")
    console.print()

def approve_note(note: Note) -> bool:
    """Ask user to approve note processing.

    Returns:
        bool: True if note should be processed, False if skipped or hidden.
    """
    import sys
    import os
    from rich.table import Table

    weight = note.get_sampling_weight()
    total_cards = 0
    deck_cards = 0
    has_deck_info = False

    if note.path in CONFIG.processing_history:
        history = CONFIG.processing_history[note.path]
        total_cards = history.get("total_flashcards", 0)

        # Check if we have deck information
        decks = history.get("decks", {})
        has_deck_info = bool(decks)

        if CONFIG.DECK and "decks" in history:
            deck_cards = history["decks"].get(CONFIG.DECK, 0)

    if deck_cards > 0:
        metadata = f"[dim](W {weight:.2f} | D {deck_cards} | T {total_cards})[/dim]"
    else:
        metadata = f"[dim](W {weight:.2f} | T {total_cards})[/dim]"

    # Format: NOTE TITLE (W <weight> | D <deck> | T <total>)
    console.print(f"   [dim]Path: {create_obsidian_link(note)} {metadata}[/dim]")

    if weight == 0:
        console.print(f"   [yellow]WARNING:[/yellow] This note has 0 weight")

    def show_deck_breakdown():
        """Display deck breakdown for the note."""
        if note.path not in CONFIG.processing_history:
            return

        history = CONFIG.processing_history[note.path]
        decks = history.get("decks", {})

        if not decks:
            return

        # Create a table for deck breakdown
        from rich.padding import Padding
        table = Table(show_header=True, header_style="bold magenta", box=None, padding=(0, 2))
        table.add_column("Deck", style="cyan")
        table.add_column("Cards", justify="right", style="green")

        for deck_name, card_count in sorted(decks.items()):
            table.add_row(deck_name, str(card_count))

        table.add_row("", "", style="dim")
        table.add_row("TOTAL", str(history.get("total_flashcards", 0)), style="bold")

        padded_table = Padding(table, (0, 0, 0, 3))
        console.print(padded_table)
        console.print()

    def get_deck_line_count():
        """Calculate how many lines the deck breakdown takes up."""
        if note.path not in CONFIG.processing_history:
            return 0

        history = CONFIG.processing_history[note.path]
        decks = history.get("decks", {})

        if not decks:
            return 0

        # 1 blank line + 1 header line + 1 table header + len(decks) rows + 1 separator + 1 total + 1 blank
        return 1 + len(decks) + 3

    def get_input_with_keyboard_listener():
        """Custom input that listens for Ctrl+D to toggle deck breakdown."""
        # Build the prompt text
        prompt_text = "   Process this note? [magenta](y/n/hide)[/magenta]"
        if has_deck_info:
            prompt_text += " [dim](Ctrl+D)[/dim]"

        showing_deck = False
        deck_lines = 0

        if os.name == 'nt':  # Windows
            import msvcrt

            console.print(prompt_text, end=" ")
            sys.stdout.flush()

            input_buffer = []

            while True:
                if msvcrt.kbhit():
                    key = msvcrt.getch()

                    # Check for Ctrl+D (0x04)
                    if key == b'\x04' and has_deck_info:
                        # Clear current input line first
                        sys.stdout.write('\r\033[K')
                        sys.stdout.flush()

                        if not showing_deck:
                            # Show the breakdown
                            console.print()
                            show_deck_breakdown()
                            deck_lines = get_deck_line_count()
                            showing_deck = True
                        else:
                            # Clear the deck breakdown lines by moving up
                            for _ in range(deck_lines + 1):  # +1 for the newline before deck
                                sys.stdout.write('\033[F')  # Move cursor up
                                sys.stdout.write('\033[K')  # Clear line
                            sys.stdout.flush()
                            showing_deck = False

                        # Re-print prompt and input buffer
                        console.print(prompt_text, end=" ")
                        for char in input_buffer:
                            sys.stdout.write(char)
                        sys.stdout.flush()
                        continue

                    # Regular key handling
                    if key == b'\r':  # Enter
                        console.print()
                        result = ''.join(input_buffer).strip().lower()
                        return result if result else 'y'
                    elif key == b'\x08':  # Backspace
                        if input_buffer:
                            input_buffer.pop()
                            sys.stdout.write('\b \b')
                            sys.stdout.flush()
                    elif key == b'\x1b':  # Escape
                        raise KeyboardInterrupt()
                    elif len(key) == 1 and 32 <= ord(key) <= 126:  # Printable character
                        char = key.decode('utf-8')
                        input_buffer.append(char)
                        sys.stdout.write(char)
                        sys.stdout.flush()

        else:  # Unix/Linux/Mac
            import tty
            import termios
            import select

            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)

            try:
                tty.setraw(fd)
                console.print(prompt_text, end=" ")
                sys.stdout.flush()

                input_buffer = []

                while True:
                    if select.select([sys.stdin], [], [], 0.1)[0]:
                        char = sys.stdin.read(1)

                        # Check for Ctrl+D (0x04)
                        if char == '\x04' and has_deck_info:
                            # Clear current input line first
                            sys.stdout.write('\r\033[K')
                            sys.stdout.flush()

                            if not showing_deck:
                                # Show the breakdown
                                console.print()
                                show_deck_breakdown()
                                deck_lines = get_deck_line_count()
                                showing_deck = True
                            else:
                                # Clear the deck breakdown lines by moving up
                                for _ in range(deck_lines + 1):  # +1 for the newline before deck
                                    sys.stdout.write('\033[F')  # Move cursor up
                                    sys.stdout.write('\033[K')  # Clear line
                                sys.stdout.flush()
                                showing_deck = False

                            # Re-print prompt and input buffer
                            console.print(prompt_text, end=" ")
                            for c in input_buffer:
                                sys.stdout.write(c)
                            sys.stdout.flush()
                            continue

                        # Check for ESC
                        if char == '\x1b':
                            # Could be an escape sequence, check for more
                            if select.select([sys.stdin], [], [], 0.1)[0]:
                                # Read the rest of the sequence and ignore
                                sys.stdin.read(1)
                                continue
                            else:
                                # Just ESC, treat as cancel
                                raise KeyboardInterrupt()

                        # Enter
                        if char == '\r' or char == '\n':
                            console.print()
                            result = ''.join(input_buffer).strip().lower()
                            return result if result else 'y'
                        # Backspace
                        elif char == '\x7f':
                            if input_buffer:
                                input_buffer.pop()
                                sys.stdout.write('\b \b')
                                sys.stdout.flush()
                        # Printable character
                        elif 32 <= ord(char) <= 126:
                            input_buffer.append(char)
                            sys.stdout.write(char)
                            sys.stdout.flush()

            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    try:
        while True:
            choice = get_input_with_keyboard_listener()

            console.print()

            if choice == "hide":
                CONFIG.hide_note(note.path)
                console.print(f"   [yellow]Note hidden permanently[/yellow]")
                return False

            if choice in ["y", "n"]:
                return choice == "y"

            # Invalid input, re-prompt
            console.print(f"   [yellow]Invalid choice. Please enter y, n, or hide[/yellow]")

    except KeyboardInterrupt:
        raise
    except Exception:
        raise

def approve_flashcard(flashcard: Flashcard) -> bool:
    """Ask user to approve Flashcard object before adding to Anki"""
    from rich.padding import Padding

    front_clean = flashcard.front_original or flashcard.front
    back_clean = flashcard.back_original or flashcard.back

    # Print with padding to maintain indentation on newlines
    console.print(Padding(f"[cyan]Front:[/cyan] {front_clean}", (0, 0, 0, 3)))
    console.print(Padding(f"[cyan]Back:[/cyan] {back_clean}", (0, 0, 0, 3)))
    console.print()

    try:
        result = Confirm.ask("   Add this card to Anki?", default=True, console=console)
        console.print()
        return result
    except KeyboardInterrupt:
        raise
    except Exception as e:
        raise

def handle_config_command(args):
    """Handle config management commands"""

    # Handle help request
    if args.help:
        show_simple_help("Configuration Management", {
            "config": "List all configuration settings",
            "config get <key>": "Get a configuration value",
            "config set <key> <value>": "Set a configuration value",
            "config reset": "Reset configuration to defaults",
            "config where": "Show configuration directory path"
        })
        return

    if args.config_action is None:
        # Default action: list configuration (same as old 'list' command)
        try:
            with open(CONFIG_FILE, 'r') as f:
                user_config = json.load(f)
        except FileNotFoundError:
            console.print("[red]No configuration file found. Run 'oki --setup' first.[/red]")
            return
        except json.JSONDecodeError:
            console.print("[red]Invalid configuration file. Run 'oki --setup' to reset.[/red]")
            return

        console.print("[bold blue]Current Configuration[/bold blue]")
        for key, value in sorted(user_config.items()):
            console.print(f"  [cyan]{key.lower()}:[/cyan] {value}")
        console.print()
        return

    if args.config_action == 'where':
        console.print(str(CONFIG_DIR))
        return

    if args.config_action == 'get':
        try:
            with open(CONFIG_FILE, 'r') as f:
                user_config = json.load(f)

            key_upper = args.key.upper()
            if key_upper in user_config:
                console.print(f"{user_config[key_upper]}")
            else:
                console.print(f"[red]Configuration key '{args.key}' not found.[/red]")
        except FileNotFoundError:
            console.print("[red]No configuration file found. Run 'oki --setup' first.[/red]")
        return

    if args.config_action == 'set':
        try:
            with open(CONFIG_FILE, 'r') as f:
                user_config = json.load(f)
        except FileNotFoundError:
            console.print("[red]No configuration file found. Run 'oki --setup' first.[/red]")
            return

        key_upper = args.key.upper()
        if key_upper not in user_config:
            console.print(f"[red]Configuration key '{args.key}' not found.[/red]")
            console.print("[dim]Use 'oki config list' to see available keys.[/dim]")
            return

        # Try to convert value to appropriate type
        value = args.value
        current_value = user_config[key_upper]

        if isinstance(current_value, bool):
            value = value.lower() in ('true', '1', 'yes', 'on')
        elif isinstance(current_value, int):
            try:
                value = int(value)
            except ValueError:
                console.print(f"[red]Invalid integer value: {value}[/red]")
                return
        elif isinstance(current_value, float):
            try:
                value = float(value)
            except ValueError:
                console.print(f"[red]Invalid float value: {value}[/red]")
                return

        user_config[key_upper] = value

        with open(CONFIG_FILE, 'w') as f:
            json.dump(user_config, f, indent=2)

        console.print(f"[green]✓[/green] Set [cyan]{args.key.lower()}[/cyan] = [bold]{value}[/bold]")
        return

    if args.config_action == 'reset':
        try:
            if Confirm.ask("Reset all configuration to defaults?", default=False):
                if CONFIG_FILE.exists():
                    CONFIG_FILE.unlink()
                console.print("[green]✓[/green] Configuration reset. Run [cyan]oki --setup[/cyan] to reconfigure")
        except KeyboardInterrupt:
            raise
        return


def handle_tag_command(args):
    """Handle tag management commands"""

    # Handle help request
    if args.help:
        show_simple_help("Tag Management", {
            "tag": "List all tag weights and exclusions",
            "tag add <tag> <weight>": "Add or update a tag weight",
            "tag remove <tag>": "Remove a tag weight",
            "tag exclude <tag>": "Add tag to exclusion list",
            "tag include <tag>": "Remove tag from exclusion list"
        })
        return

    if args.tag_action is None:
        # Default action: list tags (same as old 'list' command)
        weights = CONFIG.get_tag_weights()
        excluded = CONFIG.get_excluded_tags()

        if not weights and not excluded:
            console.print("[dim]No tag weights configured. Use 'oki tag add <tag> <weight>' to add tags.[/dim]")
            return

        if weights:
            console.print("[bold blue]Tag Weights[/bold blue]")
            for tag, weight in sorted(weights.items()):
                console.print(f"  [cyan]{tag}:[/cyan] {weight}")
            console.print()

        if excluded:
            console.print("[bold blue]Excluded Tags[/bold blue]")
            for tag in sorted(excluded):
                console.print(f"  [red]{tag}[/red]")
            console.print()
        return

    if args.tag_action == 'add':
        tag = args.tag if args.tag.startswith('#') or args.tag == '_default' else f"#{args.tag}"
        if CONFIG.add_tag_weight(tag, args.weight):
            console.print(f"[green]✓[/green] Added tag [cyan]{tag}[/cyan] with weight [bold]{args.weight}[/bold]")
        return

    if args.tag_action == 'remove':
        tag = args.tag if args.tag.startswith('#') or args.tag == '_default' else f"#{args.tag}"
        if CONFIG.remove_tag_weight(tag):
            console.print(f"[green]✓[/green] Removed tag [cyan]{tag}[/cyan] from weight list")
        else:
            console.print(f"[red]Tag '{tag}' not found.[/red]")
        return

    if args.tag_action == 'exclude':
        tag = args.tag if args.tag.startswith('#') else f"#{args.tag}"
        if CONFIG.add_excluded_tag(tag):
            console.print(f"[green]✓[/green] Added [cyan]{tag}[/cyan] to exclusion list")
        else:
            console.print(f"[yellow]Tag '{tag}' is already excluded[/yellow]")
        return

    if args.tag_action == 'include':
        tag = args.tag if args.tag.startswith('#') else f"#{args.tag}"
        if CONFIG.remove_excluded_tag(tag):
            console.print(f"[green]✓[/green] Removed [cyan]{tag}[/cyan] from exclusion list")
        else:
            console.print(f"[yellow]Tag '{tag}' is not in exclusion list[/yellow]")
        return


def handle_hide_command(args):
    """Handle hidden notes management commands"""
    from pathlib import Path

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
        from obsidianki.cli.config import CONFIG
        history_file = CONFIG.processing_history_file

        if not history_file.exists():
            console.print("[yellow]No processing history found.[/yellow]")
            return

        # Check if specific notes were requested
        if args.notes:
            # Selective clearing for specific notes
            try:
                import json
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
        from obsidianki.cli.config import CONFIG
        history_file = CONFIG.processing_history_file

        if not history_file.exists():
            console.print("[yellow]No processing history found[/yellow]")
            console.print("[dim]Generate some flashcards first to see statistics[/dim]")
            return

        try:
            import json
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
                from pathlib import Path
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


def _create_card_selector(all_cards):
    """Create a cross-platform interactive card selector"""
    import sys
    import os
    from rich.live import Live
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich.console import Group

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
                    elif key == b'K':  # Left arrow
                        return 'left'
                    elif key == b'M':  # Right arrow
                        return 'right'
                elif key == b' ':  # Space
                    return 'space'
                elif key == b'\r':  # Enter
                    return 'enter'
                elif key == b'\t':  # Tab
                    return 'tab'
                elif key == b'a':  # A key
                    return 'autoscroll'
                elif key == b'\x1b':  # Escape
                    return 'escape'

            # Small sleep to prevent 100% CPU usage
            time.sleep(0.01)
            return None
        else:  # Unix/Linux/Mac
            import tty, termios
            import select
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setraw(sys.stdin.fileno())
                key = sys.stdin.read(1)
                if key == '\x1b':  # Escape sequence - check if more data available
                    if select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], []):
                        key += sys.stdin.read(2)
                        if key == '\x1b[A':  # Up arrow
                            return 'up'
                        elif key == '\x1b[B':  # Down arrow
                            return 'down'
                        elif key == '\x1b[C':  # Right arrow
                            return 'right'
                        elif key == '\x1b[D':  # Left arrow
                            return 'left'
                        else:
                            return 'escape'
                    else:
                        return 'escape'  # Just escape key
                elif key == ' ':
                    return 'space'
                elif key == '\t':
                    return 'tab'
                elif key == '\r' or key == '\n':
                    return 'enter'
                elif key == 'a':
                    return 'autoscroll'
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return None

    selected_indices = set()
    current_index = 0
    page_size = 15
    current_page = 0
    show_back = False  # Toggle between front and back view
    scroll_offset = 0  # Horizontal scroll position for current card
    scroll_mode = False  # Whether we're in scroll mode
    autoscroll = False  # Whether autoscroll is active
    autoscroll_speed = 0.1  # Autoscroll speed in seconds (much faster!)
    autoscroll_pause_duration = 1.0  # Pause duration at start/end
    last_autoscroll_time = 0  # Last time autoscroll moved
    just_started_scroll = False  # Flag to skip initial delay

    def create_display():
        nonlocal scroll_offset, scroll_mode, autoscroll
        start_idx = current_page * page_size
        end_idx = min(start_idx + page_size, len(all_cards))

        # Get terminal width and calculate column widths
        terminal_width = console.size.width
        # Reserve space for ID with indicators (8), and minimal padding/borders (~6)
        content_width = terminal_width - 14

        # Determine what to show based on toggle
        content_label = "Back" if show_back else "Front"
        scroll_indicator = ""
        if scroll_mode and autoscroll:
            scroll_indicator = " [AUTO-SCROLL]"
        elif scroll_mode:
            scroll_indicator = " [SCROLL]"
        table_title = f"Select Cards to Edit (Page {current_page + 1}) - Showing {content_label}{scroll_indicator}"

        table = Table(title=table_title)
        table.add_column("ID", style="cyan", width=8, no_wrap=True)
        table.add_column(content_label, style="white", width=content_width, no_wrap=True)

        for i in range(start_idx, end_idx):
            card = all_cards[i]

            # Row styling based on current position and selection
            if i == current_index:
                style = "bold cyan"
                id_display = f"→ {i + 1}"
            else:
                style = "white"
                id_display = str(i + 1)

            # Add selection indicator to ID
            if i in selected_indices:
                id_display = f"☑ {id_display}"
            else:
                id_display = f"☐ {id_display}"

            # Get the content to display based on toggle
            content = card['back'] if show_back else card['front']

            # Replace newlines with spaces to force single line display
            content = content.replace('\n', ' ').replace('\r', ' ')

            # Handle scrolling for current card
            if i == current_index and scroll_mode:
                # Calculate scrollable area
                content_max = content_width - 6  # Account for scroll indicators
                if len(content) > content_max:
                    # Apply scroll offset
                    max_scroll = len(content) - content_max
                    actual_offset = min(scroll_offset, max_scroll)
                    scrolled_content = content[actual_offset:actual_offset + content_max]

                    # Add scroll indicators
                    left_indicator = "◀" if actual_offset > 0 else " "
                    right_indicator = "▶" if actual_offset < max_scroll else " "
                    display_content = f"{left_indicator}{scrolled_content}{right_indicator}"
                else:
                    display_content = content
            else:
                # Normal truncation for non-current or non-scroll cards
                content_max = content_width - 3  # Account for "..."
                display_content = content[:content_max] + "..." if len(content) > content_max else content

            table.add_row(
                id_display,
                display_content,
                style=style
            )

        # Instructions and status
        instructions = Text()
        instructions.append("Controls: ", style="bold cyan")
        instructions.append("(", style="white")
        instructions.append("Up/Down", style="cyan")
        instructions.append(") Navigate  ", style="white")
        instructions.append("(", style="white")
        instructions.append("Left/Right", style="cyan")
        instructions.append(") Scroll  ", style="white")
        instructions.append("(", style="white")
        instructions.append("A", style="cyan")
        instructions.append(") Auto-Scroll  ", style="white")
        instructions.append("(", style="white")
        instructions.append("Space", style="cyan")
        instructions.append(") Select  ", style="white")
        instructions.append("(", style="white")
        instructions.append("Tab", style="cyan")
        instructions.append(") Toggle View  ", style="white")
        instructions.append("(", style="white")
        instructions.append("Enter", style="cyan")
        instructions.append(") Confirm  ", style="white")
        instructions.append("(", style="white")
        instructions.append("Esc", style="cyan")
        instructions.append(") Cancel", style="white")

        status = Text()
        if selected_indices:
            status.append(f"Selected: {len(selected_indices)} cards", style="green")
            # Show selected card IDs
            selected_ids = sorted([i + 1 for i in selected_indices])
            status.append(f"\nIDs: {', '.join(map(str, selected_ids))}", style="dim green")
        else:
            status.append("No cards selected", style="yellow")

        return Group(table, "", instructions, "", status)

    try:
        import time
        # Windows-optimized display refresh
        refresh_rate = 60 if os.name == 'nt' else 10  # Higher refresh for smoother Windows experience

        with Live(create_display(), refresh_per_second=refresh_rate, screen=True) as live:
            needs_update = True

            while True:
                # Handle autoscroll
                current_time = time.time()
                if autoscroll and scroll_mode:
                    # Check if current card has overflowing text and can scroll more
                    card = all_cards[current_index]
                    content = card['back'] if show_back else card['front']
                    content = content.replace('\n', ' ').replace('\r', ' ')
                    content_max = (console.size.width - 14) - 6  # Account for scroll indicators

                    if len(content) > content_max:
                        max_scroll = len(content) - content_max

                        # Determine if we're at start/end for pause logic
                        at_start = scroll_offset == 0
                        at_end = scroll_offset >= max_scroll

                        # Use longer pause at start/end, but skip initial delay if just started
                        if just_started_scroll and at_start:
                            required_delay = 0  # No delay when user just pressed right
                        elif at_start or at_end:
                            required_delay = autoscroll_pause_duration
                        else:
                            required_delay = autoscroll_speed

                        if (current_time - last_autoscroll_time) >= required_delay:
                            if scroll_offset < max_scroll:
                                scroll_offset += 1  # Autoscroll by 1 char for smooth movement
                                last_autoscroll_time = current_time
                                just_started_scroll = False  # Clear the flag after first movement
                                needs_update = True
                            else:
                                # At end, reset to beginning for continuous loop
                                scroll_offset = 0
                                last_autoscroll_time = current_time
                                just_started_scroll = False  # Clear the flag
                                needs_update = True

                # Only update display when needed to reduce lag
                if needs_update:
                    live.update(create_display())
                    needs_update = False

                key = get_key()
                if key == 'up':
                    if scroll_mode:
                        scroll_mode = False
                        scroll_offset = 0
                        autoscroll = False
                    # Always move up regardless of scroll mode
                    current_index = max(0, current_index - 1)
                    if current_index < current_page * page_size:
                        current_page = max(0, current_page - 1)
                    needs_update = True
                elif key == 'down':
                    if scroll_mode:
                        scroll_mode = False
                        scroll_offset = 0
                        autoscroll = False
                    # Always move down regardless of scroll mode
                    current_index = min(len(all_cards) - 1, current_index + 1)
                    if current_index >= (current_page + 1) * page_size:
                        current_page = min((len(all_cards) - 1) // page_size, current_page + 1)
                    needs_update = True
                elif key == 'left':
                    if scroll_mode:
                        if autoscroll:
                            autoscroll = False  # Stop autoscroll when manually scrolling
                        scroll_offset = max(0, scroll_offset - 5)  # Scroll left by 5 chars
                        needs_update = True
                elif key == 'right':
                    # Check if current card has overflowing text
                    card = all_cards[current_index]
                    content = card['back'] if show_back else card['front']
                    content = content.replace('\n', ' ').replace('\r', ' ')
                    content_max = (console.size.width - 14) - 6  # Account for scroll indicators

                    if len(content) > content_max:
                        if not scroll_mode:
                            scroll_mode = True
                            scroll_offset = 0
                            autoscroll = True  # Start autoscroll by default!
                            just_started_scroll = True  # Flag to skip initial delay
                            last_autoscroll_time = time.time()
                        else:
                            if autoscroll:
                                autoscroll = False  # Stop autoscroll when manually scrolling
                            max_scroll = len(content) - content_max
                            scroll_offset = min(scroll_offset + 5, max_scroll)  # Scroll right by 5 chars
                        needs_update = True
                elif key == 'space':
                    if current_index in selected_indices:
                        selected_indices.remove(current_index)
                    else:
                        selected_indices.add(current_index)
                    needs_update = True
                elif key == 'tab':
                    show_back = not show_back
                    scroll_mode = False
                    scroll_offset = 0
                    autoscroll = False
                    needs_update = True
                elif key == 'autoscroll':
                    if scroll_mode:
                        autoscroll = not autoscroll
                        if autoscroll:
                            last_autoscroll_time = time.time()
                        needs_update = True
                elif key == 'enter':
                    if selected_indices:
                        from obsidianki.cli.utils import strip_html
                        selected_cards = []
                        for i in sorted(selected_indices):
                            card = all_cards[i].copy()
                            # Add original stripped versions for display/editing
                            card['front_original'] = strip_html(card['front'])
                            card['back_original'] = strip_html(card['back'])
                            selected_cards.append(card)
                        return selected_cards
                elif key == 'escape':
                    return None

    except Exception as e:
        console.print(f"[red]Error with interactive selector: {e}[/red]")


def edit_mode(args):
    """
    Entry point for interactive editing of existing flashcards.
    """
    from obsidianki.cli.models import Note, Flashcard
    from obsidianki.cli.services import ANKI, AI
    from rich.panel import Panel
    from rich.prompt import Prompt

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
        selected_cards = _create_card_selector(all_cards)

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


def handle_deck_command(args):
    """Handle deck management commands"""

    # Handle help request
    if args.help:
        show_simple_help("Deck Management", {
            "deck": "List all Anki decks",
            "deck -m": "List all Anki decks with card counts",
            "deck rename <old_name> <new_name>": "Rename a deck"
        })
        return

    # Import here to avoid circular imports and startup delays
    from obsidianki.cli.services import ANKI

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


def handle_template_command(args):
    """Handle template management commands"""
    import sys
    import shlex

    # Handle help request
    if args.help:
        show_simple_help("Template Management", {
            "template add <name> <command>": "Save a command template",
            "template use <name>": "Execute a saved template",
            "template remove <name>": "Remove a template"
        })
        return

    if args.template_action is None:
        templates = CONFIG.load_templates()

        if not templates:
            console.print("[yellow]No templates saved[/yellow]")
            console.print("\n[dim]Add a template with:[/dim] [cyan]oki template add <name> <command>[/cyan]")
            return

        console.print("[bold blue]Saved Templates[/bold blue]")
        console.print()

        for name, command in sorted(templates.items()):
            console.print(f"  [cyan]{name}[/cyan]")
            console.print(f"    [dim]oki {command}[/dim]")
            console.print()

    elif args.template_action == 'add':
        templates = CONFIG.load_templates()
        name = args.name
        command = args.template_command

        # Check if template already exists
        if name in templates:
            console.print(f"[yellow]WARNING:[/yellow] Template '[cyan]{name}[/cyan]' already exists")
            if not Confirm.ask("   Overwrite?", default=False):
                console.print("[yellow]Cancelled[/yellow]")
                return

        templates[name] = command

        if CONFIG.save_templates(templates):
            console.print(f"[green]✓[/green] Saved template '[cyan]{name}[/cyan]'")
            console.print(f"[dim]Use with:[/dim] [cyan]oki template use {name}[/cyan]")

    elif args.template_action == 'use':
        templates = CONFIG.load_templates()
        name = args.name

        if name not in templates:
            console.print(f"[red]ERROR:[/red] Template '[cyan]{name}[/cyan]' not found")
            return

        command = templates[name]
        console.print(f"[cyan]Executing template:[/cyan] [bold]{name}[/bold]")
        console.print(f"[dim]Command:[/dim] oki {command}")
        console.print()

        # Parse the command and re-invoke main with those arguments
        try:
            # Import main from this module's parent
            from obsidianki.main import main

            # Parse the command string into arguments
            cmd_args = shlex.split(command)

            # Replace sys.argv with the new arguments
            original_argv = sys.argv
            sys.argv = ['oki'] + cmd_args

            # Call main() with the new arguments
            result = main()

            # Restore original argv
            sys.argv = original_argv

            # Exit with the result code
            sys.exit(result if result is not None else 0)

        except Exception as e:
            console.print(f"[red]ERROR:[/red] Failed to execute template: {e}")
            sys.argv = original_argv

    elif args.template_action == 'remove':
        templates = CONFIG.load_templates()
        name = args.name

        if name not in templates:
            console.print(f"[red]ERROR:[/red] Template '[cyan]{name}[/cyan]' not found")
            return

        console.print(f"[yellow]Removing template:[/yellow] [cyan]{name}[/cyan]")
        console.print(f"[dim]Command:[/dim] oki {templates[name]}")

        if Confirm.ask("   Are you sure?", default=False):
            del templates[name]
            if CONFIG.save_templates(templates):
                console.print(f"[green]✓[/green] Removed template '[cyan]{name}[/cyan]'")
        else:
            console.print("[yellow]Cancelled[/yellow]")