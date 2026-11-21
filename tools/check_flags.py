#!/usr/bin/env python3
"""Flag and placement gate."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from cardtool import parse_src

SRC = Path(os.environ.get("KINK_SRC", ROOT / "Kink & Explicit Scenes.card.txt"))
CONTROL = {
    "Explicit vocabulary": ("at_depth", 1, "system", 170, 8),
    "Explicit scene direction": ("at_depth", 2, "system", 150, 8),
    "Explicitness - maximum": ("at_depth", 1, "system", 160, 8),
    "Reply focus (randomized)": ("at_depth", 1, "system", 140, 8),
    "Hardcore set pieces": ("at_depth", 1, "system", 165, 8),
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
}

failures = []


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        failures.append(name)


def main():
    src = parse_src(SRC.read_text(encoding="utf-8"))
    for e in src["entries"]:
        c = e.get("comment", "")
        if c in CONTROL:
            pos, depth, role, order, sticky = CONTROL[c]
        else:
            pos = "after_char"
            depth = None
            role = None
            order = (
                "100"
                if c
                in (
                    "Sex outdoors",
                    "Sex in water and showers",
                    "First time after long tension",
                )
                else "105"
                if c in SITUATIONAL
                else "110"
            )
            sticky = "8" if c == "First time after long tension" else "5"
        check(
            f"position: {c}",
            e.get("position", "after_char") == pos,
            e.get("position", "after_char"),
        )
        check(f"order: {c}", str(e.get("order", "100")) == str(order), e.get("order", "100"))
        check(f"sticky: {c}", str(e.get("sticky", "0")) == str(sticky), e.get("sticky", "0"))
        if depth:
            check(f"depth: {c}", e.get("depth") == str(depth), e.get("depth", ""))
        if role:
            check(f"role: {c}", e.get("role") == role, e.get("role", ""))
        check(
            f"prevents recursion: {c}",
            e.get("prevent_recursion") == "true",
            e.get("prevent_recursion", "false"),
        )
        check(
            f"probability 100: {c}",
            e.get("probability", "100") == "100",
            e.get("probability", "100"),
        )
        check(
            f"not constant: {c}",
            e.get("constant", "false") == "false",
            e.get("constant", "false"),
        )
        check(
            f"enabled: {c}",
            e.get("enabled", "true") == "true",
            e.get("enabled", "true"),
        )

    print(f"\n{len(failures)} failure(s)")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
