"""Defaults for Locust runs against the local `performance` site."""

from __future__ import annotations

import json
import os
import random
from pathlib import Path

LOADTEST_DIR = Path(__file__).resolve().parent
USERS_FILE = Path(os.environ.get("PERF_USERS_FILE", LOADTEST_DIR / "users.json"))
COMPANIES_FILE = Path(os.environ.get("PERF_COMPANIES_FILE", LOADTEST_DIR / "companies.json"))

BASE_URL = os.environ.get("PERF_BASE_URL", "http://127.0.0.1:8006")
SITE_HOST = os.environ.get("PERF_SITE_HOST", "performance")
COMPANY = os.environ.get("PERF_COMPANY", "Fusion")  # fallback only
PASSWORD = os.environ.get("PERF_PASSWORD", "PerfTest@123")
FISCAL_YEAR = os.environ.get("PERF_FISCAL_YEAR", "2026-2027")

THINK_TIME_MIN = float(os.environ.get("PERF_THINK_MIN", "3"))
THINK_TIME_MAX = float(os.environ.get("PERF_THINK_MAX", "8"))

SEED = {
	"selling_price_list": "Standard Selling",
	"buying_price_list": "Standard Buying",
}

PERSONA_COUNTS = {
	"sales": 25,
	"purchase": 15,
	"stock": 15,
	"accounts": 20,
	"mfg": 10,
	"report": 15,
}


def load_users() -> list[dict]:
	if not USERS_FILE.exists():
		raise FileNotFoundError(
			f"Missing {USERS_FILE}. Run: bench --site performance execute "
			"performance_testing.setup.seed_loadtest.seed"
		)
	return json.loads(USERS_FILE.read_text())


def load_companies() -> list[dict]:
	if not COMPANIES_FILE.exists():
		raise FileNotFoundError(
			f"Missing {COMPANIES_FILE}. Re-run seed to create 10 PERF companies."
		)
	return json.loads(COMPANIES_FILE.read_text())


def users_for_persona(persona: str) -> list[dict]:
	return [u for u in load_users() if u.get("persona") == persona]


def random_company() -> dict:
	companies = load_companies()
	if not companies:
		raise RuntimeError("No companies in companies.json")
	return random.choice(companies)
