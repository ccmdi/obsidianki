"""Interactive approval workflows for notes and flashcards"""

import sys
import os
from rich.prompt import Confirm
from rich.table import Table
from rich.padding import Padding

from obsidianki.cli.models import Note, Flashcard
from obsidianki.cli.config import CONFIG, console


def approve_note(note: Note) -> bool:
    """Ask user to approve note processing.

    Returns:
        bool: True if note should be processed, False if skipped or hidden.
    """
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
    console.print(f"   [dim]Path: {note.to_obsidian_link_rich()} {metadata}[/dim]")

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
    front_clean = flashcard.get_clean_front()
    back_clean = flashcard.get_clean_back()

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
