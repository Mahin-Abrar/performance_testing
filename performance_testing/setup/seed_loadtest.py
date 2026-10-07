"""Seed companies + masters + users + optional random transactions for Locust.

Run:
  bench --site performance execute performance_testing.setup.seed_loadtest.seed
  bench --site performance execute performance_testing.setup.seed_loadtest.seed_transactions \\
    --kwargs '{"count": 5000}'

Writes:
  apps/performance_testing/loadtest/users.json
  apps/performance_testing/loadtest/companies.json
"""

from __future__ import annotations

import json
import random
from datetime import date, timedelta
from pathlib import Path

import frappe
from frappe.utils import now_datetime
from frappe.utils.password import update_password

PASSWORD = "PerfTest@123"
COMPANY_COUNT = 30
TEMPLATE_COMPANY = "Fusion"  # used for CoA / country / currency if present

ITEM_COUNT = 20_000
CUSTOMER_COUNT = 2_000
SUPPLIER_COUNT = 1_000
# Finished goods PERF-FG-0001… with one active BOM per company; raw materials come
# from the opening-stock items so manufacture/purchase flows hit stocked SKUs.
FG_ITEM_COUNT = 100
# Opening stock for this many items per company (full 20k×30 Material Receipts is too heavy)
OPENING_STOCK_ITEM_COUNT = 1_000
OPENING_STOCK_QTY = 10_000
ITEM_BATCH = 500
DEFAULT_TRANSACTION_COUNT = 3_000
# Keep in sync with loadtest/config.py DATE_FROM
LOADTEST_DATE_FROM = date(2026, 1, 1)

PERSONA_COUNTS = {
	"sales": 25,
	"purchase": 15,
	"stock": 15,
	"accounts": 20,
	"mfg": 10,
	"report": 15,
}

PERSONA_ROLES = {
	# Manufacturing User = BOM read access for FG sales / BOM raw-material purchases
	"sales": ["Sales User", "Stock User", "Accounts User", "Manufacturing User"],
	"purchase": ["Purchase User", "Stock User", "Accounts User", "Manufacturing User"],
	"stock": ["Stock User", "Stock Manager"],
	"accounts": ["Accounts User", "Accounts Manager"],
	"mfg": ["Manufacturing User", "Stock User"],
	"report": ["Accounts Manager", "Sales Manager", "Purchase Manager", "Stock Manager"],
}

TX_TYPES = (
	"quotation",
	"sales_order",
	"delivery_note",
	"sales_invoice",
	"material_request",
	"purchase_order",
	"purchase_receipt",
	"purchase_invoice",
	"stock_receipt",
	"stock_issue",
	"manufacture",
	"journal_entry",
)
SALES_TX = {"quotation", "sales_order", "delivery_note", "sales_invoice"}


def _app_root() -> Path:
	return Path(frappe.get_app_path("performance_testing")).parent


def _users_json_path() -> Path:
	return _app_root() / "loadtest" / "users.json"


def _companies_json_path() -> Path:
	return _app_root() / "loadtest" / "companies.json"


def seed():
	"""Create 30 companies, 20k items, masters, stock sample, 100 Locust users."""
	frappe.flags.in_import = True
	frappe.flags.mute_emails = True

	companies = _ensure_companies()
	_ensure_shared_masters()
	_bulk_ensure_items()
	_allow_negative_stock()
	ensure_fiscal_years()
	_ensure_opening_stock(companies)
	_ensure_boms(companies)
	users = _ensure_users(companies)
	_write_json(_users_json_path(), users)
	_write_json(_companies_json_path(), companies)
	frappe.db.commit()

	item_n = frappe.db.count("Item", {"item_code": ("like", "PERF-ITEM-%")})
	bom_n = frappe.db.count("BOM", {"item": ("like", "PERF-FG-%"), "docstatus": 1})
	print(f"Seeded {len(companies)} companies → {_companies_json_path()}")
	print(f"PERF items on site: {item_n}, FG BOMs: {bom_n}")
	print(f"Seeded {len(users)} users → {_users_json_path()}")
	print(f"password={PASSWORD}")
	print(
		"Next: bench --site performance execute "
		"performance_testing.setup.seed_loadtest.seed_transactions "
		'--kwargs \'{"count": 5000}\''
	)
	return {
		"companies": len(companies),
		"items": item_n,
		"boms": bom_n,
		"users": len(users),
		"companies_file": str(_companies_json_path()),
		"users_file": str(_users_json_path()),
	}


