# Vector Deduplication

Obsidianki supports **vector embedding deduplication** - if enabled, proposed flashcards by the LLM will be matched against existing onces within the target deck, and if a card is too similar to an existing one, the agent will be instructed to write a new card.

## Setup
Ensure you have `GEMINI_API_KEY` or `OPENAI_API_KEY` in your `.env` for Obsidianki (`~/.config/obsidianki/.env`). These are the only clients supported at this time.

## Enable

```bash
oki config set vector_dedup true
```

## Index existing cards

```bash
oki vector index                    # Index cards from default deck
oki vector index --deck "My Deck"   # Index cards from specific deck
```

## Commands

```bash
oki vector status                   # Show index stats
oki vector check "question text"    # Check if similar card exists
oki vector clear                    # Clear the index
```

