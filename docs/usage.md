# CLI Reference

## Basic Usage

```bash
obsidianki                   # Generate flashcards
oki                          # Alias
```

## Note Selection

```bash
# Default: samples random old notes based on config
oki

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

## Query Mode

```bash
# Standalone: make flashcard without source note
oki -q "how to center a div"
oki -q "CSS flexbox" --cards 8

# Targeted: extract specific info from notes
oki --notes "React" -q "error handling"
oki --notes "JavaScript" "TypeScript" -q "async patterns" --cards 6
```

## Generation Options

```bash
oki --cards 10                        # Max cards to generate
oki --deck "Programming"              # Target specific deck
oki --difficulty hard                 # easy/normal/hard - affects card complexity
oki --extrapolate                     # Allow LLM to use outside knowledge
oki --use-schema                      # Match existing deck's card formatting
oki --bias 0                          # Disable density bias (0-1)
oki --allow "archive/"                # Temporarily expand search folders
```

## Subcommands

### config

```bash
oki config                         # Show all config
oki config get max_cards           # Get specific setting
oki config set max_cards 15        # Update setting
oki config set model "GPT-5"       # Switch AI model
```

### tag

Manage tag weights for weighted sampling:

```bash
oki tag                      # Show tags
oki tag add python 2.0       # Add/update tag weight
oki tag remove python        # Remove tag weight
oki tag exclude boring       # Exclude notes with 'boring' tag
oki tag include boring       # Remove 'boring' from exclusion list
```

### deck

```bash
oki deck                             # List all Anki decks
oki deck rename "Old" "New"          # Rename a deck
```

### history

```bash
oki history stats                    # View generation statistics
oki history clear                    # Clear processing history
oki history clear --notes "React*"   # Clear history for specific notes
```

### template

Save and reuse command presets:

```bash
oki template add "prog" "--notes 'frontend/*' --cards 3 -b 1"
oki template use prog                # Runs the saved command
oki template remove prog
oki template                         # List templates
```

### hide

Hide notes from future processing:

```bash
oki hide "Private Note"              # Hide a note
oki hide --list                      # Show hidden notes
oki hide --unhide "Private Note"     # Unhide a note
```

### edit

Interactively edit existing Anki cards with LLM assistance:

```bash
oki edit "My Deck"                   # Edit cards in deck
```

### vector

Manage the vector index for semantic deduplication:

```bash
oki vector index                     # Index cards from default deck
oki vector index --deck "My Deck"    # Index cards from specific deck
oki vector status                    # Show index stats
oki vector check "question text"     # Check if similar card exists
oki vector clear                     # Clear the index
```

## Flags Reference

| Flag | Short | Description |
|------|-------|-------------|
| `--notes` | `-n` | Note selection (count, names, or patterns) |
| `--cards` | `-c` | Maximum cards to generate |
| `--query` | `-q` | Query mode (standalone or targeted) |
| `--deck` | `-d` | Target Anki deck |
| `--difficulty` | `-D` | Card difficulty (easy/normal/hard) |
| `--extrapolate` | `-x` | Allow LLM to use outside knowledge |
| `--use-schema` | `-u` | Match existing deck formatting |
| `--bias` | `-b` | Density bias strength (0-1) |
| `--allow` | `-w` | Expand search folders |
| `--setup` | `-S` | Run interactive setup |
