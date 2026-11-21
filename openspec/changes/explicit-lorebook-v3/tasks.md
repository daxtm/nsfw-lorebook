Status: implemented; repair pass 2 and hardcore set-piece entries applied 2026-11-17. Automated checks green, export matches source; in-chat verification outstanding. Token and budget counts are estimates.
# Tasks

## 1. Scaffold

Copy from the handoff zip into the repo: `cardtool.py`, `Kink & Explicit Scenes.card.txt`, `research/main_BDSM-Kinks-Fetishes-Sex_world_info.json`, `research/slop_phrase_prob_adjustments.json`, `research/antislop-sampler-LICENSE`. Create `tools/` and `antislop/`.
Confirm: `ls` shows all five files and `python3 cardtool.py lint "Kink & Explicit Scenes.card.txt"` still runs.

## 2. New brief section in the source meta

Add a `meta` note defining the mandated vocabulary, the euphemism ban, and the sample-line requirement, so the source carries its own rules.
Confirm: `python3 cardtool.py book` still builds.

## 3. Rewrite the 50 existing entries

Vocabulary and sample line into every body, keep the technique. Work in batches of ten, build after each batch.
Confirm: `python3 cardtool.py lint` and `python3 tools/check_vocab.py` (task 6) on the finished batch.

## 4. Add the `Explicit vocabulary` entry

Depth 1, order 170, sticky 8, role system. Substitution map, register note, variety note, fallback clause.
Confirm: build, then `python3 tools/test_activation.py --case vocabulary-only`.

## 5. Add the 28 new subject entries

Ageplay and caregiver dynamics; Non-con; Zoophilia; Fantasy species and knotting; Necrophilia; Gore, injury and vore; Watersports; Scat; Blood play; Incest and family dynamics; Cuckolding and hotwifing; Lactation; Medical play; Sounding; Hypnosis and dollification; Sissification; Fisting and stretching; CBT and ball play; Kissing and making out; Massage and sensual vanilla; Food play; Body writing; Branding, piercing and tattoos; Public and semi-public sex; Somnophilia; TPE, protocol and honorifics; Leather and dungeon etiquette.
Confirm: `python3 tools/check_coverage.py` prints zero missing.

## 6. `tools/check_vocab.py`

Per-entry required-word table; non-zero exit with the entry and the missing word. Banned-euphemism scan over the whole source.
Confirm: delete `clit` from `Fingering and handjobs`, run it, see the entry named.

## 7. `tools/check_keys.py`

Compile every key, reject bare everyday words, reject duplicate primaries, verify the secondary string is byte-identical everywhere.
Confirm: run it; expect zero findings on a clean book.

## 8. `tools/check_flags.py`

Reject constant, recursive, off-probability or mis-placed entries against the placement table in the spec.
Confirm: set one entry to probability 70, run it, see it named.

## 9. `tools/check_coverage.py`

Hold the 78-subject list; report missing and duplicate.
Confirm: run it; zero missing, zero duplicate.

## 10. `tools/test_activation.py`

Three sections (positives, 60-line false-positive corpus, recursion replay from the two real character sentences), `--case` and `--entry` filters, budget gate behind `--budget`, PASS/FAIL lines, exit code.
Confirm: run it whole; every section PASS, exit 0.

## 11. Update the three control entries

`Explicit scene direction`, `Explicitness - maximum` and `Reply focus` raised to the enforced standard: length floor, banned euphemisms, one-beat-at-a-time rule kept.
Confirm: `python3 tools/test_activation.py --case explicit-director` fires all three control entries.

## 12. Build the phrase list

Filter the sam-paech list (drop single-token and under-12-character phrases, drop bare erotic vocabulary), add the erotica clichés, dedupe, wrap each in double quotes, cap at 700. Copy the licence into `antislop/`.
Confirm: `python3 tools/check_phrases.py` reports count ≤700 and shortest phrase >12 characters.

## 13. `tools/check_phrases.py`

Count, shortest phrase, duplicates, quoting shape, licence present.
Confirm: quote a phrase wrong, run it, see it named.

## 14. README and AGENTS.md

Install/verify/paste steps, the streaming caveat, the in-chat validation walkthrough, and the real `Run it` / `Checks` commands in the project AGENTS.md placeholders.
Confirm: follow the README on a fresh import.

## 15. Final run

All five checks plus lint and build, then walk every scenario in all four specs by hand. Fix failures before reporting.
Confirm: paste the exact command output; all exit 0.
