import json
import os
from pathlib import Path
from typing import Dict, List, Optional
from dotenv import load_dotenv
from rich.console import Console

console = Console()

CONFIG_DIR = Path.home() / ".config" / "obsidianki"
ENV_FILE = CONFIG_DIR / ".env"
CONFIG_FILE = CONFIG_DIR / "config.json"

# Load environment variables once
load_dotenv(ENV_FILE)

# Default Configuration
DEFAULT_CONFIG = {
    "MAX_CARDS": 6,
    "NOTES_TO_SAMPLE": 3,
    "DAYS_OLD": 30,
    "SAMPLING_MODE": "weighted",  # "uniform" or "weighted"
    "TAG_SCHEMA_FILE": "tags.json",
    "PROCESSING_HISTORY_FILE": "processing_history.json",
    "DENSITY_BIAS_STRENGTH": 0.5,
    "SEARCH_FOLDERS": None,  # or None for all folders
    "CARD_TYPE": "custom",  # "basic" or "custom"
    "APPROVE_NOTES": False,  # Ask user approval before AI processes each note
    "APPROVE_CARDS": False,   # Ask user approval before adding each card to Anki
    "DEDUPLICATE_VIA_HISTORY": False,  # Include past flashcard questions in prompts to avoid duplicates
    "DECK": "Obsidian"  # Default Anki deck for adding cards
}

def load_config():
    """Load configuration from global config.json, using defaults if it doesn't exist"""
    config = DEFAULT_CONFIG.copy()
    config_file = CONFIG_DIR / "config.json"

    if config_file.exists():
        try:
            with open(config_file, "r") as f:
                local_config = json.load(f)
                config.update(local_config)
        except Exception as e:
            console.print(f"[yellow]WARNING:[/yellow] Error loading config.json: {e}")
            console.print("[cyan]Using default configuration[/cyan]")

    return config

# Load configuration
_config = load_config()

MAX_CARDS = _config["MAX_CARDS"]
NOTES_TO_SAMPLE = _config["NOTES_TO_SAMPLE"]
DAYS_OLD = _config["DAYS_OLD"]
SAMPLING_MODE = _config["SAMPLING_MODE"]
TAG_SCHEMA_FILE = _config["TAG_SCHEMA_FILE"]
PROCESSING_HISTORY_FILE = _config["PROCESSING_HISTORY_FILE"]
DENSITY_BIAS_STRENGTH = _config["DENSITY_BIAS_STRENGTH"]
SEARCH_FOLDERS = _config["SEARCH_FOLDERS"]
CARD_TYPE = _config["CARD_TYPE"]
APPROVE_NOTES = _config["APPROVE_NOTES"]
APPROVE_CARDS = _config["APPROVE_CARDS"]
DEDUPLICATE_VIA_HISTORY = _config["DEDUPLICATE_VIA_HISTORY"]
DECK = _config["DECK"]

