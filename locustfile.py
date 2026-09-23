"""
Locust entrypoint — Phase 19 realistic desk mix against site `performance`.

Usage (from this app directory):

  pip install -r requirements-loadtest.txt
  bench --site performance execute performance_testing.setup.seed_loadtest.seed
  locust -f locustfile.py --host http://127.0.0.1:8006

UI: http://localhost:8089
Headless ramp example: see scripts/run_ramp.sh
"""

from loadtest.personas import (  # noqa: F401
	AccountsUser,
	ManufacturingUser,
	PurchaseUser,
	ReportUser,
	SalesUser,
	StockUser,
)
