# Spec Delta

## Purpose

A paste-ready list of stock phrases the model should stop producing, delivered without touching any sampler setting.

## ADDED Requirements

### Requirement: Paste-ready format

`antislop/erotica-phrases.txt` SHALL hold one phrase per line, each wrapped in double quotes, nothing else on the line.

#### Scenario: File pasted into SillyTavern
- **WHEN** the file's contents go into the banned-strings field
- **THEN** every line arrives as a banned phrase
- **How to check by hand:** open the file; every line starts and ends with a `"`.

### Requirement: Composition

The list SHALL be the sam-paech general list with legitimate erotic vocabulary removed (no bare `cock`, `cunt`, `clit`, `come`, `cum`), plus hand-picked erotica clichés such as `shivers down her spine`, `her ministrations`, `bundle of nerves`, `gasped as`, `waves of pleasure`, `like a woman possessed`.

#### Scenario: List reviewed
- **WHEN** the list is reviewed for over-reach
- **THEN** no phrase whose absence would starve the prose is on it
- **How to check by hand:** search for `"cum"` and `"cock"` — both absent; search `"shivers down"` — present.

### Requirement: Limits

The list SHALL be at most 700 entries (KoboldCpp caps at 768) and SHALL exclude one-word phrases under 12 characters, because those are treated as token bans and behave differently.

#### Scenario: File checked
- **WHEN** the file is built or changed
- **THEN** the count is at most 700 and the shortest phrase is over 12 characters
- **How to check by hand:** `wc -l antislop/erotica-phrases.txt` and run `python3 tools/check_phrases.py`; it prints count and shortest phrase.

### Requirement: Licence and caveat

`antislop/antislop-sampler-LICENSE` SHALL ship with the list, and the README SHALL state that banning changes output only when a banned phrase is about to appear, and that streaming stalls a few tokens while KoboldCpp backtracks.

#### Scenario: List delivered
- **WHEN** the list ships
- **THEN** the licence file and the caveat paragraph are delivered with it
- **How to check by hand:** the licence file exists and the README holds the caveat.

### Requirement: Bad phrases handled

A phrase holding a double quote SHALL be dropped rather than escaped. The check SHALL be read-only by default and report duplicate phrases by name; `--fix` SHALL remove them and report the count. If a paste is rejected, the README SHALL tell the user to paste in halves to find the offender.

#### Scenario: Duplicate present
- **WHEN** `check_phrases.py` finds a duplicate
- **THEN** it reports the duplicate count and the phrase
- **How to check by hand:** copy one line twice, run the check, see it reported.
