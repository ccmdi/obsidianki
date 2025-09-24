"""Command-line configuration and tag management"""

import json
from rich.prompt import Confirm
from rich.panel import Panel
from rich.text import Text
from cli.models import Note, Flashcard

from cli.config import ConfigManager, CONFIG_FILE, CONFIG_DIR, console

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
    """Ask user to approve note processing"""
    console.print(f"   [dim]Path: {note.path}[/dim]")

    if note is not None:
        weight = note.get_sampling_weight()
        if weight == 0:
            console.print(f"   [yellow]WARNING:[/yellow] This note has 0 weight")

    try:
        result = Confirm.ask("   Process this note?", default=True)
        console.print()
        return result
    except KeyboardInterrupt:
        raise
    except Exception as e:
        raise

def approve_flashcard(flashcard: Flashcard, note: Note) -> bool:
    """Ask user to approve Flashcard object before adding to Anki"""
    #TODO add debugging for this
    front_clean = flashcard.front_original or flashcard.front
    back_clean = flashcard.back or flashcard.back_original

    console.print(f"   [cyan]Front:[/cyan] {front_clean}")
    console.print(f"   [cyan]Back:[/cyan] {back_clean}")
    console.print()

    try:
        result = Confirm.ask("   Add this card to Anki?", default=True)
        console.print()
        return result
    except KeyboardInterrupt:
        raise
    except Exception as e:
        raise

def handle_config_command(args):
    """Handle config management commands"""

    # Handle help request
    if hasattr(args, 'help') and args.help:
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
    if hasattr(args, 'help') and args.help:
        show_simple_help("Tag Management", {
            "tag": "List all tag weights and exclusions",
            "tag add <tag> <weight>": "Add or update a tag weight",
            "tag remove <tag>": "Remove a tag weight",
            "tag exclude <tag>": "Add tag to exclusion list",
            "tag include <tag>": "Remove tag from exclusion list"
        })
        return

    config = ConfigManager() #TODO

    if args.tag_action is None:
        # Default action: list tags (same as old 'list' command)
        weights = config.get_tag_weights()
        excluded = config.get_excluded_tags()

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
        if config.add_tag_weight(tag, args.weight):
            console.print(f"[green]✓[/green] Added tag [cyan]{tag}[/cyan] with weight [bold]{args.weight}[/bold]")
        return

    if args.tag_action == 'remove':
        tag = args.tag if args.tag.startswith('#') or args.tag == '_default' else f"#{args.tag}"
        if config.remove_tag_weight(tag):
            console.print(f"[green]✓[/green] Removed tag [cyan]{tag}[/cyan] from weight list")
        else:
            console.print(f"[red]Tag '{tag}' not found.[/red]")
        return

    if args.tag_action == 'exclude':
        tag = args.tag if args.tag.startswith('#') else f"#{args.tag}"
        if config.add_excluded_tag(tag):
            console.print(f"[green]✓[/green] Added [cyan]{tag}[/cyan] to exclusion list")
        else:
            console.print(f"[yellow]Tag '{tag}' is already excluded[/yellow]")
        return

    if args.tag_action == 'include':
        tag = args.tag if args.tag.startswith('#') else f"#{args.tag}"
        if config.remove_excluded_tag(tag):
            console.print(f"[green]✓[/green] Removed [cyan]{tag}[/cyan] from exclusion list")
        else:
            console.print(f"[yellow]Tag '{tag}' is not in exclusion list[/yellow]")
        return


