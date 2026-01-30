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
obsidianki                   # Generate flashcards
oki                          # Alias
```

### Configuration
```bash
oki config                         # Show config
oki config get max_cards           # Get specific setting
oki config set max_cards 15        # Update setting
oki config set model "GPT-5"       # Switch AI model
```

### Tags
```bash
oki tag                      # Show tags
oki tag add python 2.0       # Add/update tag weight
oki tag remove python        # Remove tag weight
oki tag exclude boring       # Exclude notes with 'boring' tag
oki tag include boring       # Remove 'boring' from exclusion list
```

### Notes
```bash
# Process specific number of notes
oki --notes 5                         # Sample 5 random notes
oki --notes 10 --cards 20             # Sample 10 notes, max 20 cards total

# Process specific notes by name
oki --notes "React" "JavaScript"       # Process specific notes
oki --notes "React" --cards 6          # Process React note, max 6 cards

# Directory patterns with sampling
oki --notes "frontend/*"               # Process all notes in frontend/
oki --notes "frontend/*:5"             # Sample 5 notes from frontend/
oki --notes "docs/*.md:3"              # Sample 3 markdown files from docs/
oki --notes "react*:2" "vue*:1"        # Sample 2 React + 1 Vue note

# Mixed usage
oki --notes "React Hooks" "components/*:3"  # Specific note + 3 from pattern
```

### Query mode
```bash
# Make flashcard without source note
oki -q "how to center a div"
oki -q "CSS flexbox" --cards 8

# Targeted extraction from source note(s)
oki --notes "React" -q "error handling"
oki --notes "JavaScript" "TypeScript" -q "async patterns" --cards 6
```

### Advanced
```bash
# Deck management
oki --deck "Programming"             # Add cards to specific deck
oki deck                             # List all Anki decks
oki deck rename "Old" "New"          # Rename a deck

# History
oki history stats                    # View generation statistics
oki history clear                    # Clear processing history
oki history clear --notes "React*"   # Clear history for specific notes

# Templating
oki template add "programming" "--notes 'frontend/*' --cards 3' -b 1"
oki template use programming # runs the above command as "oki --notes 'frontend/*' --cards 3' -b 1"
```

## How it works

### Standard mode
1. Finds old notes in your vault (configurable age threshold)
2. Weights notes by tags and processing history (avoids over-processed notes)
3. Generates flashcards using Claude 4 Sonnet
4. Creates cards in Anki **"Obsidian"** deck (or `DECK` set in config)

### Query mode
- **Standalone**: Generates flashcards from AI knowledge alone based on your query
- **Targeted**: Extracts specific information from selected notes based on your query

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

## Vector Deduplication

Avoid generating semantically similar flashcards using API embeddings (Gemini or OpenAI).

### Enable

```bash
oki config set vector_dedup true
```

### Index existing cards

```bash
oki vector index                    # Index cards from default deck
oki vector index --deck "My Deck"   # Index cards from specific deck
```

### Commands

```bash
oki vector status                   # Show index stats
oki vector check "question text"    # Check if similar card exists
oki vector clear                    # Clear the index
```

### How it works

1. AI proposes flashcards via `create_flashcards` tool
2. Each card is checked for semantic similarity against existing cards
3. If similar cards exist, AI receives feedback: *"Card 2 is 87% similar to 'What is polymorphism?'"*
4. AI can revise or confirm via `submit_flashcards` tool
5. Accepted cards are indexed for future deduplication

Embeddings use Gemini (`GEMINI_API_KEY`) or OpenAI (`OPENAI_API_KEY`). The index is stored in `~/.config/obsidianki/vectors.json`.

# MCP
There is an [experimental MCP server](https://github.com/ccmdi/obsidianki-mcp) that runs Obsidianki as a subprocess. Useful if you want to generate flashcards from daily use with an LLM, such as if you ask questions back and forth and want to generate flashcards from that material.