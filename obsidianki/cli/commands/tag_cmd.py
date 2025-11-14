"""Tag management command handler"""

from obsidianki.cli.config import CONFIG, console
from obsidianki.cli.help_utils import show_simple_help


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
