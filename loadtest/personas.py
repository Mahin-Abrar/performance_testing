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


def _random_date() -> date:
	today = date.today()
	return config.DATE_FROM + timedelta(days=random.randint(0, max((today - config.DATE_FROM).days, 0)))


def _plus(d: date, days: int = 7) -> str:
	return (d + timedelta(days=days)).isoformat()


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

	def _random_bom(self, company: dict) -> dict | None:
		key = f"boms:{company['name']}"
		if key not in self._cache:
			self._cache[key] = self.desk.list_docs(
				"BOM",
				limit=200,
				filters=[
					["company", "=", company["name"]],
					["is_active", "=", 1],
					["docstatus", "=", 1],
				],
				fields=["name", "item"],
			)
		return random.choice(self._cache[key]) if self._cache[key] else None

	def _save_submit(self, doc: dict) -> dict | None:
		doctype = doc["doctype"]
		saved = self.desk.savedocs(doc, "Save")
		if not saved or not saved.get("name"):
			return None
		saved["doctype"] = doctype
		submitted = self.desk.savedocs(saved, "Submit")
		return submitted if submitted and submitted.get("name") else None

	def _map(self, method: str, source_name: str, doctype: str, **fields) -> dict | None:
		"""Run an ERPNext make_* mapper, apply overrides, then save + submit."""
		doc = self.desk.call_method(
			method, {"source_name": source_name}, name=f"flow:{method.rsplit('.', 1)[-1]}"
		)
		if not doc:
			return None
		doc.update(doctype=doctype, **fields)
		return self._save_submit(doc)

	def after_loop(self):
		self.desk.maybe_relogin(0.05)

	def _payment_against_invoice(self, invoice_doctype: str, invoice_name: str, company: dict, posting: str):
		pe = self.desk.call_method(
			"erpnext.accounts.doctype.payment_entry.payment_entry.get_payment_entry",
			{"dt": invoice_doctype, "dn": invoice_name},
			name="flow:get_payment_entry",
		)
		if not pe:
			return
		pe["doctype"] = "Payment Entry"
		pe["company"] = company["name"]
		pe["posting_date"] = posting
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
	"""[Quotation →] Sales Order → [Delivery Note →] Sales Invoice → Payment; FG items half the time."""

	persona = "sales"
	weight = 25

	@task(3)
	def full_sales_flow(self):
		self._run_sales_flow()
		self.after_loop()

	@task(1)
	def browse(self):
		self._list_and_open(random.choice(["Quotation", "Sales Order", "Delivery Note"]))
		self._list_and_open("Sales Invoice")
		self.after_loop()

	def _run_sales_flow(self):
		company = self._company()
		customer = self._random_customer()
		bom = self._random_bom(company)
		item = bom["item"] if bom and random.random() < 0.5 else self._random_item()
		wh = company.get("warehouse")
		if not customer or not item or not wh:
			return

		day = _random_date()
		posting = day.isoformat()
		delivery = _plus(day)
		row = {
			"item_code": item,
			"qty": random.randint(1, 3),
			"rate": random.choice([100, 150, 200]),
			"warehouse": wh,
		}
		base = {
			"company": company["name"],
			"selling_price_list": config.SEED["selling_price_list"],
			"ignore_pricing_rule": 1,
		}

		if random.random() < 0.3:
			# Quotation → Sales Order; ERPNext only converts quotations still valid today
			qtn = self._save_submit(
				{
					**base,
					"doctype": "Quotation",
					"quotation_to": "Customer",
					"party_name": customer,
					"transaction_date": posting,
					"valid_till": _plus(date.today(), 30),
					"items": [{**row, "doctype": "Quotation Item"}],
				}
			)
			if not qtn:
				return
			so = self.desk.call_method(
				"erpnext.selling.doctype.quotation.quotation.make_sales_order",
				{"source_name": qtn["name"]},
				name="flow:make_sales_order",
			)
			if not so:
				return
			so.update(doctype="Sales Order", transaction_date=posting, delivery_date=delivery, set_warehouse=wh)
			for r in so.get("items") or []:
				r.update(delivery_date=delivery, warehouse=wh)
		else:
			so = {
				**base,
				"doctype": "Sales Order",
				"customer": customer,
				"transaction_date": posting,
				"delivery_date": delivery,
				"order_type": "Sales",
				"set_warehouse": wh,
				"items": [{**row, "doctype": "Sales Order Item", "delivery_date": delivery}],
			}
		so = self._save_submit(so)
		if not so:
			return

		stock = {"company": company["name"], "set_posting_time": 1, "posting_date": posting}
		if random.random() < 0.4:
			dn = self._map(
				"erpnext.selling.doctype.sales_order.sales_order.make_delivery_note",
				so["name"],
				"Delivery Note",
				**stock,
			)
			if not dn:
				return
			si = self._map(
				"erpnext.stock.doctype.delivery_note.delivery_note.make_sales_invoice",
				dn["name"],
				"Sales Invoice",
				due_date=posting,
				**stock,
			)
		else:
			si = self._map(
				"erpnext.selling.doctype.sales_order.sales_order.make_sales_invoice",
				so["name"],
				"Sales Invoice",
				update_stock=1,
				set_warehouse=wh,
				due_date=posting,
				**stock,
			)
		if si:
			self._payment_against_invoice("Sales Invoice", si["name"], company, posting)


