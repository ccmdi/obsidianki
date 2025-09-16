# ObsidianKi

Automated flashcard generation to Anki from your Obsidian vault.

![Preview](images/preview.webp)

## Installation

```bash
# uv
uv tool install https://github.com/ccmdi/obsidianki.git

# pip
pip install https://github.com/ccmdi/obsidianki.git
```

## Setup

Run:
```bash
obsidianki
```

This will start the interactive setup. Here's what you'll need:

1. **Obsidian Local REST API plugin setup:**
   - Install [plugin](https://github.com/coddingtonbear/obsidian-local-rest-api) in Obsidian
   - Copy the API key from plugin settings

2. **Anthropic API key:**
   - Get from [console.anthropic.com](https://console.anthropic.com/)

3. **AnkiConnect setup:**
   - Add-on code: `2055492159`
   - Keep Anki running

You can then follow the interactive setup and edit the configuration as you like.

## Usage

### Basic Usage
```bash
obsidianki                   # Generate flashcards
oki                          # Alias
```

### Configuration Management
```bash
oki config                   # Show config commands
oki config list              # List all settings
oki config get max_cards     # Get specific setting
oki config set max_cards 15  # Update setting
```

### Tag Management
```bash
oki tag                      # Show tag commands
oki tag list                 # List tag weights and exclusions
oki tag add python 2.0       # Add/update tag weight
oki tag remove python        # Remove tag weight
oki tag exclude boring       # Exclude notes with 'boring' tag
oki tag include boring       # Remove 'boring' from exclusion list
```

### Note Selection
```bash
oki --notes "React" "JavaScript"     # Process specific notes
oki --cards 10                       # Generate up to 10 cards total
oki --notes "React" "JavaScript" --cards 6  # Generate ~3 cards per note (6 total)
oki --notes "React" --cards 6        # Generate ~6 cards from React note

# Directory patterns
oki --notes "path/to/files/*"      # Process all notes in directory
oki --notes "path/*" --sample 5          # Sample 5 random notes from directory
oki --notes "path/*" --sample 10 --bias 1 # Sample with maximum bias against over-processed notes
```

### Query Mode
```bash
# Make flashcard without source note
oki -q "how to center a div"
oki -q "CSS flexbox" --cards 8

# Targeted extraction from source note(s)
oki --notes "React" -q "error handling"
oki --notes "JavaScript" "TypeScript" -q "async patterns" --cards 6
```

### Deck Management
```bash
oki --deck "Programming"             # Add cards to specific deck
oki -q "Python basics" --deck "CS"  # Query mode with custom deck
oki config set deck "MyDeck"         # Change default deck
```

## How it works

### Standard Mode
1. Finds old notes in your vault (configurable age threshold)
2. Weights notes by tags and processing history (avoids over-processed notes)
3. Generates flashcards using Claude 4 Sonnet
4. Creates cards in Anki **"Obsidian"** deck (or `DECK` set in config)

### Query Modes
- **Standalone**: Generates flashcards from AI knowledge alone based on your query
- **Targeted**: Extracts specific information from selected notes based on your query

### Other features
**Custom flashcard type**: Includes clickable "Origin" field that opens the source note

**Deduplication**: History-based and deck-based options to avoid the same repeated content

**Statistics**: View generation history and top notes