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

NONCODING_OUTPUT_ROOT="$TEMPORARY/noncoding-output"
mkdir -m 700 "$NONCODING_OUTPUT_ROOT"
NONCODING_STATUS="$(python3 -m mva_prioritizer.cli noncoding-benchmark \
  --fixture tests/fixtures/noncoding_benchmark_cases.json \
  --config config/noncoding-benchmark-v1.json \
  --acquisition-manifest config/noncoding-acquisition-v1.json \
  --output-root "$NONCODING_OUTPUT_ROOT")"
printf '%s\n' "$NONCODING_STATUS"
python3 -c 'import json, sys; value = json.loads(sys.argv[1]); assert value["state"] == "ready_for_tool_smoke"; assert value["case_count"] == 14; assert value["passed_case_count"] == 14; assert value["external_actions"] == 0; assert value["private_execution_authorized"] is False; assert value["run_id"].startswith("benchmark-")' "$NONCODING_STATUS"
python3 -c 'import sys; from pathlib import Path; root = Path(sys.argv[1]); runs = [path for path in root.glob("benchmark-*") if path.is_dir()]; assert len(runs) == 1; assert {path.name for path in runs[0].iterdir()} == {"benchmark-public.json", "benchmark-report.json", "receipt.json"}' "$NONCODING_OUTPUT_ROOT"
printf '%s\n' 'noncoding_benchmark=pass'
