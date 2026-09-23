#!/usr/bin/env bash
# Phase 19 Locust ramp against site `performance` (bench baseline).
# Prerequisites:
#   - bench start (web on :8006)
#   - pip install -r requirements-loadtest.txt
#   - bench --site performance execute performance_testing.setup.seed_loadtest.seed
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PERF_BASE_URL="${PERF_BASE_URL:-http://127.0.0.1:8006}"
export PERF_SITE_HOST="${PERF_SITE_HOST:-performance}"

run_step() {
  local users=$1
  local minutes=$2
  local label=$3
  echo "=== ${label}: ${users} users × ${minutes} min ==="
  locust -f locustfile.py \
    --host "$PERF_BASE_URL" \
    --headless \
    -u "$users" \
    -r "$(python3 -c "print(max(1, $users // 10))")" \
    -t "${minutes}m" \
    --csv "loadtest/results_${label}" \
    --html "loadtest/results_${label}.html" \
    --only-summary
}

run_step 5 5 warmup
run_step 10 10 step1
run_step 25 10 step2
run_step 50 15 step3
run_step 100 20 step4
echo "Cool-down: stop load; check RQ with: bench --site performance worker --queue short  (or bench doctor)"