def handle_history_command(args):
    """Handle history management commands"""

    # Handle help request
    if hasattr(args, 'help') and args.help:
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
        from cli.config import PROCESSING_HISTORY_FILE
        history_file = CONFIG_DIR / PROCESSING_HISTORY_FILE

        if not history_file.exists():
            console.print("[yellow]No processing history found.[/yellow]")
            return

        # Check if specific notes were requested
        if hasattr(args, 'notes') and args.notes:
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
        from cli.config import PROCESSING_HISTORY_FILE
        history_file = CONFIG_DIR / PROCESSING_HISTORY_FILE

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
                elif key == b' ':  # Space
                    return 'space'
                elif key == b'\r':  # Enter
                    return 'enter'
                elif key == b'\t':  # Tab
                    return 'tab'
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
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return None

    selected_indices = set()
    current_index = 0
    page_size = 15
    current_page = 0
    show_back = False  # Toggle between front and back view

    def create_display():
        start_idx = current_page * page_size
        end_idx = min(start_idx + page_size, len(all_cards))

        # Get terminal width and calculate column widths
        terminal_width = console.size.width
        # Reserve space for ID with indicators (8), and minimal padding/borders (~6)
        content_width = terminal_width - 14

        # Determine what to show based on toggle
        content_label = "Back" if show_back else "Front"
        table_title = f"Select Cards to Edit (Page {current_page + 1}) - Showing {content_label}"

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

            # Truncate text to fit column width
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
        # Windows-optimized display refresh
        refresh_rate = 60 if os.name == 'nt' else 10  # Higher refresh for smoother Windows experience

        with Live(create_display(), refresh_per_second=refresh_rate, screen=True) as live:
            needs_update = True

            while True:
                # Only update display when needed to reduce lag
                if needs_update:
                    live.update(create_display())
                    needs_update = False

                key = get_key()
                if key == 'up':
                    current_index = max(0, current_index - 1)
                    if current_index < current_page * page_size:
                        current_page = max(0, current_page - 1)
                    needs_update = True
                elif key == 'down':
                    current_index = min(len(all_cards) - 1, current_index + 1)
                    if current_index >= (current_page + 1) * page_size:
                        current_page = min((len(all_cards) - 1) // page_size, current_page + 1)
                    needs_update = True
                elif key == 'space':
                    if current_index in selected_indices:
                        selected_indices.remove(current_index)
                    else:
                        selected_indices.add(current_index)
                    needs_update = True
                elif key == 'tab':
                    show_back = not show_back
                    needs_update = True
                elif key == 'enter':
                    if selected_indices:
                        return [all_cards[i] for i in sorted(selected_indices)]
                elif key == 'escape':
                    return None

    except Exception as e:
        console.print(f"[red]Error with interactive selector: {e}[/red]")


def edit_mode(args):
    """
    Entry point for interactive editing of existing flashcards.
    """
    from cli.config import console, DECK, APPROVE_CARDS
    from cli.models import Note, Flashcard
    from cli.services import ANKI, AI
    from rich.panel import Panel
    from rich.prompt import Prompt

    deck_name = args.deck if args.deck else DECK

    console.print(Panel("ObsidianKi - Editing mode", style="bold blue"))
    console.print(f"[cyan]TARGET DECK:[/cyan] {deck_name}")
    console.print()

    # Test connections
    if not ANKI.test_connection():
        console.print("[red]ERROR:[/red] Cannot connect to AnkiConnect")
        return 0

    # Get all cards from deck
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
        console.print(f"  [cyan]Original Back:[/cyan] {original_card['back']}")
        console.print(f"  [cyan]Updated Back:[/cyan] {edited_card['back']}")
        console.print()

        # Convert to Flashcard object for approval if needed
        if APPROVE_CARDS:
            dummy_note = Note(path="editing", filename="Card Editing", content="", tags=[])
            flashcard = Flashcard(
                front=edited_card['front'],
                back=edited_card['back'],
                origin=edited_card.get('origin', original_card.get('origin', ''))
            )

            if not approve_flashcard(flashcard, dummy_note):
                console.print("  [yellow]Skipping this card[/yellow]")
                continue

        # Update the card in Anki
        if ANKI.update_note(
            original_card['noteId'],
            edited_card['front'],
            edited_card['back'],
            edited_card.get('origin', original_card.get('origin', ''))
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
    if hasattr(args, 'help') and args.help:
        show_simple_help("Deck Management", {
            "deck": "List all Anki decks",
            "deck -m": "List all Anki decks with card counts",
            "deck rename <old_name> <new_name>": "Rename a deck"
        })
        return

    # Import here to avoid circular imports and startup delays
    from cli.services import ANKI

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
        show_metadata = hasattr(args, 'metadata') and args.metadata

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