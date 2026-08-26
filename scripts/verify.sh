#!/usr/bin/env bash
set -euo pipefail
umask 077

ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
cd "$ROOT"

python3 -m compileall -q mva_prioritizer scripts tests
printf '%s\n' 'compile=pass'

if [[ "${MVA_VERIFY_TEST_MODE:-0}" == "1" ]]; then
  printf '%s\n' 'unit_tests=skipped_test_mode'
else
  python3 -m unittest discover -s tests -v
  printf '%s\n' 'unit_tests=pass'
fi

python3 scripts/known_bad_tests.py
printf '%s\n' 'known_bad=pass'

python3 scripts/verify_public_tree.py
printf '%s\n' 'public_source_scan=pass'

TEMPORARY_RAW="$(mktemp -d)"
trap 'rm -rf "$TEMPORARY_RAW"' EXIT
TEMPORARY="$(cd "$TEMPORARY_RAW" && pwd -P)"
OUTPUT_ROOT="$TEMPORARY/output"
mkdir -m 700 "$OUTPUT_ROOT"

python3 -m mva_prioritizer.cli synthetic-run \
  --fixture tests/fixtures/synthetic_case.json \
  --config config/scoring-v1.json \
  --output-root "$OUTPUT_ROOT"

RUN_DIRECTORY=""
for candidate in "$OUTPUT_ROOT"/run-*; do
  RUN_DIRECTORY="$candidate"
done
if [[ -z "$RUN_DIRECTORY" ]]; then
  printf '%s\n' 'synthetic_journey=failed' >&2
  exit 1
fi

python3 -m mva_prioritizer.cli verify-run \
  --fixture tests/fixtures/synthetic_case.json \
  --config config/scoring-v1.json \
  --run-directory "$RUN_DIRECTORY"
printf '%s\n' 'synthetic_journey=pass'
