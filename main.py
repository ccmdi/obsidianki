import argparse
from obsidian import ObsidianAPI
from ai import FlashcardAI
from anki import AnkiAPI
from config import ConfigManager, MAX_CARDS, NOTES_TO_SAMPLE, DAYS_OLD, SAMPLING_MODE, CARD_TYPE

def main():
    parser = argparse.ArgumentParser(description="Generate flashcards from Obsidian notes")
    parser.add_argument("--cards", type=int, help="Override MAX_CARDS limit")
    parser.add_argument("--notes", nargs='+', help="Process specific notes by name")
    args = parser.parse_args()

    # Determine max_cards and notes_to_sample based on arguments
    if args.notes:
        # When --notes is provided, scale cards to 2 * number of notes (unless --cards also provided)
        if args.cards is not None:
            max_cards = args.cards
        else:
            max_cards = len(args.notes) * 2  # Will be updated after we find actual notes
    elif args.cards is not None:
        # When --cards is provided, scale notes to 1/2 of cards
        max_cards = args.cards
        notes_to_sample = max(1, max_cards // 2)
    else:
        # Default behavior - use config values
        max_cards = MAX_CARDS
        notes_to_sample = NOTES_TO_SAMPLE

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

    # Get notes to process
    if args.notes:
        print(f"🎯 Looking for specific notes: {', '.join(args.notes)}")
        old_notes = []

        for note_name in args.notes:
            specific_note = obsidian.find_note_by_name(note_name)

            if specific_note:
                old_notes.append(specific_note)
                print(f"✅ Found: {specific_note['result']['filename']}")
            else:
                print(f"❌ Not found: '{note_name}'")

        if not old_notes:
            print("❌ No notes found")
            return

        # Update max_cards based on actually found notes (if --cards wasn't specified)
        if args.cards is None:
            max_cards = len(old_notes) * 2

        print(f"📊 Processing {len(old_notes)} note(s)")
        print(f"🎯 Target: {max_cards} flashcards maximum ({max_cards // len(old_notes)} per note average)")
    else:
        print(f"📋 Finding {notes_to_sample} old notes (older than {DAYS_OLD} days)...")
        old_notes = obsidian.get_random_old_notes(days=DAYS_OLD, limit=notes_to_sample, config_manager=config)

        if not old_notes:
            print("❌ No old notes found")
            return

        print(f"✅ Found {len(old_notes)} notes")
        print(f"🎯 Target: {max_cards} flashcards maximum")

    total_cards = 0

    # Process each note
    for i, note in enumerate(old_notes, 1):
        if total_cards >= max_cards:
            print(f"\n🛑 Reached limit of {max_cards} cards, stopping")
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
        result = anki.add_flashcards(flashcards, card_type=CARD_TYPE,
                                   note_path=note_path, note_title=note_title)
        successful_cards = len([r for r in result if r is not None])

        if successful_cards > 0:
            print(f"  ✅ Added {successful_cards} cards to Anki")
            total_cards += successful_cards

            # Record flashcard creation for density tracking
            note_size = len(note_content)
            config.record_flashcards_created(note_path, note_size, successful_cards)
        else:
            print("  ❌ Failed to add cards to Anki")

    print(f"\n🎉 Done! Added {total_cards}/{max_cards} flashcards to your Obsidian deck")


if __name__ == "__main__":
    main()