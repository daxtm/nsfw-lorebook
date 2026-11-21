# Spec Delta

## Purpose

Entries load when the prose is actually about them, never during dishwashing, and the character intimacy books still pull the right entries through recursion.

## ADDED Requirements

### Requirement: Key shape

Every primary key SHALL be one regex of the form `/\b(...)\b/i` listing each word form (`spank(s|ed|ing)?`). Bare everyday words SHALL NOT be primary keys: `throat`, `plug`, `crop`, `switch`, `collar`, `kiss`, `massage`, `food`, `camera` SHALL be phrase-qualified, e.g. `gag (him|her|them)`, `collar(s|ing)? (him|her|them)`, `kiss(s|ed|ing)? (her|him|them) (deep|hard|slow)`.

#### Scenario: Keys written
- **WHEN** a key is authored or edited
- **THEN** it compiles as a single regex and every word form is listed
- **How to check by hand:** run `python3 tools/check_keys.py`; it compiles each key and names any key that is a bare everyday word.

### Requirement: Secondary filter

Any entry outright keyed on a place, a body part or an everyday verb SHALL carry the shared secondary key with ANY logic, so it fires only when sex vocabulary is present too. The shared string SHALL be defined once in the source meta and SHALL be byte-identical across entries. An ambiguous term can instead be phrase-qualified at the alternative level.

#### Scenario: Sexless pond scene
- **WHEN** a pond scene without sex is scanned
- **THEN** `Sex in water and showers` does not load
- **How to check by hand:** the `non-sexual-pond` case in the tester must report zero matches.

### Requirement: False-positive corpus

`tools/test_activation.py` SHALL hold at least 60 ordinary sentences, each verified to fire nothing, including `cleared his throat`, `running gag`, `flipped the switch`, `tugged his collar`, `spark plug`, `crop top`, `showed restraint`, `choked back tears`, `graphic tee`, `ticklish about it`. Adding a case SHALL be a one-line edit.

Every discovered false trigger SHALL stay in the corpus; an easier sentence may not replace a failing one.

#### Scenario: Corpus runs
- **WHEN** the tester runs its corpus section
- **THEN** every sentence reports zero matches, or the run fails and names the entry that fired
- **How to check by hand:** run `python3 tools/test_activation.py`; the run exits 0 only if every corpus line reports 0.

### Requirement: Every entry fires

The tester SHALL hold one positive sample per entry with a frozen expected activation set. An unexpected extra or missing entry fails. `--freeze` regenerates the sets for review. Genuine simultaneous activations stay expected; accidental collisions are fixed in the keys, not accepted.

#### Scenario: Positive sample scanned
- **WHEN** a positive sample runs
- **THEN** the match list equals the expected set
- **How to check by hand:** run `python3 tools/test_activation.py --entry "Oral sex"`; it fails if `Oral sex` is absent.

### Requirement: Recursion pulls preserved

The character intimacy books SHALL keep pulling entries. `pansexual switch`, `consensual non-consent`, `BDSM`, `bondage`, `orgasm control`, `praise and degradation`, `degradation` and `dominant` SHALL match.

#### Scenario: Character entry scanned
- **WHEN** a real character intimacy sentence is scanned
- **THEN** the expected kink entries load in the same step
- **How to check by hand:** run `python3 tools/test_activation.py --case recursion`; it replays both real sentences and prints the pulled entries.

### Requirement: Fixed flags and placement

Every entry SHALL be enabled, `prevent_recursion: true`, probability 100, not constant. Kink entries sit `after_char`, order 110 (situational 100–105), sticky 5. Control entries sit at depth with role `system`: `Explicit scene direction` depth 2 order 150; `Explicit vocabulary` depth 1 order 170; `Explicitness - maximum` depth 1 order 160; `Hardcore set pieces` depth 1 order 165; `Reply focus` depth 1 order 140; all sticky 8.

#### Scenario: Book built
- **WHEN** the book is built
- **THEN** no entry deviates from these flags or positions
- **How to check by hand:** `python3 tools/check_flags.py` prints any entry that is constant, recursive or off-probability.

### Requirement: Key faults fail loudly

Two entries sharing a primary key SHALL fail the key check. An unbalanced bracket SHALL fail with the entry name, not a traceback. `{{random::...}}` in `Reply focus` re-rolls every generation, so the tester SHALL normalise it before comparing. A key inside an entry's own text cannot cascade, because recursion is off per entry.

#### Scenario: Key check self-test
- **WHEN** a `)` is deleted from a key
- **THEN** `check_keys.py` names the entry and exits non-zero
- **How to check by hand:** break a key on purpose, run the check, see the entry named.
