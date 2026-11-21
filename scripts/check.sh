#!/usr/bin/env bash
# All project checks in one command. Lint must report exactly 2 warnings (lorebook-only source);
# every other check must exit 0.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

SRC="Kink & Explicit Scenes.card.txt"
fail=0

if lint_out=$(python3 cardtool.py lint "$SRC" 2>&1); then
	warns=$(printf '%s\n' "$lint_out" | grep -c '  WARN  ')
	if [ "$warns" -eq 2 ]; then
		echo "ok    lint (2 warnings as expected)"
	else
		echo "FAIL  lint: expected 2 warnings, got $warns"
		printf '%s\n' "$lint_out"
		fail=1
	fi
else
	echo "FAIL  lint"
	printf '%s\n' "$lint_out"
	fail=1
fi

for t in test_activation test_selftest test_build \
	check_vocab check_keys check_flags check_coverage check_phrases; do
	if out=$(python3 "tools/$t.py" 2>&1); then
		echo "ok    $t"
	else
		echo "FAIL  $t"
		printf '%s\n' "$out" | tail -20
		fail=1
	fi
done

[ "$fail" -eq 0 ] && echo "all checks passed"
exit "$fail"
