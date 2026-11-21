#!/usr/bin/env python3
"""Self-test: prove every gate fails for its intended reason.

Each case writes a throwaway source or sample folder, runs the real checker
against it through KINK_* environment variables, and requires the specific
diagnostic text. Nothing in the deliverable is modified.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
META = "secondary_sex: /\\b(sex|naked)\\b/i\n"
SEX_KEYS = "/\\b(sex|naked|cock)\\b/i"
GOOD = '[Kink: words here, his cock in her cunt, naked and moaning.]\n[Example: "His cock."]'


def card(entries, meta=META):
    out = ["=== meta ===", "name: Fixture", meta]
    for comment, keys, body, extra in entries:
        out += [
            "=== lorebook_entry ===",
            f"comment: {comment}",
            f"keys: {keys}",
            extra,
            "order: 110",
            "sticky: 5",
            "prevent_recursion: true",
            "---",
            body,
        ]
    return "\n".join(out) + "\n"


def run(tool, env):
    p = subprocess.run(
        [sys.executable, str(TOOLS / tool.split()[0]), *tool.split()[1:]],
        capture_output=True,
        text=True,
        env={**os.environ, **env},
    )
    return p.returncode, p.stdout + p.stderr


def case(name, entries, tool, extra=None, want="FAIL", msg="FAIL"):
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "src.card.txt"
        src.write_text(card(entries), encoding="utf-8")
        env = {"KINK_SRC": str(src)}
        for k, v in (extra or {}).items():
            pth = Path(td) / f"{k}.json"
            pth.write_text(json.dumps(v), encoding="utf-8")
            env[f"KINK_{k.upper()}"] = str(pth)
        code, out = run(tool, env)
        ok = (code == 0) if want == "PASS" else (code != 0 and msg in out)
        print(f"{'PASS' if ok else 'FAIL'} selftest: {name}")
        if not ok:
            print("  " + out.strip().splitlines()[-1])
        return ok


def builds(test):
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "c.card.txt"
        src.write_text(card([("Fine", SEX_KEYS, GOOD, "")]), encoding="utf-8")
        out = Path(td) / "out.json"
        out.write_text('{"entries": {}}', encoding="utf-8")
        code, text = run("test_build.py", {"KINK_SRC": str(src), "KINK_OUT": str(out)})
        ok = code != 0 and "export matches source" in text
        print(f"{'PASS' if ok else 'FAIL'} selftest: stale export is detected")
        test.append(ok)
    code, text = run("test_build.py --missing", {})
    ok = code == 0 and "missing source is readable" in text
    print(f"{'PASS' if ok else 'FAIL'} selftest: missing source message")
    test.append(ok)


def phrases(test):
    with tempfile.TemporaryDirectory() as td:
        d = Path(td) / "antislop"
        d.mkdir()
        (d / "antislop-sampler-LICENSE").write_text("x")
        listfile = d / "erotica-phrases.txt"
        listfile.write_text(
            '"a long phrase here"\n"a long phrase here"\n', encoding="utf-8"
        )
        code, out = run("check_phrases.py", {"KINK_ANTISLOP": str(d)})
        n = len(listfile.read_text(encoding="utf-8").splitlines())
        dry = code != 0 and n == 2 and "no duplicates" in out
        code2, out2 = run("check_phrases.py --fix", {"KINK_ANTISLOP": str(d)})
        n2 = len(listfile.read_text(encoding="utf-8").splitlines())
        ok = dry and code2 == 0 and n2 == 1 and "1 removed" in out2
        print(f"{'PASS' if ok else 'FAIL'} selftest: duplicates reported, then removed by --fix")
        test.append(ok)


def main():
    results = []
    good = ("Fine", SEX_KEYS, GOOD, "")
    results.append(case("valid fixture passes", [good], "check_keys.py", want="PASS"))
    results.append(
        case(
            "broken bracket names entry",
            [("Broken", "/\\b(sex|naked\\b/i", GOOD, "")],
            "check_keys.py",
            msg="unterminated subpattern",
        )
    )
    results.append(
        case("duplicate primary key", [good, good], "check_keys.py", msg="unique key")
    )
    results.append(
        case(
            "bare ambiguous word",
            [("Come", "/\\b(sex|come)\\b/i", GOOD, "")],
            "check_keys.py",
            msg="bare ambiguous alternative",
        )
    )
    results.append(
        case(
            "empty body",
            [("Empty", SEX_KEYS, "   ", "")],
            "check_vocab.py",
            msg="body present: Empty",
        )
    )
    results.append(
        case(
            "missing example",
            [("NoExample", SEX_KEYS, "Just words about a cock.", "")],
            "check_vocab.py",
            msg="has an example: NoExample",
        )
    )
    results.append(
        case(
            "probability drift",
            [("Drift", SEX_KEYS, GOOD, "probability: 70")],
            "check_flags.py",
            msg="probability 100: Drift",
        )
    )
    results.append(
        case(
            "missing coverage subject",
            [("Explicit vocabulary", SEX_KEYS, GOOD, "")],
            "check_coverage.py",
            msg="Explicit scene direction — found 0",
        )
    )
    sample = {
        "Explicit vocabulary": "His cock.",
        "Other": "nothing here",
        "corpus": [f"ordinary line {i}" for i in range(60)],
        "recursion": [],
        "scenes": {},
    }
    results.append(
        case(
            "corpus line that fires",
            [("Explicit vocabulary", SEX_KEYS, GOOD, "")],
            "test_activation.py",
            {"samples": sample},
            msg="corpus: ordinary line 0",
        )
    )
    phrases(results)
    builds(results)
    print(f"\n{len(results)} selftest(s), {results.count(False)} failure(s)")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
