from obsidian import ObsidianAPI
from ai import FlashcardAI
from anki import AnkiAPI
from config import ConfigManager, MAX_CARDS, NOTES_TO_SAMPLE, DAYS_OLD, SAMPLING_MODE

def main():
    print("🧠 ObsidianKi - Generating flashcards from old notes...")

    # Initialize APIs and config
    config = ConfigManager()
    obsidian = ObsidianAPI()
    ai = FlashcardAI()
    anki = AnkiAPI()

    print(f"⚙️ Sampling mode: {SAMPLING_MODE}")
    if SAMPLING_MODE == "weighted":
        config.show_current_weights()

    # Test connections
    if not obsidian.test_connection():
        print("❌ Cannot connect to Obsidian REST API")
        return

    if not anki.test_connection():
        print("❌ Cannot connect to AnkiConnect")
        return

    print("✅ Connected to Obsidian and Anki")

    # Get old notes
    print(f"📋 Finding {NOTES_TO_SAMPLE} old notes (older than {DAYS_OLD} days)...")
    old_notes = obsidian.get_random_old_notes(days=DAYS_OLD, limit=NOTES_TO_SAMPLE, config_manager=config)

    if not old_notes:
        print("❌ No old notes found")
        return

    print(f"✅ Found {len(old_notes)} notes")
    print(f"🎯 Target: {MAX_CARDS} flashcards maximum")

    total_cards = 0

    # Process each note
    for i, note in enumerate(old_notes, 1):
        if total_cards >= MAX_CARDS:
            print(f"\n🛑 Reached daily limit of {MAX_CARDS} cards, stopping")
            break
        note_path = note['result']['path']
        note_title = note['result']['filename']

        print(f"\n📝 Processing note {i}/{len(old_notes)}: {note_title}")

        # Get note content
        note_content = obsidian.get_note_content(note_path)
        if not note_content:
            print("  ⚠️ Empty or inaccessible note, skipping")
            continue

        # Generate flashcards
        flashcards = ai.generate_flashcards(note_content, note_title)
        if not flashcards:
            print("  ⚠️ No flashcards generated, skipping")
            continue

        print(f"  🧠 Generated {len(flashcards)} flashcards")

        # Hard limit (disabled)
        # cards_to_add = flashcards[:MAX_CARDS - total_cards]
        # if len(cards_to_add) < len(flashcards):
        #     print(f"  📊 Limiting to {len(cards_to_add)} cards to stay within daily limit")

        # Add to Anki
        result = anki.add_flashcards(flashcards)
        successful_cards = len([r for r in result if r is not None])

        if successful_cards > 0:
            print(f"  ✅ Added {successful_cards} cards to Anki")
            total_cards += successful_cards

            # Record flashcard creation for density tracking
            note_size = len(note_content)
            config.record_flashcards_created(note_path, note_size, successful_cards)
        else:
            print("  ❌ Failed to add cards to Anki")

    print(f"\n🎉 Done! Added {total_cards}/{MAX_CARDS} flashcards to your Obsidian deck")


if __name__ == "__main__":
    main()