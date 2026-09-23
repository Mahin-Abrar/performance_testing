"""Phase 19 desk-mix personas — multi-company full sales/purchase flows."""

from __future__ import annotations

import random
from datetime import date, timedelta

from locust import HttpUser, between, task

from loadtest import config
from loadtest.client import FrappeDeskClient


def _pick_name(rows: list[dict]) -> str | None:
	if not rows:
		return None
	return random.choice(rows).get("name")


def _today() -> str:
	return date.today().isoformat()


def _future(days: int = 7) -> str:
	return (date.today() + timedelta(days=days)).isoformat()


def _month_start() -> str:
	return date.today().replace(day=1).isoformat()


class DeskMixUser(HttpUser):
	abstract = True
	persona = ""
	wait_time = between(config.THINK_TIME_MIN, config.THINK_TIME_MAX)

	def on_start(self):
		pool = config.users_for_persona(self.persona)
		if not pool:
			raise RuntimeError(f"No users for persona={self.persona}. Seed loadtest users first.")
		self.creds = random.choice(pool)
		self.desk = FrappeDeskClient(self, self.creds)
		self.desk.login()
		self._cache: dict = {}

	def _company(self) -> dict:
		"""Pick a random PERF company for this transaction."""
		return config.random_company()

	def _list_and_open(self, doctype: str) -> str | None:
		rows = self.desk.list_docs(doctype, limit=20)
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
			self._cache["items"] = [r["name"] for r in self.desk.list_docs("Item", limit=50) if r.get("name")]
		return random.choice(self._cache["items"]) if self._cache["items"] else None

	def after_loop(self):
		self.desk.maybe_relogin(0.05)

	def _payment_against_invoice(self, invoice_doctype: str, invoice_name: str, company: dict):
		pe = self.desk.call_method(
			"erpnext.accounts.doctype.payment_entry.payment_entry.get_payment_entry",
			{"dt": invoice_doctype, "dn": invoice_name},
			name="flow:get_payment_entry",
		)
		if not pe:
			return
		pe["doctype"] = "Payment Entry"
		pe["company"] = company["name"]
		pe["posting_date"] = _today()
		if company.get("cash_account"):
			if pe.get("payment_type") == "Receive":
				pe["paid_to"] = company["cash_account"]
			elif pe.get("payment_type") == "Pay":
				pe["paid_from"] = company["cash_account"]
		pe = self.desk.savedocs(pe, "Save")
		if not pe or not pe.get("name"):
			return
		pe["doctype"] = "Payment Entry"
		self.desk.savedocs(pe, "Submit")


class SalesUser(DeskMixUser):
	"""Sales Order → Sales Invoice (update stock) → Payment Entry; random company each run."""

	persona = "sales"
	weight = 25

	@task(3)
	def full_sales_flow(self):
		self._run_sales_flow()
		self.after_loop()

	@task(1)
	def browse(self):
		self._list_and_open("Sales Order")
		self._list_and_open("Sales Invoice")
		self.after_loop()

	def _run_sales_flow(self):
		company = self._company()
		customer = self._random_customer()
		item = self._random_item()
		wh = company.get("warehouse")
		if not customer or not item or not wh:
			return

		qty = random.randint(1, 3)
		rate = random.choice([100, 150, 200])

		so = {
			"doctype": "Sales Order",
			"company": company["name"],
			"customer": customer,
			"transaction_date": _today(),
			"delivery_date": _future(7),
			"order_type": "Sales",
			"selling_price_list": config.SEED["selling_price_list"],
			"set_warehouse": wh,
			"ignore_pricing_rule": 1,
			"items": [
				{
					"doctype": "Sales Order Item",
					"item_code": item,
					"qty": qty,
					"rate": rate,
					"delivery_date": _future(7),
					"warehouse": wh,
				}
			],
		}
		so = self.desk.savedocs(so, "Save")
		if not so or not so.get("name"):
			return
		so["doctype"] = "Sales Order"
		so = self.desk.savedocs(so, "Submit")
		if not so or not so.get("name"):
			return

		# SO → Sales Invoice
		si = self.desk.call_method(
			"erpnext.selling.doctype.sales_order.sales_order.make_sales_invoice",
			{"source_name": so["name"]},
			name="flow:make_sales_invoice",
		)
		if not si:
			return
		si["doctype"] = "Sales Invoice"
		si["update_stock"] = 1
		si["posting_date"] = _today()
		si["set_warehouse"] = wh
		si["company"] = company["name"]
		si = self.desk.savedocs(si, "Save")
		if not si or not si.get("name"):
			return
		si["doctype"] = "Sales Invoice"
		si = self.desk.savedocs(si, "Submit")
		if not si or not si.get("name"):
			return

		self._payment_against_invoice("Sales Invoice", si["name"], company)