def seed_transactions(count: int = DEFAULT_TRANSACTION_COUNT):
	"""Create random submitted transactions across PERF companies and items."""
	frappe.flags.mute_emails = True
	_allow_negative_stock()
	ensure_fiscal_years()
	_ensure_item_uoms()

	companies = _load_or_ensure_companies()
	customers = frappe.get_all("Customer", filters={"name": ("like", "PERF-CUST-%")}, pluck="name")
	suppliers = frappe.get_all("Supplier", filters={"name": ("like", "PERF-SUPP-%")}, pluck="name")
	# Sample items for speed; still draws from the 20k PERF catalog
	items = frappe.db.sql_list(
		"""
		select name from `tabItem`
		where item_code like 'PERF-ITEM-%%'
		order by rand()
		limit 5000
		"""
	)

	if not companies:
		frappe.throw("No PERF companies. Run seed() first.")
	if not items:
		frappe.throw("No PERF items. Run seed() first.")
	if not customers or not suppliers:
		frappe.throw("Missing PERF customers/suppliers. Run seed() first.")
	boms: dict[str, list[dict]] = {}
	for b in frappe.get_all(
		"BOM",
		filters={"item": ("like", "PERF-FG-%"), "docstatus": 1, "is_active": 1},
		fields=["name", "item", "company"],
	):
		boms.setdefault(b.company, []).append(b)

	count = int(count)
	ok = 0
	fail = 0
	by_type: dict[str, int] = {t: 0 for t in TX_TYPES}
	sample_errors: list[str] = []

	for i in range(count):
		tx = random.choice(TX_TYPES)
		company = random.choice(companies)
		company_boms = boms.get(company["name"]) or []
		bom = random.choice(company_boms) if company_boms else None
		item = random.choice(items)
		if tx in SALES_TX and bom and random.random() < 0.5:
			item = bom.item
		try:
			_create_transaction(
				tx,
				company=company,
				customer=random.choice(customers),
				supplier=random.choice(suppliers),
				item=item,
				bom=bom,
			)
			ok += 1
			by_type[tx] += 1
		except Exception as e:
			fail += 1
			if len(sample_errors) < 10:
				sample_errors.append(f"{tx} @ {company.get('name')}: {e}")

		if (i + 1) % 50 == 0:
			frappe.db.commit()
			frappe.clear_messages()
			print(f"transactions: {i + 1}/{count} ok={ok} fail={fail}", flush=True)

	frappe.db.commit()
	print(f"Done: ok={ok} fail={fail} by_type={by_type}", flush=True)
	for err in sample_errors:
		print(f"  sample error: {err}", flush=True)
	return {"ok": ok, "fail": fail, "by_type": by_type, "sample_errors": sample_errors}


def _write_json(path: Path, data):
	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_text(json.dumps(data, indent=2))


def _template_company() -> str:
	if frappe.db.exists("Company", TEMPLATE_COMPANY):
		return TEMPLATE_COMPANY
	name = frappe.db.get_value("Company", {}, "name")
	if not name:
		frappe.throw("No Company found to use as chart-of-accounts template")
	return name


def _company_row(name: str, abbr: str) -> dict:
	warehouse = frappe.db.get_value(
		"Warehouse", {"company": name, "warehouse_name": "Stores"}, "name"
	) or frappe.db.get_value("Warehouse", {"company": name, "is_group": 0}, "name")
	cash = frappe.db.get_value(
		"Account", {"company": name, "account_type": "Cash", "is_group": 0}, "name"
	) or frappe.db.get_value(
		"Account", {"company": name, "account_type": "Bank", "is_group": 0}, "name"
	)
	expense = frappe.db.get_value(
		"Account",
		{"company": name, "root_type": "Expense", "is_group": 0},
		"name",
	)
	income = frappe.db.get_value(
		"Account",
		{"company": name, "root_type": "Income", "is_group": 0},
		"name",
	)
	cost_center = frappe.db.get_value("Cost Center", {"company": name, "is_group": 0}, "name")
	return {
		"name": name,
		"abbr": abbr,
		"warehouse": warehouse,
		"cash_account": cash,
		"expense_account": expense,
		"income_account": income,
		"cost_center": cost_center,
	}


