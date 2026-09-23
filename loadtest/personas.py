"""Phase 19 desk-mix personas (~40% write / ~60% read per user loop)."""

from __future__ import annotations

import random
from datetime import date, timedelta

from locust import HttpUser, between, task

from loadtest import config
from loadtest.client import FrappeDeskClient


def _pick_name(rows: list[dict]) -> str | None:
	if not rows:
		return None
	return rows[0].get("name") or random.choice(rows).get("name")


def _today() -> str:
	return date.today().isoformat()


def _future(days: int = 7) -> str:
	return (date.today() + timedelta(days=days)).isoformat()


class DeskMixUser(HttpUser):
	abstract = True
	persona = ""
	wait_time = between(config.THINK_TIME_MIN, config.THINK_TIME_MAX)

	def on_start(self):
		pool = config.users_for_persona(self.persona)
		if not pool:
			raise RuntimeError(f"No users for persona={self.persona}. Seed loadtest users first.")
		# Round-robin by Locust worker user count is hard; random is fine for mix
		self.creds = random.choice(pool)
		self.desk = FrappeDeskClient(self, self.creds)
		self.desk.login()
		self.company = config.COMPANY
		self._cache: dict = {}

	def _list_and_open(self, doctype: str) -> str | None:
		rows = self.desk.list_docs(doctype, limit=20)
		# paginate once
		self.desk.list_docs(doctype, limit=20)
		name = _pick_name(rows)
		if name:
			self.desk.getdoc(doctype, name)
		return name

	def _random_customer(self) -> str | None:
		if "customers" not in self._cache:
			self._cache["customers"] = [
				r["name"] for r in self.desk.list_docs("Customer", limit=50) if r.get("name")
			]
		return random.choice(self._cache["customers"]) if self._cache["customers"] else None

	def _random_supplier(self) -> str | None:
		if "suppliers" not in self._cache:
			self._cache["suppliers"] = [
				r["name"] for r in self.desk.list_docs("Supplier", limit=50) if r.get("name")
			]
		return random.choice(self._cache["suppliers"]) if self._cache["suppliers"] else None

	def _random_item(self) -> str | None:
		if "items" not in self._cache:
			self._cache["items"] = [
				r["name"] for r in self.desk.list_docs("Item", limit=50) if r.get("name")
			]
		return random.choice(self._cache["items"]) if self._cache["items"] else None

	def after_loop(self):
		self.desk.maybe_relogin(0.05)


class SalesUser(DeskMixUser):
	persona = "sales"
	weight = 25

	@task
	def loop(self):
		roll = random.random()
		self._list_and_open("Sales Order")
		if roll < 0.40:
			self._create_sales_order(submit=random.random() < 0.5)
		elif roll < 0.70:
			# delivery / invoice paths: open related doctypes (create only if SO exists)
			name = self._list_and_open("Delivery Note") or self._list_and_open("Sales Invoice")
			if not name:
				self._list_and_open("Customer")
		else:
			self._list_and_open("Customer")
		self.after_loop()

	def _create_sales_order(self, submit: bool = False):
		customer = self._random_customer()
		item = self._random_item()
		if not customer or not item:
			return
		doc = {
			"doctype": "Sales Order",
			"naming_series": "SAL-ORD-.YYYY.-",
			"company": self.company,
			"customer": customer,
			"transaction_date": _today(),
			"delivery_date": _future(7),
			"order_type": "Sales",
			"selling_price_list": config.SEED["selling_price_list"],
			"set_warehouse": config.SEED["warehouse"],
			"items": [
				{
					"doctype": "Sales Order Item",
					"item_code": item,
					"qty": 1,
					"rate": 100,
					"delivery_date": _future(7),
					"warehouse": config.SEED["warehouse"],
				}
			],
		}
		saved = self.desk.savedocs(doc, "Save")
		if submit and saved and saved.get("name"):
			saved["doctype"] = "Sales Order"
			self.desk.savedocs(saved, "Submit")


class PurchaseUser(DeskMixUser):
	persona = "purchase"
	weight = 15

	@task
	def loop(self):
		roll = random.random()
		self._list_and_open("Purchase Order")
		if roll < 0.40:
			self._create_purchase_order(submit=True)
		elif roll < 0.70:
			self._list_and_open("Purchase Receipt") or self._list_and_open("Purchase Invoice")
		else:
			self._list_and_open("Supplier")
		self.after_loop()

	def _create_purchase_order(self, submit: bool = False):
		supplier = self._random_supplier()
		item = self._random_item()
		if not supplier or not item:
			return
		doc = {
			"doctype": "Purchase Order",
			"naming_series": "PUR-ORD-.YYYY.-",
			"company": self.company,
			"supplier": supplier,
			"transaction_date": _today(),
			"schedule_date": _future(7),
			"buying_price_list": config.SEED["buying_price_list"],
			"set_warehouse": config.SEED["warehouse"],
			"items": [
				{
					"doctype": "Purchase Order Item",
					"item_code": item,
					"qty": 1,
					"rate": 80,
					"schedule_date": _future(7),
					"warehouse": config.SEED["warehouse"],
				}
			],
		}
		saved = self.desk.savedocs(doc, "Save")
		if submit and saved and saved.get("name"):
			saved["doctype"] = "Purchase Order"
			self.desk.savedocs(saved, "Submit")


