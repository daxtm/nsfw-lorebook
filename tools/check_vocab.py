#!/usr/bin/env python3
"""Vocabulary gate: crude words where the anatomy is in play, no euphemisms."""

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from cardtool import parse_src

SRC = Path(os.environ.get("KINK_SRC", ROOT / "Kink & Explicit Scenes.card.txt"))

BANNED = [
    r"\bmember\b",
    r"\bmanhood\b",
    r"\bdown there\b",
    r"\bintimate parts\b",
    r"\bbundle of nerves\b",
    r"\bher core\b",
    r"\bhis core\b",
    r"\bnether regions\b",
    r"\bprivate parts\b",
]
REQUIRED = {
    "Explicit vocabulary": ["cock", "cunt", "tits", "ass", "clit", "balls", "come"],
    "Anal sex, rimming, pegging": ["ass", "cock", "lube"],
    "Fingering and handjobs": ["cunt", "clit"],
    "Oral sex": ["cock"],
    "Fluids and mess": ["cum"],
    "Body worship and nipple play": ["tits", "nipple"],
    "CBT and ball play": ["balls", "cock"],
    "Foot play": ["cock"],
    "Sissification": ["cock"],
    "Lactation": ["tits", "milk"],
    "Watersports": ["cunt", "tits"],
    "Public and semi-public sex": ["skirt"],
    "Kissing and making out": ["tongue"],
}
CRUDE = re.compile(r"\b(cock|cunt|pussy|clit|cum|come|tits|ass|balls)\b", re.I)
MIN_CRUDE_ENTRIES = 28

failures = []


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        failures.append(name)


def main():
    src = parse_src(SRC.read_text(encoding="utf-8"))
    entries = {e.get("comment", ""): e.get("content", "") for e in src["entries"]}
    for e in src["entries"]:
        pass

    for comment, words in REQUIRED.items():
        if comment not in entries:
            check(f"entry present: {comment}", False)
            continue
        body = entries[comment]
        missing = [w for w in words if not re.search(r"\b" + w + r"\w*", body, re.I)]
        check(
            f"required words: {comment}",
            not missing,
            "missing " + ", ".join(missing) if missing else "",
        )

    for e in src["entries"]:
        c = e.get("comment", "")
        body = e.get("content", "")
        check(f"body present: {c}", bool(body.strip()))
        check(f"has an example: {c}", "[Example:" in body)
        if c in ("Explicit vocabulary", "Explicitness - maximum"):
            continue
        for pat in BANNED:
            m = re.search(pat, e.get("content", ""), re.I)
            check(f"no euphemism: {c}", not m, m.group(0) if m else "")

    crude = sum(1 for c in entries.values() if CRUDE.search(c))
    check(
        f"book-wide crude vocabulary in {MIN_CRUDE_ENTRIES}+ entries",
        crude >= MIN_CRUDE_ENTRIES,
        f"{crude} entries",
    )

    print(f"\n{len(failures)} failure(s)")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