class ConfigManager:
    def __init__(self):
        self.tag_weights = {}
        self.excluded_tags = []
        self.processing_history = {}
        self.tag_schema_file = CONFIG_DIR / "tags.json"
        self.processing_history_file = CONFIG_DIR / "processing_history.json"
        self.load_or_create_tag_schema()
        self.load_processing_history()

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
            if SAMPLING_MODE == "weighted":
                if "_default" not in self.tag_weights:
                    console.print("[yellow]WARNING:[/yellow] '_default' weight not found in tags.json")
                    self.tag_weights["_default"] = 0.1

        else:
            console.print(f"[red]ERROR:[/red] {self.tag_schema_file} not found. For weighted sampling, create it with your tag weights.")
            console.print("[cyan]Example structure:[/cyan]")
            console.print('[green]{\n  "field/history": 2.0,\n  "field/math": 1.0,\n  "_default": 0.5,\n  "_exclude": ["private", "draft"]\n}[/green]')
            self.tag_weights = {"_default": 1.0}
            self.excluded_tags = []

    def save_tag_schema(self):
        """Save current tag weights and excluded tags to file"""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)

        # Combine weights and exclude array into single schema
        schema = self.tag_weights.copy()
        if self.excluded_tags:
            schema["_exclude"] = self.excluded_tags

        with open(self.tag_schema_file, 'w') as f:
            json.dump(schema, f, indent=2)
        console.print(f"[green]SUCCESS:[/green] Saved tag schema to {self.tag_schema_file}")

    def get_tag_weights(self) -> Dict[str, float]:
        """Get current tag weights"""
        return self.tag_weights.copy()

    def get_excluded_tags(self) -> List[str]:
        """Get current excluded tags"""
        return self.excluded_tags.copy()

    def is_note_excluded(self, note_tags: List[str]) -> bool:
        """Check if a note should be excluded based on its tags"""
        if not self.excluded_tags:
            return False

        # Check if any of the note's tags are in the exclude list
        return any(tag in self.excluded_tags for tag in note_tags)

    def update_tag_weight(self, tag: str, weight: float):
        """Update weight for a specific tag"""
        if tag in self.tag_weights:
            self.tag_weights[tag] = weight
            self.save_tag_schema()
            console.print(f"[green]SUCCESS:[/green] Updated {tag} weight to {weight}")
        else:
            console.print(f"[yellow]WARNING:[/yellow] Tag '{tag}' not found in schema")

    def show_current_weights(self):
        """Display current tag weights"""
        # Only show if there are tags besides _default
        non_default_tags = {k: v for k, v in self.tag_weights.items() if k != "_default"}

        if not non_default_tags:
            return

        console.print("\n[bold cyan]Tag weights:[/bold cyan]")
        for tag, weight in sorted(self.tag_weights.items()):
            console.print(f"  [green]{tag}:[/green] {weight}")

    def normalize_weights(self):
        """Normalize all weights so they sum to 1.0"""
        if not self.tag_weights:
            return

        total = sum(self.tag_weights.values())
        if total > 0:
            for tag in self.tag_weights:
                self.tag_weights[tag] /= total
            self.save_tag_schema()
            console.print("[green]SUCCESS:[/green] Normalized tag weights")

    def reset_to_uniform(self):
        """Reset all weights to uniform distribution"""
        if self.tag_weights:
            uniform_weight = 1.0 / len(self.tag_weights)
            for tag in self.tag_weights:
                self.tag_weights[tag] = uniform_weight
            self.save_tag_schema()
            console.print("[green]SUCCESS:[/green] Reset to uniform weights")

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

    def record_flashcards_created(self, note_path: str, note_size: int, flashcard_count: int, flashcard_fronts: list = None):
        """Record that we created flashcards for a note"""
        if note_path not in self.processing_history:
            self.processing_history[note_path] = {
                "size": note_size,
                "total_flashcards": 0,
                "sessions": [],
                "flashcard_fronts": []  # Track all flashcard questions ever created
            }

        # Update totals
        self.processing_history[note_path]["total_flashcards"] += flashcard_count
        self.processing_history[note_path]["size"] = note_size  # Update in case note changed

        # Add flashcard fronts to history if provided
        if flashcard_fronts:
            if "flashcard_fronts" not in self.processing_history[note_path]:
                self.processing_history[note_path]["flashcard_fronts"] = []
            self.processing_history[note_path]["flashcard_fronts"].extend(flashcard_fronts)

        self.processing_history[note_path]["sessions"].append({
            "date": __import__('time').time(),
            "flashcards": flashcard_count
        })

        self.save_processing_history()

    def get_flashcard_fronts_for_note(self, note_path: str) -> list:
        """Get all previously created flashcard fronts for a note"""
        if note_path not in self.processing_history:
            return []

        return self.processing_history[note_path].get("flashcard_fronts", [])

    def get_density_bias_for_note(self, note_path: str, note_size: int, bias_strength: float = None) -> float:
        """Calculate density bias for a note (lower = more processed relative to size)"""
        if note_path not in self.processing_history:
            return 1.0  # No bias for unprocessed notes

        history = self.processing_history[note_path]
        total_flashcards = history["total_flashcards"]

        if note_size == 0:
            note_size = 1  # Prevent division by zero

        # Calculate flashcard density (flashcards per character)
        density = total_flashcards / note_size

        # Apply bias - higher density = lower weight
        # Bias strength controls how aggressively we avoid over-processed notes
        effective_bias = bias_strength if bias_strength is not None else DENSITY_BIAS_STRENGTH
        bias_factor = max(0.1, 1.0 - (density * 1000 * effective_bias))

        return bias_factor

def get_sampling_weight_for_note(note_tags: List[str], note_path: str, note_size: int, config: ConfigManager, bias_strength: float = None) -> float:
    """Calculate total sampling weight for a note based on tags and processing history"""

    # Base weight from tags
    tag_weight = 1.0
    if SAMPLING_MODE == "weighted" and config.tag_weights:
        # Find tags that match our configured weights (excluding _default)
        relevant_tags = [tag for tag in note_tags if tag in config.tag_weights and tag != "_default"]

        if not relevant_tags:
            # Use _default weight for notes without relevant tags
            tag_weight = config.tag_weights.get("_default", 1.0)
        else:
            # Use maximum weight among relevant tags
            tag_weight = max(config.tag_weights[tag] for tag in relevant_tags)

    # Density bias (lower for over-processed notes)
    density_bias = config.get_density_bias_for_note(note_path, note_size, bias_strength)

    # Combine weights
    final_weight = tag_weight * density_bias

    return final_weight


