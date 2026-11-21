#!/usr/bin/env python3
"""Activation and budget tests for the kink lorebook.

Simulates SillyTavern key matching: a primary key must match, and if the entry
has a secondary key that must match too (ANY logic). Each positive sample has
an exact expected activation set, so an unexpected entry fails as well.

  python3 tools/test_activation.py            # everything
  python3 tools/test_activation.py --entry "Oral sex"
  python3 tools/test_activation.py --case recursion
  python3 tools/test_activation.py --budget

KINK_SRC / KINK_SAMPLES override the files, so self-tests can use fixtures.
"""

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from cardtool import parse_src, split_keys, tok  # noqa: E402

SRC = Path(os.environ.get("KINK_SRC", ROOT / "Kink & Explicit Scenes.card.txt"))
SAMPLES = Path(os.environ.get("KINK_SAMPLES", ROOT / "tools" / "samples.json"))
LIMITS = {
    "entry": 320,
    "kink_min": 120,
    "kink_max": 260,
    "control_min": 150,
    "control_max": 300,
    "book": 16000,
    "scene": 2600,
}
CONTROLS = {
    "Explicit vocabulary",
    "Explicit scene direction",
    "Explicitness - maximum",
    "Reply focus (randomized)",
    "Hardcore set pieces",
}

failures = []


def expand(text):
    """Measure random macros at their longest alternative."""
    return re.sub(r"\{\{random::(.*?)\}\}", lambda m: max(m.group(1).split("::"), key=len), text)


def load_entries():
    if not SRC.exists():
        sys.exit(f"error: missing source file {SRC}")
    src = parse_src(SRC.read_text(encoding="utf-8"))
    out = []
    for e in src["entries"]:
        content = e.get("content", "")
        out.append(
            {
                "comment": e.get("comment", ""),
                "keys": [
                    re.compile(k[1 : k.rindex("/")], re.I)
                    for k in split_keys(e.get("keys", ""))
                    if k.startswith("/") and k.rindex("/") > 1
                ],
                "secondary": [
                    re.compile(k[1 : k.rindex("/")], re.I)
                    for k in split_keys(e.get("secondary_keys", ""))
                    if k.startswith("/") and k.rindex("/") > 1
                ],
                "content": content,
                "expanded": expand(content),
            }
        )
    return out


def match(entries, text):
    hits = []
    for e in entries:
        if not e["keys"]:
            continue
        if not any(k.search(text) for k in e["keys"]):
            continue
        if e["secondary"] and not any(k.search(text) for k in e["secondary"]):
            continue
        hits.append(e["comment"])
    return hits


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        failures.append(name)


def diff(expected, got):
    extra = sorted(set(got) - set(expected))
    miss = sorted(set(expected) - set(got))
    bits = []
    if miss:
        bits.append("missing: " + ", ".join(miss))
    if extra:
        bits.append("unexpected: " + ", ".join(extra))
    return "; ".join(bits)


def positives(entries, data, expected_all, freeze=False):
    names = {e["comment"] for e in entries}
    missing = [e["comment"] for e in entries if e["comment"] not in data]
    check("positives: every entry has a sample", not missing, ", ".join(missing))
    if freeze:
        return {c: sorted(match(entries, t)) for c, t in data.items() if c in names}
    absent = [c for c in names if c not in expected_all]
    check("positives: expected sets frozen", not absent, ", ".join(absent[:5]))
    for comment, text in data.items():
        if comment not in names:
            check(f"positives: {comment}", False, "no such entry")
            continue
        expected = set(expected_all.get(comment, []))
        got = match(entries, text)
        check(f"positives: {comment}", set(got) == expected, diff(expected, got))


def corpus(entries, lines):
    check("corpus: at least 60 lines", len(lines) >= 60, f"{len(lines)} lines")
    for line in lines:
        hits = match(entries, line)
        check(
            f"corpus: {line[:44]}",
            not hits,
            "fired: " + ", ".join(hits) if hits else "",
        )


def recursion(entries, cases):
    for i, (label, text, expect) in enumerate(cases, 1):
        got = match(entries, text)
        check(f"recursion {i}: {label}", set(got) == set(expect), diff(expect, got))


def sizes(entries):
    return {e["comment"]: tok(e["expanded"]) for e in entries}


