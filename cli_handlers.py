"""Command-line configuration and tag management"""

import json
from pathlib import Path
from rich.prompt import Confirm
from config import ConfigManager, CONFIG_FILE, CONFIG_DIR, console

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
    console.print(f"   [cyan]Front:[/cyan] {flashcard.get('front', 'N/A')}")
    console.print(f"   [cyan]Back:[/cyan] {flashcard.get('back', 'N/A')}")
    console.print()

    try:
        result = Confirm.ask("   Add this card to Anki?", default=True)
        console.print()  # Add newline after approval
        return result
    except KeyboardInterrupt:
        raise

def handle_config_command(args):
    """Handle config management commands"""

    if args.config_action == 'where':
        console.print(str(CONFIG_DIR))
        return

    if args.config_action == 'list':
        try:
            with open(CONFIG_FILE, 'r') as f:
                user_config = json.load(f)
        except FileNotFoundError:
            console.print("[red]No configuration file found. Run 'obsidianki --setup' first.[/red]")
            return
        except json.JSONDecodeError:
            console.print("[red]Invalid configuration file. Run 'obsidianki --setup' to reset.[/red]")
            return

        console.print("[bold cyan]Current Configuration:[/bold cyan]")
        for key, value in sorted(user_config.items()):
            console.print(f"  [green]{key.lower()}:[/green] {value}")
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
                console.print("[dim]Use 'obsidianki config list' to see available keys.[/dim]")
        except FileNotFoundError:
            console.print("[red]No configuration file found. Run 'obsidianki --setup' first.[/red]")
        return

    if args.config_action == 'set':
        try:
            with open(CONFIG_FILE, 'r') as f:
                user_config = json.load(f)
        except FileNotFoundError:
            console.print("[red]No configuration file found. Run 'obsidianki --setup' first.[/red]")
            return

        key_upper = args.key.upper()
        if key_upper not in user_config:
            console.print(f"[red]Configuration key '{args.key}' not found.[/red]")
            console.print("[dim]Use 'obsidianki config list' to see available keys.[/dim]")
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

        console.print(f"[green]Set {args.key.lower()} = {value}[/green]")
        return

    if args.config_action == 'reset':
        try:
            if Confirm.ask("Reset all configuration to defaults?", default=False):
                if CONFIG_FILE.exists():
                    CONFIG_FILE.unlink()
                console.print("[green]Configuration reset. Run 'obsidianki --setup' to reconfigure.[/green]")
        except KeyboardInterrupt:
            raise
        return


def handle_tag_command(args):
    """Handle tag management commands"""
    config = ConfigManager()

    if args.tag_action == 'list':
        weights = config.get_tag_weights()
        excluded = config.get_excluded_tags()

        if not weights and not excluded:
            console.print("[dim]No tag weights configured. Use 'obsidianki tag add <tag> <weight>' to add tags.[/dim]")
            return

        if weights:
            console.print("[bold cyan]Tag Weights:[/bold cyan]")
            for tag, weight in sorted(weights.items()):
                console.print(f"  [green]{tag}:[/green] {weight}")

        if excluded:
            console.print(f"\n[bold cyan]Excluded Tags:[/bold cyan]")
            for tag in sorted(excluded):
                console.print(f"  [red]{tag}[/red]")
        return

    if args.tag_action == 'add':
        config.tag_weights[args.tag] = args.weight
        config.save_tag_schema()
        console.print(f"[green]Added tag '{args.tag}' with weight {args.weight}[/green]")
        return

    if args.tag_action == 'remove':
        if args.tag in config.tag_weights:
            del config.tag_weights[args.tag]
            config.save_tag_schema()
            console.print(f"[green]Removed tag '{args.tag}'[/green]")
        else:
            console.print(f"[red]Tag '{args.tag}' not found.[/red]")
        return


def handle_history_command(args):
    """Handle history management commands"""

    if args.history_action == 'clear':
        history_file = CONFIG_DIR / "processing_history.json"

        if not history_file.exists():
            console.print("[yellow]No processing history found.[/yellow]")
            return

        try:
            if Confirm.ask("Clear all processing history? This will remove deduplication data.", default=False):
                history_file.unlink()
                console.print("[green]Processing history cleared.[/green]")
            else:
                console.print("[yellow]Operation cancelled.[/yellow]")
        except KeyboardInterrupt:
            raise
        return