class StockUser(DeskMixUser):
	persona = "stock"
	weight = 15

	@task
	def loop(self):
		roll = random.random()
		self._list_and_open("Stock Entry")
		if roll < 0.40:
			self._create_material_receipt(submit=True)
		elif roll < 0.70:
			self.desk.run_report(
				"Stock Balance",
				{"company": self.company, "warehouse": config.SEED["warehouse"]},
			)
		else:
			self.desk.run_report(
				"Stock Ledger",
				{
					"company": self.company,
					"from_date": _today(),
					"to_date": _today(),
					"warehouse": config.SEED["warehouse"],
				},
			)
		self.after_loop()

	def _create_material_receipt(self, submit: bool = False):
		item = self._random_item()
		if not item:
			return
		doc = {
			"doctype": "Stock Entry",
			"naming_series": "MAT-STE-.YYYY.-",
			"company": self.company,
			"stock_entry_type": "Material Receipt",
			"purpose": "Material Receipt",
			"to_warehouse": config.SEED["warehouse"],
			"items": [
				{
					"doctype": "Stock Entry Detail",
					"item_code": item,
					"qty": 1,
					"t_warehouse": config.SEED["warehouse"],
					"basic_rate": 50,
					"allow_zero_valuation_rate": 1,
				}
			],
		}
		saved = self.desk.savedocs(doc, "Save")
		if submit and saved and saved.get("name"):
			saved["doctype"] = "Stock Entry"
			self.desk.savedocs(saved, "Submit")


class AccountsUser(DeskMixUser):
	persona = "accounts"
	weight = 20

	@task
	def loop(self):
		roll = random.random()
		if roll < 0.35:
			self._list_and_open("Payment Entry")
			self._create_journal_entry(submit=random.random() < 0.3)
		elif roll < 0.60:
			self._create_journal_entry(submit=True)
		else:
			self.desk.run_report(
				"General Ledger",
				{
					"company": self.company,
					"from_date": (date.today().replace(day=1)).isoformat(),
					"to_date": _today(),
				},
			)
			if random.random() < 0.5:
				self._list_and_open("Sales Invoice")
			else:
				self._list_and_open("Purchase Invoice")
		self.after_loop()

	def _create_journal_entry(self, submit: bool = False):
		# Balanced JE against income/expense — amounts cancel; safe under concurrency
		doc = {
			"doctype": "Journal Entry",
			"naming_series": "ACC-JV-.YYYY.-",
			"company": self.company,
			"posting_date": _today(),
			"voucher_type": "Journal Entry",
			"accounts": [
				{
					"doctype": "Journal Entry Account",
					"account": "Cash - F",
					"debit_in_account_currency": 1,
					"credit_in_account_currency": 0,
				},
				{
					"doctype": "Journal Entry Account",
					"account": "Cash - F",
					"debit_in_account_currency": 0,
					"credit_in_account_currency": 1,
				},
			],
			"user_remark": "perf loadtest",
		}
		# Prefer Cash; fall back to Debtors/Creditors if Cash missing
		saved = self.desk.savedocs(doc, "Save")
		if not saved:
			doc["accounts"][0]["account"] = "Debtors - F"
			doc["accounts"][1]["account"] = "Creditors - F"
			saved = self.desk.savedocs(doc, "Save")
		if submit and saved and saved.get("name"):
			saved["doctype"] = "Journal Entry"
			self.desk.savedocs(saved, "Submit")


class ManufacturingUser(DeskMixUser):
	persona = "mfg"
	weight = 10

	@task
	def loop(self):
		roll = random.random()
		self._list_and_open("Work Order")
		if roll < 0.40:
			self._list_and_open("Job Card")
		elif roll < 0.70:
			self._list_and_open("BOM")
		# else: WO list already done
		self.after_loop()


class ReportUser(DeskMixUser):
	persona = "report"
	weight = 15

	@task
	def loop(self):
		start = _month_start()
		today = _today()
		report = random.choice(
			[
				(
					"Profit and Loss Statement",
					{
						"company": self.company,
						"filter_based_on": "Date Range",
						"period_start_date": start,
						"period_end_date": today,
						"from_date": start,
						"to_date": today,
						"periodicity": "Monthly",
					},
				),
				(
					"Trial Balance",
					{
						"company": self.company,
						"fiscal_year": config.FISCAL_YEAR,
						"from_date": start,
						"to_date": today,
					},
				),
				("Stock Balance", {"company": self.company}),
				(
					"Sales Register",
					{"from_date": start, "to_date": today, "company": self.company},
				),
			]
		)
		self.desk.run_report(report[0], report[1])
		self.desk.desk_ping()
		self.after_loop()


def _month_start() -> str:
	return date.today().replace(day=1).isoformat()
