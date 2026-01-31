# How it works

The main idea is: you input some *knowledge source*, an LLM of your choice will transform that knowledge into a **question/answer format**, and it is added to your Anki deck of choice.

## Modes
### Standard mode
Standard mode is the default when you run `oki`. The knowledge source is a note(s).

1. Finds notes in your vault (older than `days_old` via `mtime`)
2. Weights notes by tags and processing history (avoids over-processed notes)
3. Generates flashcards using LLM
4. Creates cards in Anki **"Obsidian"** deck (or `DECK` set in config)

### Standalone mode
If you run `oki --query ...`, you use **standalone** mode. The knowledge source is your query. The LLM simply creates flashcards based on the query.

### Targeted mode
If you run `oki --notes <some pattern> --query ...`, you use **targeted** mode. The knowledge source is a note(s), but you extract knowledge FROM that note via the query.

## Comparison
| Mode | Command | Knowledge Source | Primary Purpose |
| --- | --- | --- | --- |
| **Standard** | `oki` | **Note(s)** | Study your note(s) directly. |
| **Standalone** | `oki -q "query"` | **The query** | Disparate knowledge that either isn't in or doesn't belong in your vault. |
| **Targeted** | `oki --notes <pattern> -q "query"` | **Extraction from note(s)** | Study *an extracted aspect* of your note(s). |