class PurchaseUser(DeskMixUser):
	"""[Material Request →] PO → Purchase Receipt → Purchase Invoice → Payment; BOM raw materials half the time."""

	persona = "purchase"
	weight = 15

	@task(3)
	def full_purchase_flow(self):
		self._run_purchase_flow()
		self.after_loop()

	@task(1)
	def browse(self):
		self._list_and_open(random.choice(["Material Request", "Purchase Order", "Purchase Receipt"]))
		self._list_and_open("Purchase Invoice")
		self.after_loop()

	def _run_purchase_flow(self):
		company = self._company()
		supplier = self._random_supplier()
		wh = company.get("warehouse")
		bom = self._random_bom(company) if random.random() < 0.5 else None
		if bom:
			# Buy all raw materials of a BOM
			bom_doc = self.desk.getdoc("BOM", bom["name"]) or {}
			lines = [(r["item_code"], r["qty"]) for r in bom_doc.get("items") or []]
		else:
			item = self._random_item()
			lines = [(item, 1)] if item else []
		if not supplier or not lines or not wh:
			return

		qty = random.randint(1, 5)
		day = _random_date()
		posting = day.isoformat()
		schedule = _plus(day)
		rows = [
			{
				"item_code": code,
				"qty": per_unit * qty,
				"rate": random.choice([50, 80, 120]),
				"schedule_date": schedule,
				"warehouse": wh,
			}
			for code, per_unit in lines
		]
		base = {
			"company": company["name"],
			"transaction_date": posting,
			"schedule_date": schedule,
			"set_warehouse": wh,
		}

		if random.random() < 0.4:
			mr = self._save_submit(
				{
					**base,
					"doctype": "Material Request",
					"material_request_type": "Purchase",
					"items": [{**r, "doctype": "Material Request Item"} for r in rows],
				}
			)
			if not mr:
				return
			po = self.desk.call_method(
				"erpnext.stock.doctype.material_request.material_request.make_purchase_order",
				{"source_name": mr["name"]},
				name="flow:make_purchase_order",
			)
			if not po:
				return
			rates = {r["item_code"]: r["rate"] for r in rows}
			po.update(
				doctype="Purchase Order",
				supplier=supplier,
				buying_price_list=config.SEED["buying_price_list"],
				ignore_pricing_rule=1,
				**base,
			)
			for r in po.get("items") or []:
				r["rate"] = rates.get(r.get("item_code"), 50)
		else:
			po = {
				**base,
				"doctype": "Purchase Order",
				"supplier": supplier,
				"buying_price_list": config.SEED["buying_price_list"],
				"ignore_pricing_rule": 1,
				"items": [{**r, "doctype": "Purchase Order Item"} for r in rows],
			}
		po = self._save_submit(po)
		if not po:
			return

		stock = {"company": company["name"], "set_posting_time": 1, "posting_date": posting}
		pr = self._map(
			"erpnext.buying.doctype.purchase_order.purchase_order.make_purchase_receipt",
			po["name"],
			"Purchase Receipt",
			**stock,
		)
		if not pr:
			return
		pi = self._map(
			"erpnext.stock.doctype.purchase_receipt.purchase_receipt.make_purchase_invoice",
			pr["name"],
			"Purchase Invoice",
			bill_date=posting,
			due_date=posting,
			**stock,
		)
		if pi:
			self._payment_against_invoice("Purchase Invoice", pi["name"], company, posting)


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
			"set_posting_time": 1,
			"posting_date": _random_date().isoformat(),
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
			"posting_date": _random_date().isoformat(),
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
		if roll < 0.50:
			self._run_manufacture(self._company())
		elif roll < 0.75:
			self._list_and_open("BOM")
		else:
			self._list_and_open("Job Card")
		self.after_loop()

	def _run_manufacture(self, company: dict):
		"""Work Order from a company BOM → Manufacture stock entry (raw materials backflushed)."""
		bom = self._random_bom(company)
		wh = company.get("warehouse")
		if not bom or not wh:
			return
		posting = _random_date().isoformat()
		qty = random.randint(1, 5)
		wo = self._save_submit(
			{
				"doctype": "Work Order",
				"company": company["name"],
				"production_item": bom["item"],
				"bom_no": bom["name"],
				"qty": qty,
				"skip_transfer": 1,
				"source_warehouse": wh,
				"wip_warehouse": wh,
				"fg_warehouse": wh,
				"planned_start_date": f"{posting} 09:00:00",
			}
		)
		if not wo:
			return
		se = self.desk.call_method(
			"erpnext.manufacturing.doctype.work_order.work_order.make_stock_entry",
			{"work_order_id": wo["name"], "purpose": "Manufacture", "qty": qty},
			name="flow:make_stock_entry",
		)
		if se:
			se.update(doctype="Stock Entry", set_posting_time=1, posting_date=posting)
			self._save_submit(se)


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
