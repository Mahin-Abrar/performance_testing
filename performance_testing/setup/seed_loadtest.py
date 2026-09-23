"""Seed 10 companies + masters + perf_* users for Locust multi-company desk mix.

Run:
  bench --site performance execute performance_testing.setup.seed_loadtest.seed

Writes:
  apps/performance_testing/loadtest/users.json
  apps/performance_testing/loadtest/companies.json
"""

from __future__ import annotations

import json
from pathlib import Path

import frappe
from frappe.utils.password import update_password

PASSWORD = "PerfTest@123"
COMPANY_COUNT = 10
TEMPLATE_COMPANY = "Fusion"  # used for CoA / country / currency if present

PERSONA_COUNTS = {
	"sales": 25,
	"purchase": 15,
	"stock": 15,
	"accounts": 20,
	"mfg": 10,
	"report": 15,
}

PERSONA_ROLES = {
	"sales": ["Sales User", "Stock User", "Accounts User"],
	"purchase": ["Purchase User", "Stock User", "Accounts User"],
	"stock": ["Stock User", "Stock Manager"],
	"accounts": ["Accounts User", "Accounts Manager"],
	"mfg": ["Manufacturing User", "Stock User"],
	"report": ["Accounts Manager", "Sales Manager", "Purchase Manager", "Stock Manager"],
}


def _app_root() -> Path:
	return Path(frappe.get_app_path("performance_testing")).parent


def _users_json_path() -> Path:
	return _app_root() / "loadtest" / "users.json"


def _companies_json_path() -> Path:
	return _app_root() / "loadtest" / "companies.json"


def seed():
	"""Create 10 companies, masters, stock, 100 Locust users; write JSON files."""
	frappe.flags.in_import = True
	companies = _ensure_companies()
	_ensure_shared_masters()
	_ensure_opening_stock(companies)
	users = _ensure_users(companies)
	_write_json(_users_json_path(), users)
	_write_json(_companies_json_path(), companies)
	frappe.db.commit()
	print(f"Seeded {len(companies)} companies → {_companies_json_path()}")
	print(f"Seeded {len(users)} users → {_users_json_path()}")
	print(f"password={PASSWORD}")
	return {
		"companies": len(companies),
		"users": len(users),
		"companies_file": str(_companies_json_path()),
		"users_file": str(_users_json_path()),
	}


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

		warehouse = (
			frappe.db.get_value("Warehouse", {"company": name, "warehouse_name": "Stores"}, "name")
			or frappe.db.get_value("Warehouse", {"company": name, "is_group": 0}, "name")
		)
		cash = frappe.db.get_value(
			"Account", {"company": name, "account_type": "Cash", "is_group": 0}, "name"
		) or frappe.db.get_value("Account", {"company": name, "account_type": "Bank", "is_group": 0}, "name")
		cost_center = frappe.db.get_value("Cost Center", {"company": name, "is_group": 0}, "name")

		companies.append(
			{
				"name": name,
				"abbr": abbr,
				"warehouse": warehouse,
				"cash_account": cash,
				"cost_center": cost_center,
			}
		)
	return companies


def _ensure_shared_masters():
	if not frappe.db.exists("UOM", "Nos"):
		frappe.get_doc({"doctype": "UOM", "uom_name": "Nos"}).insert(ignore_permissions=True)

	for i in range(1, 21):
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

	for i in range(1, 11):
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

	for i in range(1, 21):
		code = f"PERF-ITEM-{i:03d}"
		if not frappe.db.exists("Item", code):
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": code,
					"item_name": code,
					"item_group": "Products",
					"stock_uom": "Nos",
					"is_stock_item": 1,
					"include_item_in_manufacturing": 1,
					"is_purchase_item": 1,
					"is_sales_item": 1,
				}
			).insert(ignore_permissions=True)


def _ensure_opening_stock(companies: list[dict]):
	"""Put stock in each company warehouse so SO→SI with update_stock works."""
	items = frappe.get_all("Item", filters={"item_code": ("like", "PERF-ITEM-%")}, pluck="name")
	for company in companies:
		wh = company.get("warehouse")
		if not wh:
			continue
		# One receipt per company if none exists yet for PERF items
		exists = frappe.db.exists(
			"Stock Entry",
			{"company": company["name"], "stock_entry_type": "Material Receipt", "docstatus": 1},
		)
		if exists:
			continue
		doc = frappe.get_doc(
			{
				"doctype": "Stock Entry",
				"company": company["name"],
				"stock_entry_type": "Material Receipt",
				"purpose": "Material Receipt",
				"to_warehouse": wh,
				"items": [
					{
						"item_code": item,
						"qty": 500,
						"t_warehouse": wh,
						"basic_rate": 50,
						"allow_zero_valuation_rate": 1,
					}
					for item in items
				],
			}
		)
		doc.insert(ignore_permissions=True)
		doc.submit()
		frappe.db.commit()


def _ensure_role(role: str):
	if not frappe.db.exists("Role", role):
		frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(ignore_permissions=True)


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

			# Default company rotates; Locust still picks randomly per transaction
			default_company = company_names[(i - 1) % len(company_names)]
			frappe.defaults.set_user_default("company", default_company, email)

			# Clear company user-permissions so all 10 companies are usable
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