def _ensure_companies() -> list[dict]:
	template = _template_company()
	tmpl = frappe.get_doc("Company", template)
	companies: list[dict] = []

	for i in range(1, COMPANY_COUNT + 1):
		name = f"PERF Company {i:02d}"
		abbr = f"PC{i:02d}"
		if not frappe.db.exists("Company", name):
			doc = frappe.get_doc(
				{
					"doctype": "Company",
					"company_name": name,
					"abbr": abbr,
					"default_currency": tmpl.default_currency,
					"country": tmpl.country,
					"valuation_method": tmpl.valuation_method or "FIFO",
					"create_chart_of_accounts_based_on": "Existing Company",
					"existing_company": template,
				}
			)
			doc.insert(ignore_permissions=True)
			frappe.db.commit()

		companies.append(_company_row(name, abbr))
	return companies


def _load_or_ensure_companies() -> list[dict]:
	path = _companies_json_path()
	if path.exists():
		data = json.loads(path.read_text())
		if len(data) >= COMPANY_COUNT:
			return data
	return _ensure_companies()


def _ensure_shared_masters():
	if not frappe.db.exists("UOM", "Nos"):
		frappe.get_doc({"doctype": "UOM", "uom_name": "Nos"}).insert(ignore_permissions=True)

	for i in range(1, CUSTOMER_COUNT + 1):
		name = f"PERF-CUST-{i:03d}"
		if not frappe.db.exists("Customer", name):
			frappe.get_doc(
				{
					"doctype": "Customer",
					"customer_name": name,
					"customer_type": "Company",
					"customer_group": "Commercial",
					"territory": "All Territories",
				}
			).insert(ignore_permissions=True)

	for i in range(1, SUPPLIER_COUNT + 1):
		name = f"PERF-SUPP-{i:03d}"
		if not frappe.db.exists("Supplier", name):
			frappe.get_doc(
				{
					"doctype": "Supplier",
					"supplier_name": name,
					"supplier_group": "Local",
					"supplier_type": "Company",
				}
			).insert(ignore_permissions=True)

	frappe.db.commit()


def _bulk_ensure_items():
	"""Create PERF-ITEM-00001 … PERF-ITEM-20000 via bulk_insert (skips existing)."""
	existing = set(
		frappe.get_all("Item", filters={"item_code": ("like", "PERF-ITEM-%")}, pluck="name")
	)
	missing = [
		i for i in range(1, ITEM_COUNT + 1) if f"PERF-ITEM-{i:05d}" not in existing
	]
	if missing:
		now = now_datetime()
		fields = [
			"name",
			"item_code",
			"item_name",
			"item_group",
			"stock_uom",
			"is_stock_item",
			"is_sales_item",
			"is_purchase_item",
			"include_item_in_manufacturing",
			"disabled",
			"has_variants",
			"is_fixed_asset",
			"docstatus",
			"idx",
			"creation",
			"modified",
			"owner",
			"modified_by",
		]

		print(f"Bulk inserting {len(missing)} items…", flush=True)
		for start in range(0, len(missing), ITEM_BATCH):
			chunk = missing[start : start + ITEM_BATCH]
			rows = []
			for i in chunk:
				code = f"PERF-ITEM-{i:05d}"
				rows.append(
					(
						code,
						code,
						code,
						"Products",
						"Nos",
						1,
						1,
						1,
						1,
						0,
						0,
						0,
						0,
						0,
						now,
						now,
						"Administrator",
						"Administrator",
					)
				)
			frappe.db.bulk_insert("Item", fields=fields, values=rows)
			frappe.db.commit()
			print(f"  items {start + len(chunk)}/{len(missing)}", flush=True)
	else:
		print(f"Items already present: {ITEM_COUNT}", flush=True)

	_ensure_item_uoms()
	frappe.clear_cache(doctype="Item")


