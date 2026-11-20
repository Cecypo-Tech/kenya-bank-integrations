import base64
from unittest import mock

import frappe
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from frappe.tests.utils import FrappeTestCase

from cecypo_bank_integrations.kcb_m_pesa.utils import (
	get_access_token,
	get_base_url,
	resolve_account_mapping,
	verify_signature,
)


class TestKCBMPesaUtils(FrappeTestCase):
	def setUp(self):
		self.settings = frappe.get_single("Bank Integration Settings")
		self._orig_mappings = list(self.settings.kcb_mpesa_account_mappings)
		self._orig_env = self.settings.environment
		self._orig_uat = self.settings.uat_base_url
		self._orig_prod = self.settings.production_base_url
		frappe.cache().delete_value("kcb_mpesa_access_token")

	def tearDown(self):
		self.settings.reload()
		self.settings.kcb_mpesa_account_mappings = self._orig_mappings
		self.settings.environment = self._orig_env
		self.settings.uat_base_url = self._orig_uat
		self.settings.production_base_url = self._orig_prod
		self.settings.save()
		frappe.cache().delete_value("kcb_mpesa_access_token")

	def test_get_base_url_uat(self):
		self.settings.environment = "UAT"
		self.settings.uat_base_url = "https://uat.buni.kcbgroup.com"
		self.settings.save()
		self.assertEqual(get_base_url(self.settings), "https://uat.buni.kcbgroup.com")

	def test_get_base_url_production(self):
		self.settings.environment = "Production"
		self.settings.production_base_url = "https://buni.kcbgroup.com"
		self.settings.save()
		self.assertEqual(get_base_url(self.settings), "https://buni.kcbgroup.com")

	def test_resolve_account_mapping_found(self):
		self.settings.kcb_mpesa_account_mappings = []
		self.settings.append("kcb_mpesa_account_mappings", {
			"till_or_account_identifier": "1234567",
			"company": frappe.db.get_value("Company", {}, "name"),
			"bank_account": frappe.db.get_value("Account", {"account_type": "Bank", "is_group": 0}, "name"),
		})
		self.settings.save()

		company, bank_account = resolve_account_mapping("1234567")
		self.assertIsNotNone(company)
		self.assertIsNotNone(bank_account)

	def test_resolve_account_mapping_not_found(self):
		company, bank_account = resolve_account_mapping("does-not-exist-999")
		self.assertIsNone(company)
		self.assertIsNone(bank_account)

	def test_verify_signature_valid(self):
		private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
		public_pem = private_key.public_key().public_bytes(
			encoding=serialization.Encoding.PEM,
			format=serialization.PublicFormat.SubjectPublicKeyInfo,
		).decode()

		self.settings.kcb_public_key = public_pem
		self.settings.save()

		body = b'{"transactionID": "FT123"}'
		signature = private_key.sign(body, padding.PKCS1v15(), hashes.SHA256())
		signature_b64 = base64.b64encode(signature).decode()

		self.assertTrue(verify_signature(body, signature_b64, self.settings))

	def test_verify_signature_invalid(self):
		private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
		public_pem = private_key.public_key().public_bytes(
			encoding=serialization.Encoding.PEM,
			format=serialization.PublicFormat.SubjectPublicKeyInfo,
		).decode()

		self.settings.kcb_public_key = public_pem
		self.settings.save()

		body = b'{"transactionID": "FT123"}'
		tampered_body = b'{"transactionID": "FT999"}'
		signature = private_key.sign(body, padding.PKCS1v15(), hashes.SHA256())
		signature_b64 = base64.b64encode(signature).decode()

		self.assertFalse(verify_signature(tampered_body, signature_b64, self.settings))

	def test_get_access_token_caches(self):
		self.settings.client_id = "test-client"
		self.settings.client_secret = "test-secret"
		self.settings.save()

		mock_response = mock.Mock()
		mock_response.json.return_value = {"access_token": "abc123", "expires_in": 3600}
		mock_response.raise_for_status.return_value = None

		with mock.patch(
			"cecypo_bank_integrations.kcb_m_pesa.utils.requests.get", return_value=mock_response
		) as mock_get:
			token1 = get_access_token(self.settings)
			token2 = get_access_token(self.settings)

		self.assertEqual(token1, "abc123")
		self.assertEqual(token2, "abc123")
		mock_get.assert_called_once()