def budget(entries):
    measured = sizes(entries)
    total = sum(measured.values())
    biggest = max(measured.items(), key=lambda x: x[1])
    print(f"  book ~{total} tokens, largest {biggest[0]} ~{biggest[1]}")
    check("budget: whole book", total <= LIMITS["book"], f"{total} / {LIMITS['book']}")
    check(
        "budget: every entry",
        biggest[1] <= LIMITS["entry"],
        f"{biggest[0]} {biggest[1]} / {LIMITS['entry']}",
    )


def scene_budget(entries, scenes, expected):
    worst = (0, "none", [])
    for label, text in scenes.items():
        hits = match(entries, text)
        check(f"scene activation: {label}", set(hits) == set(expected.get(label, [])), diff(expected.get(label, []), hits))
        used = sum(
            tok(next(e["expanded"] for e in entries if e["comment"] == h)) for h in hits
        )
        print(f"  scene {label}: {len(hits)} entries, ~{used} tokens")
        if used > worst[0]:
            worst = (used, label, hits)
    check(
        "budget: worst reference scene",
        worst[0] <= LIMITS["scene"],
        f"{worst[1]} {worst[0]} / {LIMITS['scene']} ({', '.join(worst[2])})",
    )


def entry_sizes(entries):
    for e in entries:
        n = tok(e["content"])
        if e["comment"] in CONTROLS:
            ok = LIMITS["control_min"] <= n <= LIMITS["control_max"]
            bound = f"{LIMITS['control_min']}-{LIMITS['control_max']}"
        else:
            ok = LIMITS["kink_min"] <= n <= LIMITS["kink_max"]
            bound = f"{LIMITS['kink_min']}-{LIMITS['kink_max']}"
        check(f"size: {e['comment']}", ok, f"{n} / {bound}")


def main():
    args = sys.argv[1:]
    entry_filter = args[args.index("--entry") + 1] if "--entry" in args else None
    case = args[args.index("--case") + 1] if "--case" in args else None
    freeze = "--freeze" in args
    entries = load_entries()
    data = json.loads(SAMPLES.read_text(encoding="utf-8"))
    check("source: entries found", bool(entries), f"{len(entries)} entries")

    if case == "vocabulary-only":
        hits = match(entries, "He pushed inside her and fucked her slowly.")
        check(
            "vocabulary-only: Explicit vocabulary fires",
            "Explicit vocabulary" in hits,
            ", ".join(hits),
        )
    elif case == "non-sexual-pond":
        hits = match(
            entries,
            "She ran for the pond and sat on the dock in her shorts, moonlight on the water.",
        )
        check(
            "non-sexual-pond: nothing fires",
            not hits,
            "fired: " + ", ".join(hits) if hits else "",
        )
    elif case == "recursion":
        recursion(entries, data["recursion"])
    elif case == "explicit-director":
        text = (
            "Write them fucking on the platform. NC-17, pornographic, as explicit as it gets. "
            "They dive into kinky sex."
        )
        hits = match(entries, text)
        want = sorted(CONTROLS)
        check(
            "explicit-director: all control entries fire",
            all(w in hits for w in want),
            ", ".join(hits),
        )
    elif case:
        sys.exit(f"error: unknown case {case!r}")
    elif entry_filter:
        if entry_filter not in data:
            sys.exit(f"error: no sample for {entry_filter!r}")
        hits = match(entries, data[entry_filter])
        check(
            f"entry: {entry_filter}",
            entry_filter in hits,
            "fired: " + (", ".join(hits) or "nothing"),
        )
        return finish()
    else:
        expected_all = positives(
            entries,
            {
                k: v
                for k, v in data.items()
                if k not in ("corpus", "recursion", "scenes", "expected", "expected_all", "scene_expected")
            },
            data.get("expected_all", {}),
            freeze,
        )
        if freeze:
            data["expected_all"] = expected_all
            data["scene_expected"] = {k: sorted(match(entries, v)) for k, v in data["scenes"].items()}
            SAMPLES.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print(f"froze {len(expected_all)} expected sets and {len(data['scenes'])} scene sets")
            return finish()
        corpus(entries, data["corpus"])
        recursion(entries, data["recursion"])
        entry_sizes(entries)
        budget(entries)
        scene_budget(entries, data["scenes"], data.get("scene_expected", {}))

    return finish()


def finish():
    print(f"\n{len(failures)} failure(s)")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
