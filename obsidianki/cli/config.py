from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from obsidianki.cli.models import Note

import json
from pathlib import Path
from typing import Dict, List, Union, Mapping, cast
from dotenv import load_dotenv
from rich.console import Console



console = Console()

CONFIG_DIR = Path.home() / ".config" / "obsidianki"
ENV_FILE = CONFIG_DIR / ".env"
CONFIG_FILE = CONFIG_DIR / "config.json"

load_dotenv(ENV_FILE)

DEFAULT_CONFIG = {
    "MAX_CARDS": 6,
    "NOTES_TO_SAMPLE": 3,
    "DAYS_OLD": 30,
    "SAMPLING_MODE": "weighted",  # "uniform" or "weighted"
    "DENSITY_BIAS_STRENGTH": 0.5,
    "SEARCH_FOLDERS": None,  # or None for all folders
    "CARD_TYPE": "custom",  # "basic" or "custom"
    "APPROVE_NOTES": False,  # Ask user approval before AI processes each note
    "APPROVE_CARDS": False,   # Ask user approval before adding each card to Anki
    "DEDUPLICATE_VIA_HISTORY": False,  # Include past flashcard questions in prompts to avoid duplicates
    "DEDUPLICATE_VIA_DECK": False,  # Include all deck cards in prompts to avoid duplicates (experimental/expensive)
    "USE_DECK_SCHEMA": False,  # Sample existing cards from deck to enforce consistent formatting/style
    "DECK": "Obsidian",  # Default Anki deck for adding cards
    "DIFFICULTY": "normal",  # Flashcard difficulty level: "easy", "normal", or "hard"
    "SYNTAX_HIGHLIGHTING": True,  # Enable syntax highlighting for code blocks in flashcards
    "UPFRONT_BATCHING": False,  # Process all notes in parallel instead of one-by-one
    "BATCH_SIZE_LIMIT": 20,  # Maximum notes to process in batch mode
    "BATCH_CARD_LIMIT": 100  # Maximum total cards in batch mode
}

