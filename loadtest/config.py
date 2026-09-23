"""Defaults for Locust runs against the local `performance` site."""

from __future__ import annotations

import json
import os
from pathlib import Path

LOADTEST_DIR = Path(__file__).resolve().parent
USERS_FILE = Path(os.environ.get("PERF_USERS_FILE", LOADTEST_DIR / "users.json"))

# bench serve --port 8006; site name must be Host header
BASE_URL = os.environ.get("PERF_BASE_URL", "http://127.0.0.1:8006")
SITE_HOST = os.environ.get("PERF_SITE_HOST", "performance")
COMPANY = os.environ.get("PERF_COMPANY", "Fusion")
PASSWORD = os.environ.get("PERF_PASSWORD", "PerfTest@123")
FISCAL_YEAR = os.environ.get("PERF_FISCAL_YEAR", "2026-2027")

# Phase 19 think time (seconds)
THINK_TIME_MIN = float(os.environ.get("PERF_THINK_MIN", "3"))
THINK_TIME_MAX = float(os.environ.get("PERF_THINK_MAX", "8"))

# Shared masters used by write paths (seed script fills these)
  
PERSONA_COUNTS = {
	"sales": 25,
	"purchase": 15,
	"stock": 15,
	"accounts": 20,
	"mfg": 10,
	"report": 15,
}

PERSONA_ROLES = {
	"sales": ["Sales User", "Sales Manager", "Stock User", "Accounts User"],
	"purchase": ["Purchase User", "Purchase Manager", "Stock User", "Accounts User"],
	"stock": ["Stock User", "Stock Manager"],
	"accounts": ["Accounts User", "Accounts Manager"],
	"mfg": ["Manufacturing User", "Manufacturing Manager", "Stock User"],
	"report": ["Accounts Manager", "Sales Manager", "Purchase Manager", "Stock Manager"],
}


def load_users() -> list[dict]:
	if not USERS_FILE.exists():
		raise FileNotFoundError(
			f"Missing {USERS_FILE}. Run: bench --site performance execute "
			"performance_testing.setup.seed_loadtest.seed"
		)
	return json.loads(USERS_FILE.read_text())


def users_for_persona(persona: str) -> list[dict]:
	return [u for u in load_users() if u.get("persona") == persona]
