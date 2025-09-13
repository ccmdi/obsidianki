import json
import os
from typing import Dict, List, Optional
from obsidian import ObsidianAPI

import json
import os

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
    "CARD_TYPE": "custom"  # "basic" or "custom"
}

def load_config():
    """Load configuration from config.json, creating it from defaults if it doesn't exist"""
    config = DEFAULT_CONFIG.copy()

    if os.path.exists("config.json"):
        try:
            with open("config.json", "r") as f:
                local_config = json.load(f)
                config.update(local_config)
                print(f"📁 Loaded configuration from config.json")
        except Exception as e:
            print(f"⚠️ Error loading config.json: {e}")
            print("Using default configuration")
    else:
        # Create config.json from defaults
        try:
            with open("config.json", "w") as f:
                json.dump(DEFAULT_CONFIG, f, indent=2)
            print(f"🆕 Created config.json with default settings - customize as needed!")
        except Exception as e:
            print(f"⚠️ Could not create config.json: {e}")

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

class ConfigManager:
    def __init__(self):
        self.tag_weights = {}
        self.processing_history = {}
        self.load_or_create_tag_schema()
        self.load_processing_history()

    def load_or_create_tag_schema(self):
        """Load existing tag schema"""
        if os.path.exists(TAG_SCHEMA_FILE):
            print(f"📁 Loading tag schema from {TAG_SCHEMA_FILE}")
            with open(TAG_SCHEMA_FILE, 'r') as f:
                self.tag_weights = json.load(f)

            # Validate required keys for weighted sampling
            if SAMPLING_MODE == "weighted":
                if "_default" not in self.tag_weights:
                    print("⚠️ Warning: '_default' weight not found in tags.json")
                    self.tag_weights["_default"] = 0.1

        else:
            print(f"❌ {TAG_SCHEMA_FILE} not found. For weighted sampling, create it with your tag weights.")
            print("Example structure:")
            print('{\n  "field/history": 2.0,\n  "field/math": 1.0,\n  "_default": 0.5\n}')
            self.tag_weights = {"_default": 1.0}

    def save_tag_schema(self):
        """Save current tag weights to file"""
        with open(TAG_SCHEMA_FILE, 'w') as f:
            json.dump(self.tag_weights, f, indent=2)
        print(f"💾 Saved tag schema to {TAG_SCHEMA_FILE}")

    def get_tag_weights(self) -> Dict[str, float]:
        """Get current tag weights"""
        return self.tag_weights.copy()

    def update_tag_weight(self, tag: str, weight: float):
        """Update weight for a specific tag"""
        if tag in self.tag_weights:
            self.tag_weights[tag] = weight
            self.save_tag_schema()
            print(f"📊 Updated {tag} weight to {weight}")
        else:
            print(f"⚠️ Tag '{tag}' not found in schema")

    def show_current_weights(self):
        """Display current tag weights"""
        print("\n📊 Current Tag Weights:")
        if not self.tag_weights:
            print("  No tags configured")
            return

        for tag, weight in sorted(self.tag_weights.items()):
            print(f"  {tag}: {weight}")

    def normalize_weights(self):
        """Normalize all weights so they sum to 1.0"""
        if not self.tag_weights:
            return

        total = sum(self.tag_weights.values())
        if total > 0:
            for tag in self.tag_weights:
                self.tag_weights[tag] /= total
            self.save_tag_schema()
            print("📐 Normalized tag weights")

    def reset_to_uniform(self):
        """Reset all weights to uniform distribution"""
        if self.tag_weights:
            uniform_weight = 1.0 / len(self.tag_weights)
            for tag in self.tag_weights:
                self.tag_weights[tag] = uniform_weight
            self.save_tag_schema()
            print("🔄 Reset to uniform weights")

    def load_processing_history(self):
        """Load processing history from file"""
        if os.path.exists(PROCESSING_HISTORY_FILE):
            with open(PROCESSING_HISTORY_FILE, 'r') as f:
                self.processing_history = json.load(f)
            print(f"📊 Loaded processing history for {len(self.processing_history)} notes")
        else:
            self.processing_history = {}

    def save_processing_history(self):
        """Save processing history to file"""
        with open(PROCESSING_HISTORY_FILE, 'w') as f:
            json.dump(self.processing_history, f, indent=2)

    def record_flashcards_created(self, note_path: str, note_size: int, flashcard_count: int):
        """Record that we created flashcards for a note"""
        if note_path not in self.processing_history:
            self.processing_history[note_path] = {
                "size": note_size,
                "total_flashcards": 0,
                "sessions": []
            }

        # Update totals
        self.processing_history[note_path]["total_flashcards"] += flashcard_count
        self.processing_history[note_path]["size"] = note_size  # Update in case note changed
        self.processing_history[note_path]["sessions"].append({
            "date": __import__('time').time(),
            "flashcards": flashcard_count
        })

        self.save_processing_history()

    def get_density_bias_for_note(self, note_path: str, note_size: int) -> float:
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
        bias_factor = max(0.1, 1.0 - (density * 1000 * DENSITY_BIAS_STRENGTH))

        return bias_factor

def get_sampling_weight_for_note(note_tags: List[str], note_path: str, note_size: int, config: ConfigManager) -> float:
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
    density_bias = config.get_density_bias_for_note(note_path, note_size)

    # Combine weights
    final_weight = tag_weight * density_bias

    return final_weight


if __name__ == "__main__":
    # Demo the config system
    config = ConfigManager()
    config.show_current_weights()

    print(f"\nSampling mode: {SAMPLING_MODE}")

    # Example of updating weights
    if config.tag_weights:
        first_tag = list(config.tag_weights.keys())[0]
        print(f"\nExample: Setting {first_tag} weight to 2.0")
        config.update_tag_weight(first_tag, 2.0)
        config.show_current_weights()