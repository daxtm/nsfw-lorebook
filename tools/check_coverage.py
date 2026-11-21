#!/usr/bin/env python3
"""Coverage gate: every required subject exists exactly once."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from cardtool import parse_src

SRC = Path(os.environ.get("KINK_SRC", ROOT / "Kink & Explicit Scenes.card.txt"))
SUBJECTS = [
    "Explicit vocabulary",
    "Explicit scene direction",
    "Limits, safewords, check-ins",
    "Dominance and submission",
    "Switching",
    "Bratting and taming",
    "Bondage and restraint",
    "Rope bondage",
    "Impact play",
    "Marks and bruising",
    "Orgasm control",
    "Forced orgasms and overstimulation",
    "Praise kink",
    "Degradation and humiliation",
    "Consensual non-consent (CNC)",
    "Rough sex",
    "Choking and breath play",
    "Sensory deprivation and gags",
    "Sensation play",
    "Collars and leashes",
    "Sex toys",
    "Dirty talk",
    "Exhibitionism and voyeurism",
    "Subspace, domspace and drop",
    "Aftercare",
    "Explicitness - maximum",
    "Reply focus (randomized)",
    "Oral sex",
    "Anal sex, rimming, pegging",
    "Fingering and handjobs",
    "Positions",
    "Teasing and foreplay",
    "Body worship and nipple play",
    "Pet play",
    "Breeding and creampies",
    "Size difference",
    "Fluids and mess",
    "Sexual roleplay scenarios",
    "Masturbation and watching",
    "Foot play",
    "Primal play",
    "Sadism and masochism",
    "Multiple partners",
    "Clothing and fetishwear",
    "Tickling",
    "Recording and photos",
    "Edge play: knives and electricity",
    "Sex outdoors",
    "Sex in water and showers",
    "First time after long tension",
    "Service and objectification",
    "Ageplay and caregiver dynamics",
    "Non-con",
    "Zoophilia",
    "Fantasy species and knotting",
    "Necrophilia",
    "Gore, injury and vore",
    "Watersports",
    "Scat",
    "Blood play",
    "Incest and family dynamics",
    "Cuckolding and hotwifing",
    "Lactation",
    "Medical play",
    "Sounding",
    "Hypnosis and dollification",
    "Sissification",
    "Fisting and stretching",
    "CBT and ball play",
    "Kissing and making out",
    "Massage and sensual vanilla",
    "Food play",
    "Body writing",
    "Branding, piercing and tattoos",
    "Public and semi-public sex",
    "Somnophilia",
    "TPE, protocol and honorifics",
    "Leather and dungeon etiquette",
    "Hardcore set pieces",
    "Gear: suspension, chastity, machines",
]

failures = []


def main():
    src = parse_src(SRC.read_text(encoding="utf-8"))
    got = [e.get("comment", "") for e in src["entries"]]
    for s in SUBJECTS:
        n = got.count(s)
        ok = n == 1
        print(f"{'PASS' if ok else 'FAIL'} {s}" + ("" if ok else f" — found {n}"))
        if not ok:
            failures.append(s)
    for c in set(got):
        if c not in SUBJECTS:
            print(f"FAIL unexpected subject: {c}")
            failures.append(c)
    print(f"\n{len(SUBJECTS)} subjects, {len(got)} entries, {len(failures)} failure(s)")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
