# ObsidianKi

Automated flashcard generation to Anki from your Obsidian vault.

![Preview](images/preview.webp)

## Installation

```bash
# uv
uv tool install obsidianki
# uv (source)
uv tool install https://github.com/ccmdi/obsidianki.git

# pip
pip install obsidianki
# pip (source)
pip install https://github.com/ccmdi/obsidianki.git
```

## Why?
Obsidian is a knowledge store. You write notes without the explicit intention of reviewing them later. The knowledge in Obsidian is **unstructured** (natural language), and forcing flashcard review into Obsidian via manual question/answer pairs is making it something it fundamentally isn't.

Anki, on the other hand, is an application exactly for purposeful review. Anki is inherently **structured** via "question/answer" flashcard format. 

To get the best of both worlds, knowledge management in Obsidian and review scheduling in Anki, we need to translate the unstructured notes to structured flashcards. **Bridging this gap is the main goal of ObsidianKi**.

## Setup

Run:
```bash
obsidianki
```

This will start the interactive setup. Here's what you'll need:

1. **Obsidian Local REST API plugin setup:**
   - Install [plugin](https://github.com/coddingtonbear/obsidian-local-rest-api) in Obsidian
   - Copy the API key from plugin settings

2. **AnkiConnect setup:**
   - Add-on code: `2055492159`
   - Keep Anki running

The interactive setup will guide you through model selection and configuration.

## Usage

```bash
oki                                # Generate from random old notes
oki --notes "React"                # Generate from specific note
oki --notes "frontend/*:3"         # Sample 3 notes from folder
oki -q "What is X?"                # Standalone query (no source note)
oki --notes "React" -q "hooks"     # Targeted extraction from note
```

See the [reference](docs/usage.md) for all commands and options.

## Index
* [Reference](docs/usage.md) - all commands and options
* [How it works](docs/how-it-works.md)
* [Vector deduplication](docs/vectors.md) - best deduplication method
* [MCP server](docs/mcp.md) - for conversational use

## Configuration options

| Setting | Default | Description |
|---------|---------|-------------|
| `max_cards` | `6` | Maximum cards per session |
| `notes_to_sample` | `3` | Number of notes to process in default mode |
| `days_old` | `30` | Only process notes older than N days |
| `sampling_mode` | `"weighted"` | `"weighted"` or `"uniform"` note selection |
| `card_type` | `"custom"` | `"basic"` or `"custom"` Anki card type |
| `deck` | `"Obsidian"` | Default Anki deck name |
| `approve_notes` | `false` | Review each note before processing |
| `approve_cards` | `false` | Review each card before adding to Anki |
| `deduplicate_via_history` | `false` | Avoid duplicates using processing history |
| `deduplicate_via_deck` | `false` | Avoid duplicates by checking existing deck cards |
| `use_deck_schema` | `false` | Match existing card formatting in deck |
| `syntax_highlighting` | `true` | Enable code syntax highlighting |
| `upfront_batching` | `false` | Process notes in parallel (faster) |
| `batch_size_limit` | `20` | Max notes per batch |
| `batch_card_limit` | `100` | Max cards per batch |
| `density_bias_strength` | `0.5` | Bias strength against over-processed notes (0-1) |
| `search_folders` | `[]` | Limit processing to specific folders (array) |
| `vector_dedup` | `false` | Enable semantic deduplication via embeddings |
| `vector_threshold` | `0.7` | Similarity threshold for duplicate detection (0-1) |