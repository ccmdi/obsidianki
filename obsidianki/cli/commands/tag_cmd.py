"""Tag management command handler"""

from obsidianki.cli.config import CONFIG, console
from obsidianki.cli.help_utils import show_simple_help


def setup_parser(subparsers):
    """Setup argparse parser for tag command"""
    tag_parser = subparsers.add_parser('tag', aliases=['tags'], help='Manage tag weights', add_help=False)
    tag_parser.add_argument("-h", "--help", action="store_true", help="Show help message")
    tag_subparsers = tag_parser.add_subparsers(dest='tag_action', help='Tag actions')

    # tag add <tag> <weight>
    add_parser = tag_subparsers.add_parser('add', help='Add or update a tag weight')
    add_parser.add_argument('tag', help='Tag name')
    add_parser.add_argument('weight', type=float, help='Tag weight')

    # tag remove <tag>
    remove_parser = tag_subparsers.add_parser('remove', help='Remove a tag weight')
    remove_parser.add_argument('tag', help='Tag name to remove')

    # tag exclude <tag>
    exclude_parser = tag_subparsers.add_parser('exclude', help='Add a tag to exclusion list')
    exclude_parser.add_argument('tag', help='Tag name to exclude')

    # tag include <tag>
    include_parser = tag_subparsers.add_parser('include', help='Remove a tag from exclusion list')
    include_parser.add_argument('tag', help='Tag name to include')

    return tag_parser


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


# Command registration for main.py
COMMAND = {
    'names': ['tag', 'tags'],
    'setup_parser': setup_parser,
    'handler': handle_tag_command
}