class PurchaseUser(DeskMixUser):
	"""Purchase Order → Purchase Receipt → Purchase Invoice → Payment; random company."""

	persona = "purchase"
	weight = 15

	@task(3)
	def full_purchase_flow(self):
		self._run_purchase_flow()
		self.after_loop()

	@task(1)
	def browse(self):
		self._list_and_open("Purchase Order")
		self._list_and_open("Purchase Invoice")
		self.after_loop()

	def _run_purchase_flow(self):
		company = self._company()
		supplier = self._random_supplier()
		item = self._random_item()
		wh = company.get("warehouse")
		if not supplier or not item or not wh:
			return

		qty = random.randint(1, 5)
		rate = random.choice([50, 80, 120])

		po = {
			"doctype": "Purchase Order",
			"company": company["name"],
			"supplier": supplier,
			"transaction_date": _today(),
			"schedule_date": _future(7),
			"buying_price_list": config.SEED["buying_price_list"],
			"set_warehouse": wh,
			"ignore_pricing_rule": 1,
			"items": [
				{
					"doctype": "Purchase Order Item",
					"item_code": item,
					"qty": qty,
					"rate": rate,
					"schedule_date": _future(7),
					"warehouse": wh,
				}
			],
		}
		po = self.desk.savedocs(po, "Save")
		if not po or not po.get("name"):
			return
		po["doctype"] = "Purchase Order"
		po = self.desk.savedocs(po, "Submit")
		if not po or not po.get("name"):
			return

		pr = self.desk.call_method(
			"erpnext.buying.doctype.purchase_order.purchase_order.make_purchase_receipt",
			{"source_name": po["name"]},
			name="flow:make_purchase_receipt",
		)
		if not pr:
			return
		pr["doctype"] = "Purchase Receipt"
		pr["company"] = company["name"]
		pr["posting_date"] = _today()
		pr = self.desk.savedocs(pr, "Save")
		if not pr or not pr.get("name"):
			return
		pr["doctype"] = "Purchase Receipt"
		pr = self.desk.savedocs(pr, "Submit")
		if not pr or not pr.get("name"):
			return

		pi = self.desk.call_method(
			"erpnext.stock.doctype.purchase_receipt.purchase_receipt.make_purchase_invoice",
			{"source_name": pr["name"]},
			name="flow:make_purchase_invoice",
		)
		if not pi:
			return
		pi["doctype"] = "Purchase Invoice"
		pi["company"] = company["name"]
		pi["posting_date"] = _today()
		pi = self.desk.savedocs(pi, "Save")
		if not pi or not pi.get("name"):
			return
		pi["doctype"] = "Purchase Invoice"
		pi = self.desk.savedocs(pi, "Submit")
		if not pi or not pi.get("name"):
			return

		self._payment_against_invoice("Purchase Invoice", pi["name"], company)


class StockUser(DeskMixUser):
	persona = "stock"
	weight = 15

	@task
	def loop(self):
		company = self._company()
		roll = random.random()
		self._list_and_open("Stock Entry")
		if roll < 0.40:
			self._create_material_receipt(company, submit=True)
		elif roll < 0.70:
			self.desk.run_report(
				"Stock Balance",
				{"company": company["name"], "warehouse": company.get("warehouse")},
			)
		else:
			self.desk.run_report(
				"Stock Ledger",
				{
					"company": company["name"],
					"from_date": _today(),
					"to_date": _today(),
					"warehouse": company.get("warehouse"),
				},
			)
		self.after_loop()

	def _create_material_receipt(self, company: dict, submit: bool = False):
		item = self._random_item()
		wh = company.get("warehouse")
		if not item or not wh:
			return
		doc = {
			"doctype": "Stock Entry",
			"company": company["name"],
			"stock_entry_type": "Material Receipt",
			"purpose": "Material Receipt",
			"to_warehouse": wh,
			"items": [
				{
					"doctype": "Stock Entry Detail",
					"item_code": item,
					"qty": random.randint(1, 10),
					"t_warehouse": wh,
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
		company = self._company()
		roll = random.random()
		if roll < 0.35:
			self._list_and_open("Payment Entry")
			self._create_journal_entry(company, submit=random.random() < 0.3)
		elif roll < 0.60:
			self._create_journal_entry(company, submit=True)
		else:
			self.desk.run_report(
				"General Ledger",
				{
					"company": company["name"],
					"from_date": _month_start(),
					"to_date": _today(),
				},
			)
			if random.random() < 0.5:
				self._list_and_open("Sales Invoice")
			else:
				self._list_and_open("Purchase Invoice")
		self.after_loop()

	def _create_journal_entry(self, company: dict, submit: bool = False):
		cash = company.get("cash_account")
		if not cash:
			return
		doc = {
			"doctype": "Journal Entry",
			"company": company["name"],
			"posting_date": _today(),
			"voucher_type": "Journal Entry",
			"accounts": [
				{
					"doctype": "Journal Entry Account",
					"account": cash,
					"debit_in_account_currency": 1,
					"credit_in_account_currency": 0,
					"cost_center": company.get("cost_center"),
				},
				{
					"doctype": "Journal Entry Account",
					"account": cash,
					"debit_in_account_currency": 0,
					"credit_in_account_currency": 1,
					"cost_center": company.get("cost_center"),
				},
			],
			"user_remark": "perf loadtest",
		}
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
		self.after_loop()


class ReportUser(DeskMixUser):
	persona = "report"
	weight = 15

	@task
	def loop(self):
		company = self._company()
		start = _month_start()
		today = _today()
		cname = company["name"]
		report = random.choice(
			[
				(
					"Profit and Loss Statement",
					{
						"company": cname,
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
						"company": cname,
						"fiscal_year": config.FISCAL_YEAR,
						"from_date": start,
						"to_date": today,
					},
				),
				("Stock Balance", {"company": cname}),
				(
					"Sales Register",
					{"from_date": start, "to_date": today, "company": cname},
				),
			]
		)
		self.desk.run_report(report[0], report[1])
		self.desk.desk_ping()
		self.after_loop()
