#!/usr/bin/env python3
"""Key discipline gate: compiles keys, catches ambiguous bare alternatives,
duplicates and a drifted secondary filter."""

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from cardtool import parse_src, split_keys

SRC = Path(os.environ.get("KINK_SRC", ROOT / "Kink & Explicit Scenes.card.txt"))
AMBIGUOUS = {
    "throat",
    "plug",
    "crop",
    "switch",
    "collar",
    "kiss",
    "massage",
    "food",
    "camera",
    "balls",
    "master",
    "slave",
    "ass",
    "come",
    "restrain",
    "restraint",
    "ice",
    "traffic",
    "strawberry",
    "berries",
    "oral",
    "wand",
    "vibe",
    "protocol",
    "clinical",
    "marker",
    "sounding",
    "trance",
    "cupping",
    "topping",
    "tattoo",
    "share",
    "shared",
    "bleed",
    "blood",
    "wound",
    "injury",
    "sensitive",
    "position",
    "positions",
    "paws",
    "lipstick",
}
SITUATIONAL = {
    "Positions",
    "Teasing and foreplay",
    "Body worship and nipple play",
    "Breeding and creampies",
    "Size difference",
    "Fluids and mess",
    "Sexual roleplay scenarios",
    "Primal play",
    "Clothing and fetishwear",
    "Tickling",
    "Recording and photos",
    "Sex outdoors",
    "Sex in water and showers",
    "First time after long tension",
    "Service and objectification",
    "Zoophilia",
    "Fantasy species and knotting",
    "Incest and family dynamics",
    "Massage and sensual vanilla",
    "Public and semi-public sex",
    "Marks and bruising",
    "Rough sex",
    "Gore, injury and vore",
    "Blood play",
    "Branding, piercing and tattoos",
}
FLEX = re.compile(
    r"\((?:(?:s|es|ed|ing|d|t|rs|ts|ies|ier|iest|med|ming|ged|ging|ged|ped|ping|ped|ning|sed|sing)\b[^()]*)\)\??"
)
ALLOWED = {
    'Dominance and submission': {'master', 'slave'},
    'Oral sex': {'oral'},
    'Positions': {'positions?'},
    'Recording and photos': {'camera'},
    'Gore, injury and vore': {'wound'},
    'Blood play': {'bleed'},
    'Branding, piercing and tattoos': {'tattoo'},
    'Massage and sensual vanilla': {'massage'},
}
failures = []


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        failures.append(name)


def alternatives(pattern):
    """Split a regex body on top-level | and drop suffix-only groups."""
    if pattern.startswith(r"\b(") and pattern.endswith(r")\b"):
        pattern = pattern[3:-3]
    out, cur, depth = [], "", 0
    for c in pattern:
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        if c == "|" and depth == 0:
            out.append(cur)
            cur = ""
            continue
        cur += c
    out.append(cur)
    cleaned = []
    for alt in out:
        alt = alt.replace(r"\b", "").replace("?", "?")
        alt = FLEX.sub("", alt)
        cleaned.append(alt)
    return cleaned


def needs_context(alt):
    """True when an ambiguous token is all this alternative says."""
    first = re.match(r"[a-z]+", alt)
    if not first:
        return False
    if first.group(0) not in AMBIGUOUS:
        return False
    rest = alt[len(first.group(0)) :]
    rest = FLEX.sub(" ", rest)
    words = re.findall(r"[a-z]{2,}", rest)
    return not words


def main():
    if not SRC.exists():
        sys.exit(f"error: missing source file {SRC}")
    src = parse_src(SRC.read_text(encoding="utf-8"))
    canonical = src["meta"].get("secondary_sex")
    check("meta defines the shared secondary filter", bool(canonical))
    seen = {}

    for e in src["entries"]:
        comment = e.get("comment", "")
        keys = split_keys(e.get("keys", ""))
        check(f"one primary key: {comment}", len(keys) == 1, f"{len(keys)} keys")
        for k in keys:
            m = re.match(r"^/(.+)/([a-z]*)$", k)
            if not m:
                check(f"regex shape: {comment}", False, repr(k))
                continue
            try:
                re.compile(m.group(1))
            except re.error as err:
                check(f"compiles: {comment}", False, str(err))
                continue
            check(f"compiles: {comment}", True)
            inner = m.group(1)
            check(
                f"has word boundaries: {comment}",
                inner.startswith(r"\b") and inner.endswith(r"\b"),
                inner[:20],
            )
            bare = [a for a in alternatives(inner) if needs_context(a) and a not in ALLOWED.get(comment, set())]
            check(
                f"no bare ambiguous alternative: {comment}",
                not bare,
                ", ".join(bare[:3]),
            )
            seen.setdefault(k, []).append(comment)

        secondaries = split_keys(e.get("secondary_keys", ""))
        check(f"one secondary: {comment}", len(secondaries) <= 1, f"{len(secondaries)}")
        for s in secondaries:
            m = re.match(r"^/(.+)/([a-z]*)$", s)
            if not m:
                check(f"secondary shape: {comment}", False, repr(s))
                continue
            try:
                re.compile(m.group(1))
                check(f"secondary compiles: {comment}", True)
            except re.error as err:
                check(f"secondary compiles: {comment}", False, str(err))
            if canonical:
                check(f"secondary matches meta: {comment}", s == canonical, s[:40])
        if comment in SITUATIONAL:
            check(f"situational entry is filtered: {comment}", len(secondaries) == 1)
        else:
            check(f"not filtered: {comment}", not secondaries)

    for k, comments in seen.items():
        check(f"unique key: {k[:40]}", len(comments) == 1, ", ".join(comments))

    print(f"\n{len(failures)} failure(s)")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
