"""Command registry for ObsidianKi CLI"""

from obsidianki.cli.commands.config_cmd import COMMAND as config_command
from obsidianki.cli.commands.tag_cmd import COMMAND as tag_command
from obsidianki.cli.commands.history_cmd import COMMAND as history_command
from obsidianki.cli.commands.deck_cmd import COMMAND as deck_command
from obsidianki.cli.commands.template_cmd import COMMAND as template_command
from obsidianki.cli.commands.hide_cmd import COMMAND as hide_command
from obsidianki.cli.commands.edit_cmd import COMMAND as edit_command
from obsidianki.cli.commands.vector_cmd import COMMAND as vector_command

ALL_COMMANDS = [
    config_command,
    tag_command,
    history_command,
    deck_command,
    template_command,
    hide_command,
    edit_command,
    vector_command,
]
