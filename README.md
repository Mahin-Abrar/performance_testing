# Performance testing

Locust desk-mix load tests for ERPNext site **`performance`** (Phase 19 concurrent users).

## Quick start

```bash
# 1. Install Locust into the bench env (once)
./env/bin/pip install -r apps/performance_testing/requirements-loadtest.txt

# 2. Seed masters + 100 perf_* users + API keys
bench --site performance execute performance_testing.setup.seed_loadtest.seed

# 3. Ensure site is serving (bench start → port 8006)
# 4. Run Locust UI
cd apps/performance_testing
../../env/bin/locust -f locustfile.py --host http://127.0.0.1:8006
# Open http://localhost:8089  → start with 10 users, spawn rate 2
```

## Phase 19 ramp (headless)

```bash
cd apps/performance_testing
./scripts/run_ramp.sh
```

Ramp: 5 → 10 → 25 → 50 → **100** users. HTML/CSV reports land in `loadtest/results_*`.

## Desk mix (Locust weights)

| Persona class | Weight | Users @100 |
|---|---:|---:|
| SalesUser | 25 | 25 |
| PurchaseUser | 15 | 15 |
| StockUser | 15 | 15 |
| AccountsUser | 20 | 20 |
| ManufacturingUser | 10 | 10 |
| ReportUser | 15 | 15 |

Think time 3–8s. Hits Desk endpoints: login / list / getdoc / savedocs / query_report (not full Playwright).

## Config env vars

| Variable | Default |
|---|---|
| `PERF_BASE_URL` | `http://127.0.0.1:8006` |
| `PERF_SITE_HOST` | `performance` |
| `PERF_COMPANY` | `Fusion` |
| `PERF_USERS_FILE` | `loadtest/users.json` |
| `PERF_THINK_MIN` / `PERF_THINK_MAX` | `3` / `8` |

Label results as **bench baseline** while `developer_mode=1`.

## License

mit
