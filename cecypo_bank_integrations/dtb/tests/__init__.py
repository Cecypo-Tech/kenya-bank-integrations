import json


class FakeRequest:
	"""Minimal stand-in for frappe.local.request used by webhook tests."""

	def __init__(self, body_bytes):
		self._body = body_bytes

	def get_data(self, as_text=False):
		return self._body.decode() if as_text else self._body

	def get_json(self, force=False, silent=False):
		return json.loads(self._body.decode())