class Config:
    def __init__(self):
        self._config = self.load()
        self.tag_weights: dict[str, float] = {}
        self.excluded_tags: List[str] = []
        self.processing_history = {}
        self.tag_schema_file = CONFIG_DIR / "tags.json"
        self.processing_history_file = CONFIG_DIR / "processing_history.json"
        self.templates_file = CONFIG_DIR / "templates.json"
        self.load_or_create_tag_schema()
        self.load_processing_history()

    def __getattr__(self, name):
        """Dynamically expose config dict values as attributes (lowercase or uppercase)"""
        upper_name = name.upper()
        if upper_name in self._config:
            return self._config[upper_name]
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

    def __setattr__(self, name, value):
        """Allow setting config values dynamically (lowercase or uppercase)"""
        try:
            _config = object.__getattribute__(self, '_config')
            upper_name = name.upper()
            if upper_name in _config:
                _config[upper_name] = value
                return
        except AttributeError:
            pass
        # Normal attribute assignment
        object.__setattr__(self, name, value)

    def __delattr__(self, name):
        """Allow deleting config values (needed for patch cleanup)"""
        if hasattr(self, '_config'):
            upper_name = name.upper()
            if upper_name in self._config:
                pass
                return
        object.__delattr__(self, name)
    
    def save(self, config_dict):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config_dict, f, indent=2)
    
    def load(self):
        config = DEFAULT_CONFIG.copy()

        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r") as f:
                    local_config = json.load(f)
                    config.update(local_config)
            except Exception as e:
                console.print(f"[yellow]WARNING:[/yellow] Error loading config.json: {e}")
                console.print("[cyan]Using default configuration[/cyan]")

        return config

    def load_or_create_tag_schema(self):
        """Load existing tag schema"""
        if self.tag_schema_file.exists():
            with open(self.tag_schema_file, 'r') as f:
                schema = json.load(f)

            # Handle both old format (flat dict) and new format (with exclude array)
            if isinstance(schema, dict) and "_exclude" in schema:
                # New format with exclude array
                self.excluded_tags = schema.get("_exclude", [])
                # Remove exclude key to get weights
                self.tag_weights = {k: v for k, v in schema.items() if k != "_exclude"}
            else:
                # Old format (backward compatibility)
                self.tag_weights = schema
                self.excluded_tags = []

            # Validate required keys for weighted sampling
            if self.SAMPLING_MODE == "weighted":
                if "_default" not in self.tag_weights:
                    self.tag_weights["_default"] = 1

        else:
            console.print(f"[red]ERROR:[/red] {self.tag_schema_file} not found. For weighted sampling, create it with your tag weights.")
            console.print("[cyan]Example structure:[/cyan]")
            console.print('[green]{\n  "field/history": 2.0,\n  "field/math": 1.0,\n  "_default": 0.5,\n  "_exclude": ["private", "draft"]\n}[/green]')
            self.tag_weights = {"_default": 1.0}
            self.excluded_tags = []

    def save_tag_schema(self):
        """Save current tag weights and excluded tags to file"""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        schema: dict[str, float | list[str]] = cast(dict[str, float | list[str]], self.tag_weights.copy())
        if self.excluded_tags:
            schema["_exclude"] = self.excluded_tags

        with open(self.tag_schema_file, 'w') as f:
            json.dump(schema, f, indent=2)

    def get_tag_weights(self) -> dict[str, float]:
        """Get current tag weights"""
        return self.tag_weights.copy()

    def get_excluded_tags(self) -> List[str]:
        """Get current excluded tags"""
        return self.excluded_tags.copy()

    def is_note_excluded(self, note: Note) -> bool:
        """Check if a note should be excluded based on its tags"""
        if not self.excluded_tags:
            return False

        return any(tag in self.excluded_tags for tag in note.tags)

    def update_tag_weight(self, tag: str, weight: float):
        """Update weight for a specific tag"""
        if tag in self.tag_weights:
            self.tag_weights[tag] = weight
            self.save_tag_schema()
        else:
            console.print(f"[yellow]WARNING:[/yellow] Tag '{tag}' not found in schema")

    def show_weights(self):
        """Display current tag weights"""
        non_default_tags = {k: v for k, v in self.tag_weights.items() if k != "_default"}
        if non_default_tags:
            for tag, weight in sorted(self.tag_weights.items()):
                console.print(f"  [green]{tag}:[/green] {weight}")

    def add_tag_weight(self, tag: str, weight: float) -> bool:
        """Add or update a tag weight"""
        if weight < 0:
            console.print(f"[red]ERROR:[/red] Weight must be positive")
            return False

        self.tag_weights[tag] = weight
        self.save_tag_schema()
        return True

    def remove_tag_weight(self, tag: str) -> bool:
        """Remove a tag weight"""
        if tag in self.tag_weights:
            del self.tag_weights[tag]
            self.save_tag_schema()
            return True
        return False

    def add_excluded_tag(self, tag: str) -> bool:
        """Add tag to exclusion list"""
        if tag not in self.excluded_tags:
            self.excluded_tags.append(tag)
            self.save_tag_schema()
            return True
        return False

    def remove_excluded_tag(self, tag: str) -> bool:
        """Remove tag from exclusion list"""
        if tag in self.excluded_tags:
            self.excluded_tags.remove(tag)
            self.save_tag_schema()
            return True
        return False

    def load_processing_history(self):
        """Load processing history from file"""
        if self.processing_history_file.exists():
            with open(self.processing_history_file, 'r') as f:
                self.processing_history = json.load(f)
        else:
            self.processing_history = {}

    def save_processing_history(self):
        """Save processing history to file"""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(self.processing_history_file, 'w') as f:
            json.dump(self.processing_history, f, indent=2)
    
    def load_templates(self):
        """Load templates from JSON file"""
        if not self.templates_file.exists():
            return {}
        try:
            with open(self.templates_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            console.print(f"[red]ERROR:[/red] Failed to load templates: {e}")
            return {}

    def save_templates(self, templates):
        """Save templates to JSON file"""
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(self.templates_file, 'w') as f:
                json.dump(templates, f, indent=2)
            return True
        except Exception as e:
            console.print(f"[red]ERROR:[/red] Failed to save templates: {e}")
            return False

    def record_flashcards_created(self, note: Note, flashcard_count: int, flashcard_fronts: list = []):
        """Record that we created flashcards for a note"""
        if note.path not in self.processing_history:
            self.processing_history[note.path] = {
                "size": note.size,
                "total_flashcards": 0,
                "sessions": [],
                "flashcard_fronts": [],  # Track all flashcard questions ever created
                "decks": {}  # Track per deck flashcard counts
            }

        # Update totals
        self.processing_history[note.path]["total_flashcards"] += flashcard_count
        self.processing_history[note.path]["size"] = note.size  # Update in case note changed

        if CONFIG.deck:
            if "decks" not in self.processing_history[note.path]:
                self.processing_history[note.path]["decks"] = {}

            if CONFIG.deck not in self.processing_history[note.path]["decks"]:
                self.processing_history[note.path]["decks"][CONFIG.deck] = 0

            self.processing_history[note.path]["decks"][CONFIG.deck] += flashcard_count

        # Add flashcard fronts to history if provided
        if flashcard_fronts:
            if "flashcard_fronts" not in self.processing_history[note.path]:
                self.processing_history[note.path]["flashcard_fronts"] = []
            self.processing_history[note.path]["flashcard_fronts"].extend(flashcard_fronts)

        self.processing_history[note.path]["sessions"].append({
            "date": __import__('time').time(),
            "flashcards": flashcard_count,
            "deck": CONFIG.deck
        })

        self.save_processing_history()

    def get_flashcard_fronts_for_note(self, note: Note) -> list:
        """Get all previously created flashcard fronts for a note"""
        if note.path not in self.processing_history:
            return []

        return self.processing_history[note.path].get("flashcard_fronts", [])

    def get_density_bias_for_note(self, note: Note, bias_strength: float = 0.0) -> float:
        """Calculate density bias for a note (lower = more processed relative to size)"""
        if note.path not in self.processing_history:
            return 1.0  # No bias for unprocessed notes

        history = self.processing_history[note.path]
        total_flashcards = history["total_flashcards"]

        if note.size == 0:
            note.size = 1

        density = total_flashcards / note.size

        # Apply bias - higher density = lower weight
        # bias_strength = 1: guaranteed zero probability for any processed notes
        # bias_strength = 0: no penalty for processed notes
        effective_bias = bias_strength if bias_strength is not None else self.DENSITY_BIAS_STRENGTH
        bias_factor = (1.0 - effective_bias) ** (density * 1000)

        return bias_factor


    def get_sampling_weight_for_note_object(self, note: Note, bias_strength: float = 0.0) -> float:
        """Calculate total sampling weight for a Note object"""
        tag_weight = 1.0
        if self.SAMPLING_MODE == "weighted" and self.tag_weights:
            relevant_tags = [tag for tag in note.tags if tag in self.tag_weights and tag != "_default"]

            if not relevant_tags:
                tag_weight = self.tag_weights.get("_default", 1.0)
            else:
                tag_weight = max(self.tag_weights[tag] for tag in relevant_tags)

        density_bias = note.get_density_bias(bias_strength)
        final_weight = tag_weight * density_bias

        return final_weight

    def is_note_hidden(self, note_path: str) -> bool:
        """Check if a note is hidden"""
        if note_path not in self.processing_history:
            return False
        return self.processing_history[note_path].get("hidden", False)

    def hide_note(self, note_path: str):
        """Mark a note as hidden"""
        if note_path not in self.processing_history:
            self.processing_history[note_path] = {
                "size": 0,
                "total_flashcards": 0,
                "sessions": [],
                "flashcard_fronts": [],
                "decks": {},
                "hidden": True
            }
        else:
            self.processing_history[note_path]["hidden"] = True
        self.save_processing_history()

    def unhide_note(self, note_path: str) -> bool:
        """Unmark a note as hidden"""
        if note_path in self.processing_history:
            self.processing_history[note_path]["hidden"] = False
            self.save_processing_history()
            return True
        return False

    def get_hidden_notes(self) -> List[str]:
        """Get list of all hidden note paths"""
        return [path for path, data in self.processing_history.items()
                if data.get("hidden", False)]


# Global config instance
CONFIG = Config()
