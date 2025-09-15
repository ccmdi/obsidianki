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
obsidianki --setup           # Reconfigure
obsidianki --config          # Show config path
```

### Note Selection
```bash
obsidianki --notes "React" "JavaScript"     # Process specific notes
obsidianki --cards 10                       # Generate up to 10 cards total
obsidianki --notes "React" "JavaScript" --cards 6  # Generate ~3 cards per note (6 total)
obsidianki --notes "React" --cards 6        # Generate ~6 cards from React note
```

### Query Mode
```bash
# Standalone query (no source material needed)
obsidianki -q "how to center a div"
obsidianki -q "CSS flexbox" --cards 8

# Targeted extraction
obsidianki --notes "React" -q "error handling"
obsidianki --notes "JavaScript" "TypeScript" -q "async patterns" --cards 6
```

### Approval Settings
During setup, you can enable:
- **Note approval**: Review each note before AI processing
- **Card approval**: Review each flashcard before adding to Anki

## Configuration Files
- `config.json` - Main settings (cards per session, sampling mode, approval settings, etc.)
- `tags.json` - Tag weights and exclusions for weighted sampling
- `processing_history.json` - Tracks flashcards created per note

**Example tags.json for weighted sampling:**
```json
{
  "field/history": 2.0,
  "field/math": 1.0,
  "field/science": 1.5,
  "_default": 0.5,
  "_exclude": ["private", "draft", "personal"]
}
```

**Tag exclusions**: Notes with tags in the `_exclude` array will be completely filtered out during note selection (applied at the database level for efficiency).

## How it works

### Standard Mode
1. Finds old notes in your vault (configurable age threshold)
2. Excludes notes with tags in `_exclude` array (database-level filtering)
3. Weights notes by tags and processing history (avoids over-processed notes)
4. Generates flashcards using Claude 4 Sonnet
5. Creates cards in Anki **"Obsidian"** deck

### Query Modes
- **Standalone**: Generates flashcards from AI knowledge alone based on your query
- **Targeted**: Extracts specific information from selected notes based on your query

### Smart Features
**Intelligent sampling:**
- Higher-weighted tags get selected more often
- Notes with fewer flashcards relative to size are preferred
- Prevents exhausting small notes while allowing large notes more cards

**Card generation:**
- `--cards` parameter instructs the AI on exactly how many cards to generate
- Distributes card count across multiple notes automatically
- Supports approval workflows for both note selection and individual cards

**Card Types:**
- **Basic**: Standard front/back flashcards
- **Custom**: Includes clickable "Origin" field that opens the source note