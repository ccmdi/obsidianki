"""Edit mode command handler"""

from obsidianki.cli.interactive.edit_mode import edit_mode


def setup_parser(subparsers):
    """Setup argparse parser for edit command"""
    edit_parser = subparsers.add_parser('edit', help='Edit existing cards', add_help=False)
    edit_parser.add_argument("-h", "--help", action="store_true", help="Show help message")
    edit_parser.add_argument('deck', type=str, help="Anki deck to edit cards from", nargs='?', default=None)

    return edit_parser


def handle_edit_command(args):
    """Handle edit command"""
    return edit_mode(args)


# Command registration for main.py
COMMAND = {
    'names': ['edit'],
    'setup_parser': setup_parser,
    'handler': handle_edit_command
}
