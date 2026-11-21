# Spec Delta

## Purpose

Every entry body carries the exact vocabulary and the technique the model needs to write explicit scenes, so the book fixes word choice instead of only describing acts.

## ADDED Requirements

### Requirement: Explicit anatomical vocabulary

Every entry naming anatomy, an act or a body part SHALL use the crude term at least once for each relevant part: `cunt`/`pussy`, `cock`, `tits`, `ass`, `clit`, `balls`, `come`/`cum`, `anus`. `member`, `manhood`, `core`, `down there`, `intimate parts` and `bundle of nerves` SHALL NOT appear.

#### Scenario: Entry names genitals
- **WHEN** an entry describes penetration, genitals, breasts, ass or climax
- **THEN** it uses the crude term, not a euphemism
- **How to check by hand:** run `python3 tools/check_vocab.py`; it lists each entry missing a required word and exits non-zero. Search the source for `manhood` — no hits.

### Requirement: The vocabulary entry

One entry, `Explicit vocabulary`, SHALL fire with any sexual scene and SHALL hold the substitution map (`cock`, `cunt`/`pussy`, `tits`, `ass`, `clit`, `balls`, `come`), the note that each character keeps their own register, the variety rule, and the fallback clause for a kink no entry covers.

#### Scenario: Scene with no kink keys
- **WHEN** a sexual scene matches no kink key
- **THEN** `Explicit vocabulary` still loads and dictates word choice
- **How to check by hand:** run `python3 tools/test_activation.py --case vocabulary-only`; it fails if the entry is absent from the match list.

### Requirement: Instruction first, sample second

Each body SHALL open with a bracketed label naming the subject, then the technique as instruction, then one or two sample sentences of the act itself marked as an example.

#### Scenario: Entry read in source
- **WHEN** an entry is opened
- **THEN** label and technique come before any example prose, and the example uses the crude words
- **How to check by hand:** open any entry in the source file — label, technique, example, in that order.

### Requirement: Entry size

A kink entry SHALL be 120–260 tokens, a writing-control entry 150–300, and no entry SHALL exceed 320.

#### Scenario: Entry edited
- **WHEN** an entry is written or changed
- **THEN** its token count stays inside its bound
- **How to check by hand:** run `python3 cardtool.py lint "Kink & Explicit Scenes.card.txt"` (flags over 320) and `python3 tools/test_activation.py` (flags any entry outside its range).

### Requirement: Coverage

The book SHALL contain each of the 80 named subjects exactly once.

#### Scenario: Book built
- **WHEN** `check_coverage.py` runs against the book
- **THEN** no subject is missing and none appears twice
- **How to check by hand:** run `python3 tools/check_coverage.py`; it prints missing and duplicate subjects. The 78 are the 50 v2 subjects, `Explicit vocabulary`, `Ageplay and caregiver dynamics`, `Non-con`, `Zoophilia`, `Fantasy species and knotting`, `Necrophilia`, `Gore, injury and vore`, `Watersports`, `Scat`, `Blood play`, `Incest and family dynamics`, `Cuckolding and hotwifing`, `Lactation`, `Medical play`, `Sounding`, `Hypnosis and dollification`, `Sissification`, `Fisting and stretching`, `CBT and ball play`, `Kissing and making out`, `Massage and sensual vanilla`, `Food play`, `Body writing`, `Branding, piercing and tattoos`, `Public and semi-public sex`, `Somnophilia`, `TPE, protocol and honorifics`, `Leather and dungeon etiquette`, `Hardcore set pieces` and `Gear: suspension, chastity, machines`.

### Requirement: Coverage stance

Entries for a non-human, non-living or childlike-headspace partner SHALL name the concrete difference instead of hedging. Necrophilia SHALL separate fresh from cold, zoophilia SHALL separate animal partner from anthro, and ageplay SHALL state that the body is adult. Actual minors still have no entry.

#### Scenario: One of those entries fires
- **WHEN** a necrophilia, zoophilia or ageplay entry loads
- **THEN** it names a physical or social difference (temperature, knotting, size, headspace, honorifics), not just "like normal sex but—"
- **How to check by hand:** read those entries; each holds at least one concrete difference.

### Requirement: Fallback and separation

An uncovered kink SHALL fall back to the vocabulary entry, never to silence. Watersports and scat SHALL stay separate entries so their keys stay distinct. A sample line SHALL NOT name a character, so the entry works with any card. An empty body SHALL fail lint and a missing `[Example: ...]` line SHALL fail `check_vocab.py`.

#### Scenario: Sample line read
- **WHEN** any entry's sample line is read
- **THEN** it names no character and no card
- **How to check by hand:** read ten sample lines; none uses a proper name.
