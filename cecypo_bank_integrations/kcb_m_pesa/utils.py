"""
KCB M-Pesa (BUNI) — shared settings, OAuth, signature verification, and account mapping helpers.
"""

import base64

import frappe
import requests
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import load_pem_public_key

ACCESS_TOKEN_CACHE_KEY = "kcb_mpesa_access_token"


def get_settings():
	settings = frappe.get_single("Bank Integration Settings")
	if not settings.kcb_mpesa_enabled:
		frappe.throw("KCB M-Pesa integration is not enabled in Bank Integration Settings.")
	return settings


def get_base_url(settings):
	if settings.environment == "Production":
		return (settings.production_base_url or "").rstrip("/")
	return (settings.uat_base_url or "https://uat.buni.kcbgroup.com").rstrip("/")


def get_access_token(settings):
	cached = frappe.cache().get_value(ACCESS_TOKEN_CACHE_KEY)
	if cached:
		return cached

	response = requests.get(
		f"{get_base_url(settings)}/token?grant_type=client_credentials",
		auth=(settings.client_id, settings.get_password("client_secret")),
		timeout=15,
	)
	response.raise_for_status()
	data = response.json()

	token = data["access_token"]
	expires_in = int(data.get("expires_in", 3600))
	frappe.cache().set_value(ACCESS_TOKEN_CACHE_KEY, token, expires_in_sec=max(expires_in - 30, 30))
	return token


def verify_signature(body_bytes, signature_b64, settings):
	try:
		public_key = load_pem_public_key(settings.kcb_public_key.encode())
		signature = base64.b64decode(signature_b64)
		public_key.verify(signature, body_bytes, padding.PKCS1v15(), hashes.SHA256())
		return True
	except Exception:
		return False


def resolve_account_mapping(identifier):
	settings = frappe.get_single("Bank Integration Settings")
	mapping = next(
		(r for r in settings.kcb_mpesa_account_mappings if r.till_or_account_identifier == identifier),
		None,
	)
	if not mapping:
		return None, None
	return mapping.company, mapping.bank_account
