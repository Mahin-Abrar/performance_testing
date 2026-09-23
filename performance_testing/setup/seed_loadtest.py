"""Seed masters + perf_* users + API keys for Locust desk-mix on site `performance`.

Run:
  bench --site performance execute performance_testing.setup.seed_loadtest.seed

Writes credentials to apps/performance_testing/loadtest/users.json (gitignored).
"""

from __future__ import annotations

import json
from pathlib import Path

import frappe
from frappe.utils.password import update_password

COMPANY = "Fusion"
PASSWORD = "PerfTest@123"


def _users_json_path() -> Path:
	# app path is .../performance_testing/performance_testing → parent is app root
	return Path(frappe.get_app_path("performance_testing")).parent / "loadtest" / "users.json"


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


def seed():
	"""Create minimal masters and 100 Locust users; write users.json."""
	# Bypass User creation throttle (default 60 users / minute)
	frappe.flags.in_import = True
	_ensure_masters()
	users = _ensure_users()
	path = _users_json_path()
	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_text(json.dumps(users, indent=2))
	frappe.db.commit()
	print(f"Seeded {len(users)} users → {path}")
	print(f"Company={COMPANY} password={PASSWORD}")
	return {"users": len(users), "users_file": str(path)}


def _ensure_masters():
	if not frappe.db.exists("Company", COMPANY):
		frappe.throw(f"Company {COMPANY} missing on this site")

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


def _ensure_role(role: str):
	if not frappe.db.exists("Role", role):
		frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(ignore_permissions=True)


def _ensure_users() -> list[dict]:
	out: list[dict] = []
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
			changed = False
			for role in [*roles, "Desk User"]:
				if role not in existing and frappe.db.exists("Role", role):
					user.append("roles", {"role": role})
					changed = True

			# Fresh API credentials (plaintext secret returned once via Password field)
			api_key = user.api_key or frappe.generate_hash(length=15)
			api_secret = frappe.generate_hash(length=15)
			user.api_key = api_key
			user.api_secret = api_secret
			user.save(ignore_permissions=True)

			frappe.defaults.set_user_default("company", COMPANY, email)

			out.append(
				{
					"email": email,
					"password": PASSWORD,
					"persona": persona,
					"api_key": api_key,
					"api_secret": api_secret,
				}
			)
	return out
