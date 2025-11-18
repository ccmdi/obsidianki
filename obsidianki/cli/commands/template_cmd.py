"""Template management command handler"""

import sys
import shlex
from rich.prompt import Confirm

from obsidianki.cli.config import CONFIG, console
from obsidianki.cli.help_utils import show_simple_help


def handle_template_command(args):
    """Handle template management commands"""

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

        override_args = getattr(args, 'override_args', []) or []

        console.print(f"[cyan]Executing template:[/cyan] [bold]{name}[/bold]")
        console.print(f"[dim]Command:[/dim] oki {command}")
        if override_args:
            console.print(f"[dim]Overrides:[/dim] {' '.join(override_args)}")
        console.print()

        # Parse the command and re-invoke main with those arguments
        try:
            from obsidianki.main import main

            cmd_args = shlex.split(command)

            # Merge: template args + override args (override args win for duplicates)
            final_args = cmd_args + override_args

            original_argv = sys.argv
            sys.argv = ['oki'] + final_args

            result = main()

            sys.argv = original_argv

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
