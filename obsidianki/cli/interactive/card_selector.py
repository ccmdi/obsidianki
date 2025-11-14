"""Interactive card selector for editing mode"""

import sys
import os
import time
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.console import Group

from obsidianki.cli.config import console
from obsidianki.cli.utils import strip_html


def create_card_selector(all_cards):
    """Create a cross-platform interactive card selector"""

    def get_key():
        """Cross-platform key reading with Windows optimization"""
        if os.name == 'nt':  # Windows
            import msvcrt

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
