"""Configuration management command handler"""

import json
from rich.prompt import Confirm

from obsidianki.cli.config import CONFIG_FILE, CONFIG_DIR, console
from obsidianki.cli.help_utils import show_simple_help


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

        from obsidianki.cli.config import DEFAULT_CONFIG

        key_upper = args.key.upper()
        # Check if key exists in DEFAULT_CONFIG (support new config keys)
        if key_upper not in DEFAULT_CONFIG:
            console.print(f"[red]Configuration key '{args.key}' not found.[/red]")
            console.print("[dim]Use 'oki config list' to see available keys.[/dim]")
            return

        # Try to convert value to appropriate type
        value = args.value
        # Use value from user_config if exists, otherwise from DEFAULT_CONFIG
        current_value = user_config.get(key_upper, DEFAULT_CONFIG[key_upper])

        # Special validation for DIFFICULTY
        if key_upper == 'DIFFICULTY':
            if value not in ('easy', 'normal', 'hard', 'none'):
                console.print(f"[red]Invalid difficulty: {value}[/red]")
                console.print("[dim]Valid options: easy, normal, hard[/dim]")
                return

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
