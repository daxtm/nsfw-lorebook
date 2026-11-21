# Project: Kink & Explicit Scenes lorebook

A SillyTavern World Info lorebook that makes sex scenes explicit and gives accurate mechanics for each kink, for one user's local RP setup.

## Run it
- Build: `python3 cardtool.py book "Kink & Explicit Scenes.card.txt" --out "Kink & Explicit Scenes.json"`
- Install: World Info → Import the JSON → add to Active World(s) for all chats

## Checks (run these after every change)
- All of them: `scripts/check.sh` (exits 0, prints one line per check)
- Lint: `python3 cardtool.py lint "Kink & Explicit Scenes.card.txt"` (expect exactly 2 warnings)
- Activation: `python3 tools/test_activation.py`
- Checker self-test: `python3 tools/test_selftest.py`
- Build/export match: `python3 tools/test_build.py`
- Vocabulary: `python3 tools/check_vocab.py`
- Keys: `python3 tools/check_keys.py`
- Flags: `python3 tools/check_flags.py`
- Coverage: `python3 tools/check_coverage.py`
- Phrases: `python3 tools/check_phrases.py`

## Conventions
- `Kink & Explicit Scenes.card.txt` is the only file edited by hand; the JSON is generated.
- Entry bodies: label, technique, one sample sentence. Crude vocabulary, no euphemisms.
- Keys are one regex with word forms listed; situational entries take the shared secondary filter from the meta block.
- Entries are 120-260 tokens, never over 320. All `prevent_recursion`.
- Python standard library only.

## Specs
Feature specs live in `openspec/specs/`. Planned changes live in `openspec/changes/`. When implementing a change, follow its tasks.md and tick off each task as you finish it.