def _ensure_item_uoms():
	"""Bulk-inserted items need a Nos conversion row or sales/purchase validate fails."""
	missing = frappe.db.sql_list(
		"""
		select i.name
		from `tabItem` i
		left join `tabUOM Conversion Detail` u
			on u.parent = i.name and u.uom = 'Nos'
		where i.item_code like 'PERF-ITEM-%%'
			and u.name is null
		"""
	)
	if not missing:
		return

	print(f"Adding UOM conversions for {len(missing)} items…", flush=True)
	now = now_datetime()
	fields = [
		"name",
		"parent",
		"parenttype",
		"parentfield",
		"uom",
		"conversion_factor",
		"docstatus",
		"idx",
		"creation",
		"modified",
		"owner",
		"modified_by",
	]
	for start in range(0, len(missing), ITEM_BATCH):
		chunk = missing[start : start + ITEM_BATCH]
		rows = [
			(
				frappe.generate_hash(length=10),
				code,
				"Item",
				"uoms",
				"Nos",
				1.0,
				0,
				1,
				now,
				now,
				"Administrator",
				"Administrator",
			)
			for code in chunk
		]
		frappe.db.bulk_insert("UOM Conversion Detail", fields=fields, values=rows)
		frappe.db.commit()
		print(f"  uoms {start + len(chunk)}/{len(missing)}", flush=True)


def _allow_negative_stock():
	"""Avoid stock blocks while seeding random SI/SE across 20k SKUs."""
	if frappe.db.exists("Stock Settings"):
		frappe.db.set_single_value("Stock Settings", "allow_negative_stock", 1)


def _ensure_opening_stock(companies: list[dict]):
	"""Material Receipt for first N PERF items per company (batched)."""
	items = [
		f"PERF-ITEM-{i:05d}"
		for i in range(1, OPENING_STOCK_ITEM_COUNT + 1)
		if frappe.db.exists("Item", f"PERF-ITEM-{i:05d}")
	]
	legacy = frappe.get_all(
		"Item", filters={"item_code": ("like", "PERF-ITEM-___")}, pluck="name"
	)
	for code in legacy:
		if code not in items:
			items.append(code)

	for company in companies:
		wh = company.get("warehouse")
		if not wh:
			continue
		marker = frappe.db.exists(
			"Stock Entry",
			{
				"company": company["name"],
				"stock_entry_type": "Material Receipt",
				"docstatus": 1,
				"remarks": "PERF opening stock",
			},
		)
		if marker:
			continue

		print(f"Opening stock → {company['name']} ({len(items)} items)", flush=True)
		for start in range(0, len(items), 100):
			chunk = items[start : start + 100]
			doc = frappe.get_doc(
				{
					"doctype": "Stock Entry",
					"company": company["name"],
					"stock_entry_type": "Material Receipt",
					"purpose": "Material Receipt",
					"to_warehouse": wh,
					"remarks": "PERF opening stock",
					"items": [
						{
							"item_code": item,
							"qty": OPENING_STOCK_QTY,
							"t_warehouse": wh,
							"basic_rate": 50,
							"allow_zero_valuation_rate": 1,
						}
						for item in chunk
					],
				}
			)
			doc.insert(ignore_permissions=True)
			doc.submit()
			frappe.db.commit()


def _ensure_boms(companies: list[dict]):
	"""PERF-FG-* items with a submitted BOM (3–5 raw items) in every company.

	ERPNext keeps one default BOM per item across companies, so lookups use is_active.
	"""
	# in_import skips field defaults (e.g. BOM cost_allocation_per=100) and BOM validation fails
	frappe.flags.in_import = False
	raw = [f"PERF-ITEM-{i:05d}" for i in range(1, OPENING_STOCK_ITEM_COUNT + 1)]
	has_bom = {
		(r.item, r.company)
		for r in frappe.get_all(
			"BOM", filters={"item": ("like", "PERF-FG-%"), "docstatus": 1}, fields=["item", "company"]
		)
	}
	for i in range(1, FG_ITEM_COUNT + 1):
		fg = f"PERF-FG-{i:04d}"
		if not frappe.db.exists("Item", fg):
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": fg,
					"item_name": fg,
					"item_group": "Products",
					"stock_uom": "Nos",
					"is_stock_item": 1,
					"include_item_in_manufacturing": 1,
					"standard_rate": 500,
				}
			).insert(ignore_permissions=True)
		# Same recipe in every company
		rng = random.Random(i)
		components = [(code, rng.randint(1, 4)) for code in rng.sample(raw, rng.randint(3, 5))]
		for company in companies:
			if (fg, company["name"]) in has_bom:
				continue
			bom = frappe.get_doc(
				{
					"doctype": "BOM",
					"item": fg,
					"company": company["name"],
					"quantity": 1,
					"is_active": 1,
					"is_default": 1,
					"rm_cost_as_per": "Valuation Rate",
					"items": [
						{
							"item_code": code,
							"qty": qty,
							"source_warehouse": company.get("warehouse"),
						}
						for code, qty in components
					],
				}
			)
			bom.insert(ignore_permissions=True)
			bom.submit()
		frappe.db.commit()
		print(f"  BOMs for {fg} ({i}/{FG_ITEM_COUNT})", flush=True)


