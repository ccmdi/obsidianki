"""Command-line configuration and tag management"""

import json
import re
from pathlib import Path
from rich.prompt import Confirm
from rich.panel import Panel
from rich.text import Text
from config import ConfigManager, CONFIG_FILE, CONFIG_DIR, console

def strip_html_for_terminal(text: str) -> str:
    """Strip HTML tags for cleaner terminal display"""
    # Remove HTML tags but keep the content
    text = re.sub(r'<[^>]+>', '', text)
    # Convert HTML entities
    text = text.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
    return text

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

def approve_note(note_title: str, note_path: str) -> bool:
    """Ask user to approve note processing"""
    console.print(f"   [magenta]Review note:[/magenta] [bold]{note_title}[/bold]")
    console.print(f"   [dim]Path: {note_path}[/dim]")

    try:
        result = Confirm.ask("   Process this note?", default=True)
        console.print()  # Add newline after approval
        return result
    except KeyboardInterrupt:
        raise

def approve_flashcard(flashcard: dict, note_title: str) -> bool:
    """Ask user to approve flashcard before adding to Anki"""
    console.print(f"   [magenta]Review flashcard from:[/magenta] [bold]{note_title}[/bold]")
    front_clean = strip_html_for_terminal(flashcard.get('front', 'N/A'))
    back_clean = strip_html_for_terminal(flashcard.get('back', 'N/A'))
    console.print(f"   [cyan]Front:[/cyan] {front_clean}")
    console.print(f"   [cyan]Back:[/cyan] {back_clean}")
    console.print()

    try:
        result = Confirm.ask("   Add this card to Anki?", default=True)
        console.print()  # Add newline after approval
        return result
    except KeyboardInterrupt:
        raise

def handle_config_command(args):
    """Handle config management commands"""

    # Handle help request
    if hasattr(args, 'help') and args.help:
        show_simple_help("Configuration Management", {
            "config list": "List all configuration settings",
            "config get <key>": "Get a configuration value",
            "config set <key> <value>": "Set a configuration value",
            "config reset": "Reset configuration to defaults",
            "config where": "Show configuration directory path"
        })
        return

    if args.config_action is None:
        show_simple_help("Configuration Management", {
            "config list": "List all configuration settings",
            "config get <key>": "Get a configuration value",
            "config set <key> <value>": "Set a configuration value",
            "config reset": "Reset configuration to defaults",
            "config where": "Show configuration directory path"
        })
        return

    if args.config_action == 'where':
        console.print(str(CONFIG_DIR))
        return

    if args.config_action == 'list':
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

    if args.config_action == 'get':
        try:
            with open(CONFIG_FILE, 'r') as f:
                user_config = json.load(f)

            key_upper = args.key.upper()
            if key_upper in user_config:
                console.print(f"{user_config[key_upper]}")
            else:
                console.print(f"[red]Configuration key '{args.key}' not found.[/red]")
                console.print("[dim]Use 'oki config list' to see available keys.[/dim]")
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
            "tag list": "List all tag weights and exclusions",
            "tag add <tag> <weight>": "Add or update a tag weight",
            "tag remove <tag>": "Remove a tag weight",
            "tag exclude <tag>": "Add tag to exclusion list",
            "tag include <tag>": "Remove tag from exclusion list"
        })
        return

    if args.tag_action is None:
        show_simple_help("Tag Management", {
            "tag list": "List all tag weights and exclusions",
            "tag add <tag> <weight>": "Add or update a tag weight",
            "tag remove <tag>": "Remove a tag weight",
            "tag exclude <tag>": "Add tag to exclusion list",
            "tag include <tag>": "Remove tag from exclusion list"
        })
        return

    config = ConfigManager()

    if args.tag_action == 'list':
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
        config.tag_weights[args.tag] = args.weight
        config.save_tag_schema()
        console.print(f"[green]✓[/green] Added tag [cyan]{args.tag}[/cyan] with weight [bold]{args.weight}[/bold]")
        return

    if args.tag_action == 'remove':
        if args.tag in config.tag_weights:
            del config.tag_weights[args.tag]
            config.save_tag_schema()
            console.print(f"[green]✓[/green] Removed tag [cyan]{args.tag}[/cyan]")
        else:
            console.print(f"[red]Tag '{args.tag}' not found.[/red]")
        return

    if args.tag_action == 'exclude':
        if args.tag not in config.excluded_tags:
            config.excluded_tags.append(args.tag)
            config.save_tag_schema()
            console.print(f"[green]✓[/green] Added [cyan]{args.tag}[/cyan] to exclusion list")
        else:
            console.print(f"[yellow]Tag '{args.tag}' is already excluded[/yellow]")
        return

    if args.tag_action == 'include':
        if args.tag in config.excluded_tags:
            config.excluded_tags.remove(args.tag)
            config.save_tag_schema()
            console.print(f"[green]✓[/green] Removed [cyan]{args.tag}[/cyan] from exclusion list")
        else:
            console.print(f"[yellow]Tag '{args.tag}' is not in exclusion list[/yellow]")
        return


def handle_history_command(args):
    """Handle history management commands"""

    # Handle help request
    if hasattr(args, 'help') and args.help:
        show_simple_help("History Management", {
            "history clear": "Clear processing history",
            "history stats": "Show flashcard generation statistics"
        })
        return

    if args.history_action is None:
        show_simple_help("History Management", {
            "history clear": "Clear processing history",
            "history stats": "Show flashcard generation statistics"
        })
        return

    if args.history_action == 'clear':
        from config import PROCESSING_HISTORY_FILE
        history_file = CONFIG_DIR / PROCESSING_HISTORY_FILE

        if not history_file.exists():
            console.print("[yellow]No processing history found.[/yellow]")
            return

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
        from config import PROCESSING_HISTORY_FILE
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