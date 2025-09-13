import json
import os
from typing import Dict, List, Optional
from obsidian import ObsidianAPI

# Basic Configuration
MAX_CARDS = 6  # Daily limit of flashcards to generate
NOTES_TO_SAMPLE = 3  # Number of old notes to sample from
DAYS_OLD = 30  # Notes older than this many days

# Tag Weighting Configuration
SAMPLING_MODE = "weighted"  # "uniform" or "weighted"
TAG_FAMILY_PREFIX = "field/"  # Only weight tags starting with this prefix (e.g., "field/history", "field/math")
TAG_SCHEMA_FILE = "tags.json"  # File to store tag weights

class ConfigManager:
    def __init__(self):
        self.tag_weights = {}
        self.load_or_create_tag_schema()

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

def get_sampling_weight_for_note_tags(note_tags: List[str], config: ConfigManager) -> float:
    """Calculate sampling weight for a note based on its tags"""
    if SAMPLING_MODE == "uniform":
        return 1.0

    if not config.tag_weights:
        return 1.0

    # Find tags that match our configured weights (excluding _default)
    relevant_tags = [tag for tag in note_tags if tag in config.tag_weights and tag != "_default"]

    if not relevant_tags:
        # Use _default weight for notes without relevant tags
        return config.tag_weights.get("_default", 1.0)

    # Use maximum weight among relevant tags
    return max(config.tag_weights[tag] for tag in relevant_tags)


if __name__ == "__main__":
    # Demo the config system
    config = ConfigManager()
    config.show_current_weights()

    print(f"\nSampling mode: {SAMPLING_MODE}")
    print(f"Tag family prefix: {TAG_FAMILY_PREFIX}")

    # Example of updating weights
    if config.tag_weights:
        first_tag = list(config.tag_weights.keys())[0]
        print(f"\nExample: Setting {first_tag} weight to 2.0")
        config.update_tag_weight(first_tag, 2.0)
        config.show_current_weights()