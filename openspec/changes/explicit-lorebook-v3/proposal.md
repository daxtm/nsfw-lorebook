# Proposal

## Why

The v2 lorebook in the handoff is structurally sound but morally defanged. Across all 5,249 words of entry text it uses `cock` 5 times (mostly inside "cock ring"), `cum` 23, `tits` once, and `cunt`, `pussy`, `balls`, `anus`, `penis` **zero** times; it writes "breasts (or chest)", "mouth or body", "clitoris rather than rubbing it raw". It also narrowed coverage to one pair of characters' limits, dropping ageplay, animals, necrophilia, gore, non-negotiated non-con, watersports/scat/blood, fantasy species and incest. Result: the model is told to be graphic while being handed timid vocabulary, and half the field is missing.

## What Changes

- Rewrite all 50 entry bodies into explicit anatomical vocabulary, keeping each entry's instruction structure and adding one or two sample sentences as a calibration target.
- Add a high-priority **Vocabulary** entry: the word substitution map (cunt, cock, tits, ass, clit, balls, come) and "use the character's own register, never `sex`/`member`/`core`".
- Add ~28 entries covering the banned categories: ageplay, non-con, zoophilia, necrophilia, gore/injury, watersports, scat, blood, fantasy species, incest, plus cuckolding, lactation, medical play, sounding, hypnosis/dollification, sissification, fisting, CBT, kissing, massage, food play, body writing, branding/piercing, masturbation-in-public, somnophilia, TPE, leather/dungeon etiquette, aftercare-of-marks, and a fallback for kinks not covered.
- Raise explicitness in the three writing-control entries from "graphic detail" to an enforced standard with a length floor and a banned-euphemism list.
- Replace the throwaway activation check with a committed tester: one positive sample per entry plus a 60-line false-positive corpus of ordinary prose, run in one command with a pass/fail exit code, and a token-budget gate.
- Ship a curated antislop phrase list (sam-paech general list minus legitimate erotica, plus erotica clichés) as a paste-ready file for KoboldCpp's banned-strings field.
- Build the importable `Kink & Explicit Scenes.json` from the card source; never hand-edit the JSON.

## Capabilities

### New Capabilities

- `entry-content`: what an entry body must contain — explicit vocabulary, instruction-first structure, sample line, length bounds, excluded-content stance.
- `entry-activation`: key discipline — regex shape, secondary sexual-word filter, avert everyday false positives, preserve character-lorebook recursion pulls.
- `book-build`: building and validating the book — source format, lint, tester, token budget gate, install steps.
- `antislop-phrase-list`: the curated phrase list and its paste-ready delivery format.

### Modified Capabilities

None; `openspec/specs/` is empty.

## Impact

New content project. Files: `Kink & Explicit Scenes.card.txt` (source of truth), `Kink & Explicit Scenes.json` (built artifact), `cardtool.py`, `tools/` (tester + vocabulary lint), `research/` (Memreal checklist, antislop licence), `antislop/erotica-phrases.txt`. No app code. No new dependencies — Python stdlib only. Target is the existing SillyTavern 1.19.0 / KoboldCpp install at 16K context.

## Out of scope

Sampler changes (DRY, temperature), character cards and their embedded intimacy books, a slop-forensics benchmark run, any editing of SillyTavern or KoboldCpp source, non-English output, a GUI.

## Assumptions

- "Censored on moral grounds" means the vocabulary and category choices, not entry structure — the v2 structure, key discipline and placement are kept.
- The character books still exist and their phrases must keep pulling entries; recursion is not turned off.
- All banned categories are wanted even where the current characters never use them, because the book is global and reusable.
- No subjects are off topic
- "Best end result" outranks a fixed token cap; entries still stay lean (120–260 tokens) and the whole book is gated at 16k tokens so a busy loaded scene stays under 2.6k.
- Curated antislop list, no measurement pass.
- One final lorebook delivered; v2 is replaced, not kept in parallel.

## Definition of done

`python3 cardtool.py book` and `python3 cardtool.py lint` pass; `python3 tools/test_activation.py` prints PASS/FAIL per case and exits 0; `python3 tools/check_vocab.py` exits 0; the token gate passes; a real in-chat scene loads the expected entries with no budget-overflow warning; **all scenarios pass**.