def _ensure_role(role: str):
	if not frappe.db.exists("Role", role):
		frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(
			ignore_permissions=True
		)


def _ensure_users(companies: list[dict]) -> list[dict]:
	out: list[dict] = []
	company_names = [c["name"] for c in companies]
	for persona, count in PERSONA_COUNTS.items():
		for i in range(1, count + 1):
			email = f"perf_{persona}_{i:02d}@example.com"
			roles = PERSONA_ROLES[persona]
			for role in roles:
				_ensure_role(role)

			if frappe.db.exists("User", email):
				user = frappe.get_doc("User", email)
			else:
				user = frappe.get_doc(
					{
						"doctype": "User",
						"email": email,
						"first_name": f"Perf {persona} {i:02d}",
						"send_welcome_email": 0,
						"user_type": "System User",
						"enabled": 1,
					}
				)
				user.insert(ignore_permissions=True)
				update_password(user=email, pwd=PASSWORD, logout_all_sessions=False)

			user.enabled = 1
			existing = {r.role for r in user.roles}
			for role in [*roles, "Desk User"]:
				if role not in existing and frappe.db.exists("Role", role):
					user.append("roles", {"role": role})

			api_key = user.api_key or frappe.generate_hash(length=15)
			api_secret = frappe.generate_hash(length=15)
			user.api_key = api_key
			user.api_secret = api_secret
			user.save(ignore_permissions=True)

			default_company = company_names[(i - 1) % len(company_names)]
			frappe.defaults.set_user_default("company", default_company, email)
			frappe.db.delete("User Permission", {"user": email, "allow": "Company"})

			out.append(
				{
					"email": email,
					"password": PASSWORD,
					"persona": persona,
					"api_key": api_key,
					"api_secret": api_secret,
					"default_company": default_company,
				}
			)
	return out


def _fiscal_year_for(d: date) -> str | None:
	"""Fiscal year containing `d`, created from an existing year's start month if missing."""
	fy_name = frappe.db.get_value(
		"Fiscal Year",
		{"disabled": 0, "year_start_date": ("<=", d), "year_end_date": (">=", d)},
		"name",
	)
	if fy_name:
		return fy_name
	start = frappe.db.get_value("Fiscal Year", {"disabled": 0}, "year_start_date")
	if not start:
		return None
	start = start.replace(year=d.year)
	if start > d:
		start = start.replace(year=d.year - 1)
	end = start.replace(year=start.year + 1) - timedelta(days=1)
	year = str(start.year) if start.year == end.year else f"{start.year}-{end.year}"
	return frappe.get_doc(
		{"doctype": "Fiscal Year", "year": year, "year_start_date": start, "year_end_date": end}
	).insert(ignore_permissions=True).name


def ensure_fiscal_years():
	"""Fiscal years covering LOADTEST_DATE_FROM..today, linked to all PERF companies."""
	for d in (LOADTEST_DATE_FROM, date.today()):
		_ensure_fiscal_year_for_companies(d)


