#!/usr/bin/env python3
"""Phrase-list gate: count, length, quoting, duplicates, licence.

Read-only by default. `--fix` removes duplicates and rewrites the list.
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIR = Path(os.environ.get("KINK_ANTISLOP", ROOT / "antislop"))
LIST = DIR / "erotica-phrases.txt"
CAP = 700

failures = []


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        failures.append(name)


def main():
    check("list exists", LIST.exists())
    if not LIST.exists():
        sys.exit(1)
    lines = LIST.read_text(encoding="utf-8").splitlines()
    lines = [l for l in lines if l.strip()]
    check("count cap", len(lines) <= CAP, f"{len(lines)} / {CAP}")
    check("not empty", bool(lines))

    bad_quote = [
        l
        for l in lines
        if not (l.startswith('"') and l.endswith('"') and l.count('"') == 2)
    ]
    check("every line is quoted", not bad_quote, ", ".join(bad_quote[:3]))

    inner = [l[1:-1] for l in lines]
    short = [p for p in inner if len(p) <= 12]
    check("shortest phrase over 12 characters", not short, ", ".join(short[:3]))

    seen, kept, removed = set(), [], []
    for line in lines:
        low = line.lower()
        if low in seen:
            removed.append(line)
            continue
        seen.add(low)
        kept.append(line)
    if removed and "--fix" in sys.argv:
        LIST.write_text("\n".join(kept) + "\n", encoding="utf-8")
        lines = kept
        inner = [l[1:-1] for l in lines]
        check("duplicates removed", True, f"{len(removed)} removed")
    else:
        check("no duplicates", not removed, ", ".join(removed[:3]) if removed else "none found")

    check(
        "bare erotic words absent",
        not ({"cum", "cock", "cunt", "clit", "come"} & {p.lower() for p in inner}),
    )
    check("licence shipped", (DIR / "antislop-sampler-LICENSE").exists())

    print(f"\n{len(lines)} phrases, {len(failures)} failure(s)")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
