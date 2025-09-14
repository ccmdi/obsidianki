# ObsidianKi

Automated flashcard generation to Anki from your Obsidian vault.

![Preview](images/preview.webm)

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

**Generate flashcards:**
```bash
obsidianki
```

**Options:**
```bash
obsidianki --config          # Show config directory
obsidianki --setup           # Reconfigure

obsidianki --cards 10        # Override card limit
obsidianki --notes "Note 1" "Note 2"  # Process specific notes
```

## Configuration Files
- `config.json` - Main settings (cards per session, sampling mode, etc.)
- `tags.json` - Tag weights for weighted sampling
- `processing_history.json` - Tracks flashcards created per note

**Example tags.json for weighted sampling:**
```json
{
  "field/history": 2.0,
  "field/math": 1.0,
  "field/science": 1.5,
  "_default": 0.5
}
```

## How it works

1. Finds old notes in your vault (configurable age threshold)
2. Weights notes by tags and processing history (avoids over-processed notes)
3. Generates flashcards using Claude 4 Sonnet
4. Creates cards in Anki **"Obsidian"** deck

**Smart sampling:**
- Higher-weighted tags get selected more often
- Notes with fewer flashcards relative to size are preferred
- Prevents exhausting small notes while allowing large notes more cards

**Card Types:**
- **Basic**: Standard front/back flashcards
- **Custom**: Includes clickable "Origin" field that opens the source note