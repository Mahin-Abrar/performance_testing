"""HTTP helpers that mirror Desk API calls (list / getdoc / savedocs / reports)."""

from __future__ import annotations

import json
import random
from typing import Any

from locust import HttpUser

from loadtest import config


class FrappeDeskClient:
	"""Thin wrapper around Locust's HttpSession for Frappe token + session auth."""

	def __init__(self, user: HttpUser, creds: dict):
		self.user = user
		self.creds = creds
		self.csrf_token: str | None = None
		self._authed = False

	@property
	def client(self):
		return self.user.client

	def _headers(self, extra: dict | None = None) -> dict:
		headers = {
			"Host": config.SITE_HOST,
			"Accept": "application/json",
		}
		api_key = self.creds.get("api_key")
		api_secret = self.creds.get("api_secret")
		if api_key and api_secret:
			headers["Authorization"] = f"token {api_key}:{api_secret}"
		if self.csrf_token:
			headers["X-Frappe-CSRF-Token"] = self.csrf_token
		if extra:
			headers.update(extra)
		return headers

	def login(self) -> None:
		"""Session login (also refreshes csrf). Prefer API key when present."""
		if self.creds.get("api_key") and self.creds.get("api_secret"):
			# Validate token works; name request as login for SLO tracking
			with self.client.get(
				"/api/method/frappe.auth.get_logged_user",
				headers=self._headers(),
				name="login",
				catch_response=True,
			) as resp:
				if resp.status_code != 200:
					resp.failure(f"token auth failed: {resp.status_code} {resp.text[:200]}")
					return
				try:
					msg = resp.json().get("message")
				except Exception:
					resp.failure("invalid login response")
					return
				if msg in (None, "Guest"):
					resp.failure(f"not authenticated: {msg}")
				else:
					resp.success()
					self._authed = True
			# Token auth does not need CSRF for resource/method calls
			return

		with self.client.post(
			"/api/method/login",
			data={"usr": self.creds["email"], "pwd": self.creds["password"]},
			headers=self._headers(),
			name="login",
			catch_response=True,
		) as resp:
			if resp.status_code != 200:
				resp.failure(f"login HTTP {resp.status_code}")
				return
			try:
				body = resp.json()
			except Exception:
				resp.failure("login non-json")
				return
			if body.get("message") not in ("Logged In", "No App"):
				resp.failure(f"login rejected: {body}")
			else:
				resp.success()
				self._authed = True
		self._refresh_csrf()

	def logout(self) -> None:
		# Token auth has no session cookie; skip cookie logout (returns 403)
		if self.creds.get("api_key") and self.creds.get("api_secret"):
			self._authed = False
			return
		self.client.get(
			"/api/method/logout",
			headers=self._headers(),
			name="logout",
		)
		self.csrf_token = None
		self._authed = False

	def maybe_relogin(self, chance: float = 0.05) -> None:
		if random.random() < chance:
			self.logout()
			self.login()

	def _refresh_csrf(self) -> None:
		with self.client.get(
			"/app",
			headers=self._headers({"Accept": "text/html"}),
			name="desk_home",
			catch_response=True,
		) as resp:
			if resp.status_code >= 400:
				resp.failure(f"desk home {resp.status_code}")
				return
			text = resp.text or ""
			marker = 'csrf_token = "'
			idx = text.find(marker)
			if idx == -1:
				marker = 'csrf_token:"'
				idx = text.find(marker)
			if idx != -1:
				start = idx + len(marker)
				end = text.find('"', start)
				if end != -1:
					self.csrf_token = text[start:end]
					resp.success()
					return
			# Token auth may still work without csrf for GET; mark ok
			resp.success()

	def list_docs(self, doctype: str, limit: int = 20, filters: list | None = None) -> list[dict]:
		params: dict[str, Any] = {
			"fields": json.dumps(["name", "modified"]),
			"limit_page_length": limit,
			"limit_start": 0,
			"order_by": "modified desc",
		}
		if filters:
			params["filters"] = json.dumps(filters)
		with self.client.get(
			f"/api/resource/{doctype}",
			params=params,
			headers=self._headers(),
			name=f"list:{doctype}",
			catch_response=True,
		) as resp:
			if resp.status_code != 200:
				resp.failure(f"list {doctype}: {resp.status_code}")
				return []
			try:
				data = resp.json().get("data") or []
			except Exception:
				resp.failure("list non-json")
				return []
			resp.success()
			return data

	def getdoc(self, doctype: str, name: str) -> dict | None:
		with self.client.get(
			"/api/method/frappe.desk.form.load.getdoc",
			params={"doctype": doctype, "name": name},
			headers=self._headers(),
			name=f"form:{doctype}",
			catch_response=True,
		) as resp:
			if resp.status_code != 200:
				resp.failure(f"getdoc {doctype}/{name}: {resp.status_code}")
				return None
			try:
				payload = resp.json()
			except Exception:
				resp.failure("getdoc non-json")
				return None
			if payload.get("exc") or payload.get("exception"):
				resp.failure(str(payload.get("exception") or payload.get("exc"))[:200])
				return None
			resp.success()
			docs = payload.get("docs") or []
			return docs[0] if docs else payload.get("message")

	def savedocs(self, doc: dict, action: str = "Save") -> dict | None:
		name = "submit" if action == "Submit" else "save"
		payload = dict(doc)
		# Mapped docs from make_* often set __islocal without a temp name; savedocs crashes.
		if action == "Save" and (payload.get("__islocal") or not payload.get("name")):
			dt = (payload.get("doctype") or "doc").lower().replace(" ", "-")
			payload["name"] = f"new-{dt}-{random.randint(100000, 999999)}"
			payload["__islocal"] = 1
		with self.client.post(
			"/api/method/frappe.desk.form.save.savedocs",
			data={"doc": json.dumps(payload), "action": action},
			headers=self._headers({"Content-Type": "application/x-www-form-urlencoded"}),
			name=f"{name}:{doc.get('doctype')}",
			catch_response=True,
		) as resp:
			if resp.status_code != 200:
				resp.failure(f"{action} HTTP {resp.status_code}: {resp.text[:200]}")
				return None
			try:
				body = resp.json()
			except Exception:
				resp.failure(f"{action} non-json")
				return None
			if body.get("exc") or body.get("exception"):
				# Expected when masters missing / permission — count as failure for SLO
				resp.failure(str(body.get("exception") or body.get("_server_messages") or "")[:240])
				return None
			resp.success()
			docs = body.get("docs") or []
			return docs[0] if docs else body

	def run_report(self, report_name: str, filters: dict | None = None) -> None:
		data = {
			"report_name": report_name,
			"ignore_prepared_report": 1,
			"are_default_filters": 0,
		}
		if filters:
			data["filters"] = json.dumps(filters)
		with self.client.post(
			"/api/method/frappe.desk.query_report.run",
			data=data,
			headers=self._headers({"Content-Type": "application/x-www-form-urlencoded"}),
			name=f"report:{report_name}",
			catch_response=True,
		) as resp:
			if resp.status_code != 200:
				resp.failure(f"report HTTP {resp.status_code}")
				return
			try:
				payload = resp.json()
			except Exception:
				resp.failure("report non-json")
				return
			if payload.get("exc") or payload.get("exception"):
				resp.failure(str(payload.get("exception") or "")[:200])
				return
			resp.success()

	def call_method(self, method: str, args: dict | None = None, name: str | None = None) -> dict | None:
		"""Call a whitelisted ERPNext/Frappe method; returns message dict/list."""
		data = dict(args or {})
		with self.client.post(
			f"/api/method/{method}",
			data={k: (json.dumps(v) if isinstance(v, (dict, list)) else v) for k, v in data.items()},
			headers=self._headers({"Content-Type": "application/x-www-form-urlencoded"}),
			name=name or f"method:{method.split('.')[-1]}",
			catch_response=True,
		) as resp:
			if resp.status_code != 200:
				resp.failure(f"{method} HTTP {resp.status_code}: {resp.text[:200]}")
				return None
			try:
				payload = resp.json()
			except Exception:
				resp.failure(f"{method} non-json")
				return None
			if payload.get("exc") or payload.get("exception"):
				resp.failure(str(payload.get("exception") or payload.get("_server_messages") or "")[:240])
				return None
			resp.success()
			return payload.get("message")

	def desk_ping(self) -> None:
		"""Light Desk touch without loading full /app HTML."""
		self.client.get(
			"/api/method/frappe.auth.get_logged_user",
			headers=self._headers(),
			name="desk_ping",
		)