def _ensure_fiscal_year_for_companies(d: date | None = None):
	"""Link all PERF companies to the fiscal year containing `d` (default today)."""
	fy_name = _fiscal_year_for(d or date.today())
	if not fy_name:
		return
	fy = frappe.get_doc("Fiscal Year", fy_name)
	existing = {row.company for row in fy.companies}
	changed = False
	for i in range(1, COMPANY_COUNT + 1):
		name = f"PERF Company {i:02d}"
		if frappe.db.exists("Company", name) and name not in existing:
			fy.append("companies", {"company": name})
			changed = True
	if changed:
		fy.flags.ignore_links = True
		fy.save(ignore_permissions=True)
		frappe.db.commit()


def _random_posting_date() -> str:
	"""Date between LOADTEST_DATE_FROM and today."""
	span = (date.today() - LOADTEST_DATE_FROM).days
	return (LOADTEST_DATE_FROM + timedelta(days=random.randint(0, max(span, 0)))).isoformat()


def _create_transaction(
	tx: str,
	*,
	company: dict,
	customer: str,
	supplier: str,
	item: str,
	bom: dict | None = None,
):
	qty = random.randint(1, 10)
	rate = round(random.uniform(10, 500), 2)
	posting = _random_posting_date()
	wh = company.get("warehouse")
	posting_time = f"{random.randint(8, 17):02d}:{random.randint(0, 59):02d}:00"

	if tx == "sales_order":
		doc = frappe.get_doc(
			{
				"doctype": "Sales Order",
				"company": company["name"],
				"customer": customer,
				"transaction_date": posting,
				"delivery_date": posting,
				"order_type": "Sales",
				"selling_price_list": "Standard Selling",
				"items": [{"item_code": item, "qty": qty, "rate": rate, "warehouse": wh}],
			}
		)
		doc.insert(ignore_permissions=True)
		doc.reload()
		doc.submit()
		return

	if tx == "sales_invoice":
		doc = frappe.get_doc(
			{
				"doctype": "Sales Invoice",
				"company": company["name"],
				"customer": customer,
				"posting_date": posting,
				"posting_time": posting_time,
				"due_date": posting,
				"set_posting_time": 1,
				"update_stock": 1 if wh else 0,
				"selling_price_list": "Standard Selling",
				"items": [
					{
						"item_code": item,
						"qty": qty,
						"rate": rate,
						"warehouse": wh,
						"income_account": company.get("income_account"),
						"cost_center": company.get("cost_center"),
					}
				],
			}
		)
		doc.insert(ignore_permissions=True)
		doc.submit()
		return

	if tx == "purchase_order":
		doc = frappe.get_doc(
			{
				"doctype": "Purchase Order",
				"company": company["name"],
				"supplier": supplier,
				"transaction_date": posting,
				"schedule_date": posting,
				"buying_price_list": "Standard Buying",
				"items": [{"item_code": item, "qty": qty, "rate": rate, "warehouse": wh}],
			}
		)
		doc.insert(ignore_permissions=True)
		doc.reload()
		doc.submit()
		return

	if tx == "purchase_invoice":
		doc = frappe.get_doc(
			{
				"doctype": "Purchase Invoice",
				"company": company["name"],
				"supplier": supplier,
				"posting_date": posting,
				"posting_time": posting_time,
				"due_date": posting,
				"set_posting_time": 1,
				"update_stock": 1 if wh else 0,
				"buying_price_list": "Standard Buying",
				"items": [
					{
						"item_code": item,
						"qty": qty,
						"rate": rate,
						"warehouse": wh,
						"expense_account": company.get("expense_account"),
						"cost_center": company.get("cost_center"),
					}
				],
			}
		)
		doc.insert(ignore_permissions=True)
		doc.submit()
		return

	if tx == "stock_receipt":
		doc = frappe.get_doc(
			{
				"doctype": "Stock Entry",
				"company": company["name"],
				"stock_entry_type": "Material Receipt",
				"purpose": "Material Receipt",
				"posting_date": posting,
				"posting_time": posting_time,
				"set_posting_time": 1,
				"to_warehouse": wh,
				"items": [
					{
						"item_code": item,
						"qty": qty,
						"t_warehouse": wh,
						"basic_rate": rate,
						"allow_zero_valuation_rate": 1,
					}
				],
			}
		)
		doc.insert(ignore_permissions=True)
		doc.submit()
		return

	if tx == "stock_issue":
		doc = frappe.get_doc(
			{
				"doctype": "Stock Entry",
				"company": company["name"],
				"stock_entry_type": "Material Issue",
				"purpose": "Material Issue",
				"posting_date": posting,
				"posting_time": posting_time,
				"set_posting_time": 1,
				"from_warehouse": wh,
				"items": [
					{
						"item_code": item,
						"qty": qty,
						"s_warehouse": wh,
						"basic_rate": rate,
						"allow_zero_valuation_rate": 1,
					}
				],
			}
		)
		doc.insert(ignore_permissions=True)
		doc.submit()
		return

	if tx == "journal_entry":
		cash = company.get("cash_account")
		expense = company.get("expense_account")
		cc = company.get("cost_center")
		if not cash or not expense:
			raise frappe.ValidationError("Missing cash/expense account")
		amount = round(random.uniform(50, 5000), 2)
		doc = frappe.get_doc(
			{
				"doctype": "Journal Entry",
				"company": company["name"],
				"posting_date": posting,
				"voucher_type": "Journal Entry",
				"user_remark": "PERF seed",
				"accounts": [
					{
						"account": expense,
						"debit_in_account_currency": amount,
						"cost_center": cc,
					},
					{
						"account": cash,
						"credit_in_account_currency": amount,
						"cost_center": cc,
					},
				],
			}
		)
		doc.insert(ignore_permissions=True)
		doc.submit()
		return

	if tx == "quotation":
		doc = frappe.get_doc(
			{
				"doctype": "Quotation",
				"company": company["name"],
				"quotation_to": "Customer",
				"party_name": customer,
				"transaction_date": posting,
				"valid_till": (date.fromisoformat(posting) + timedelta(days=30)).isoformat(),
				"selling_price_list": "Standard Selling",
				"items": [{"item_code": item, "qty": qty, "rate": rate, "warehouse": wh}],
			}
		)
		doc.insert(ignore_permissions=True)
		doc.submit()
		return

	if tx == "delivery_note":
		doc = frappe.get_doc(
			{
				"doctype": "Delivery Note",
				"company": company["name"],
				"customer": customer,
				"posting_date": posting,
				"posting_time": posting_time,
				"set_posting_time": 1,
				"selling_price_list": "Standard Selling",
				"items": [{"item_code": item, "qty": qty, "rate": rate, "warehouse": wh}],
			}
		)
		doc.insert(ignore_permissions=True)
		doc.submit()
		return

	if tx == "material_request":
		doc = frappe.get_doc(
			{
				"doctype": "Material Request",
				"company": company["name"],
				"material_request_type": "Purchase",
				"transaction_date": posting,
				"schedule_date": posting,
				"items": [
					{"item_code": item, "qty": qty, "schedule_date": posting, "warehouse": wh}
				],
			}
		)
		doc.insert(ignore_permissions=True)
		doc.submit()
		return

	if tx == "purchase_receipt":
		doc = frappe.get_doc(
			{
				"doctype": "Purchase Receipt",
				"company": company["name"],
				"supplier": supplier,
				"posting_date": posting,
				"posting_time": posting_time,
				"set_posting_time": 1,
				"buying_price_list": "Standard Buying",
				"items": [{"item_code": item, "qty": qty, "rate": rate, "warehouse": wh}],
			}
		)
		doc.insert(ignore_permissions=True)
		doc.submit()
		return

	if tx == "manufacture":
		from erpnext.manufacturing.doctype.work_order.work_order import make_stock_entry

		if not bom:
			raise frappe.ValidationError("No PERF BOM for company")
		wo = frappe.get_doc(
			{
				"doctype": "Work Order",
				"company": company["name"],
				"production_item": bom.item,
				"bom_no": bom.name,
				"qty": qty,
				"skip_transfer": 1,
				"source_warehouse": wh,
				"wip_warehouse": wh,
				"fg_warehouse": wh,
				"planned_start_date": f"{posting} {posting_time}",
			}
		)
		wo.insert(ignore_permissions=True)
		wo.submit()
		se = frappe.get_doc(make_stock_entry(wo.name, "Manufacture", qty))
		se.update({"posting_date": posting, "posting_time": posting_time, "set_posting_time": 1})
		se.insert(ignore_permissions=True)
		se.submit()
		return

	raise ValueError(f"Unknown tx type: {tx}")