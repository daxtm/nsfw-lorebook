# Kink & Explicit Scenes — lorebook

A global SillyTavern World Info book that makes sex scenes explicit (up to NC-17 when the director asks), gives accurate mechanics for each kink, and stays quiet during non-sexual scenes. The director decides when a scene turns sexual.

SillyTavern 1.19.0, KoboldCpp, Artemis-31B-v1.2, 16K context. All entries are instructions plus one sample line; the explicit prose itself still comes from the model.

## Install

1. World Info panel → delete any old `Kink & Explicit Scenes`.
2. Import `Kink & Explicit Scenes.json`.
3. Add it to **Active World(s) for all chats**.

Global install matters: in Writer group chats only the speaking card's own book loads, so an unlinked book would never fire.

Status: automated checks pass. In-chat verification below is still outstanding; token counts are estimates.

## Antislop phrases (optional)

`antislop/erotica-phrases.txt` holds 182 banned phrases, one quoted phrase per line. Paste the whole file into SillyTavern's sampler panel, **banned tokens/strings** field. Lines wrapped in double quotes are sent as banned phrases; do not unwrap them, and do not put unquoted lines in that field (those become token bans).

Banned phrases only change generation when one is about to appear, so most replies are untouched. KoboldCpp backtracks and resamples, which holds streaming output back a few tokens. If SillyTavern rejects the paste, paste it in halves to find the offending line.

Licence: sam-paech antislop-sampler, Apache-2.0, see `antislop/antislop-sampler-LICENSE`.

## SillyTavern settings

Sensible starting values, not measured optima. Change one at a time.

- Scan depth **2**; recursive scanning **on**; match whole words **on**; case-sensitive **off**.
- Context **15%** of the 16K window (about 2,400 tokens). If the panel offers a numeric budget cap, use about 2,400-2,600 and leave `ignoreBudget` off.
- Overflow alert **on**; minimum activations **off**; probability stays 100 per entry.
- Sticky: kinks 2, control entries 4. Cooldown 0 until you see actual spam.

Settings bound load and lingering time. They do not fix ambiguous keys: a false match in the current message still activates.

## Hardcore scenes

Say `XXX`, `hardcore` or `NC-17` in a direction. Two entries load: the hardcore set-piece rule (at least four distinct acts per reply, one act or escalation per paragraph, no recap, no cut at orgasm) and the gear entry (suspension, chastity, clamps, machines, latex, TENS). The director's list is a floor within the limits they set.

## Verify in chat

After a sexual reply, open the message's prompt itemization and check:

- the expected entries fired (kinks named in the scene, not neighbours);
- no false triggers in ordinary scenes;
- no console warning about budget overflow.

## Rebuild after an edit

`Kink & Explicit Scenes.card.txt` is the source of truth; never hand-edit the JSON.

```
python3 cardtool.py book "Kink & Explicit Scenes.card.txt" --out "Kink & Explicit Scenes.json"
```

## Checks

`scripts/check.sh` runs everything below and exits non-zero on the first failure to report.

```
scripts/check.sh
python3 cardtool.py lint "Kink & Explicit Scenes.card.txt"
python3 tools/test_activation.py
python3 tools/test_selftest.py
python3 tools/test_build.py
python3 tools/check_vocab.py
python3 tools/check_keys.py
python3 tools/check_flags.py
python3 tools/check_coverage.py
python3 tools/check_phrases.py
```

Lint reports exactly two warnings (empty description and first_mes): this is a lorebook-only source. Everything else must exit 0.

Token counts are estimates from character length and a reference scene, not a guarantee. Confirm real usage in the prompt itemization.
