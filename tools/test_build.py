#!/usr/bin/env python3
"""Build gate: the delivered JSON must equal a fresh build of the source."""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = Path(os.environ.get("KINK_SRC", ROOT / "Kink & Explicit Scenes.card.txt"))
OUT = Path(os.environ.get("KINK_OUT", ROOT / "Kink & Explicit Scenes.json"))
CARDTOOL = ROOT / "cardtool.py"
failures = []


def check(name, ok, detail=""):
    print(f'{"PASS" if ok else "FAIL"} {name}' + (f' — {detail}' if detail else ''))
    if not ok:
        failures.append(name)


def main():
    if "--missing" in sys.argv:
        p = subprocess.run([sys.executable, str(CARDTOOL), "book", "/nonexistent/card.txt", "--out", "/tmp/x.json"],
                           capture_output=True, text=True)
        check("missing source is readable", p.returncode != 0 and "no such file" in p.stderr + p.stdout)
    else:
        check("source exists", SRC.exists(), str(SRC))
        check("export exists", OUT.exists(), str(OUT))
        if SRC.exists() and OUT.exists():
            with tempfile.TemporaryDirectory() as td:
                fresh = Path(td) / "fresh.json"
                p = subprocess.run([sys.executable, str(CARDTOOL), "book", str(SRC), "--out", str(fresh)],
                                   capture_output=True, text=True)
                check("build succeeds", p.returncode == 0, p.stderr.strip())
                check("export matches source", fresh.exists() and
                      json.loads(fresh.read_text(encoding="utf-8")) == json.loads(OUT.read_text(encoding="utf-8")))
    print(f"\n{len(failures)} failure(s)")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
