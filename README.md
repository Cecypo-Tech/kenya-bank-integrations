### Kenya Bank Integrations for ERPNext

A Frappe app (`cecypo_bank_integrations`) that brings Kenyan bank payment APIs into ERPNext:

- **I&M Bank** – Business Connect collections and M-Pesa Push (documented below).
- **KCB M-Pesa (BUNI)** – payment notifications and Payment Entry creation.
- **DTB** – IPN payment notifications.

Looking for SMS Payments (recording payments from M-Pesa and bank SMS)? It has moved to its own app,
which works without this one: [SMS Payments Bridge](https://github.com/Cecypo-Tech/sms-payments-bridge)
holds both the ERPNext app and the Android phone app.

### Installation

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app https://github.com/Cecypo-Tech/kenya-bank-integrations --branch version-16
bench --site <your-site> install-app cecypo_bank_integrations
bench --site <your-site> migrate
```

---

## I&M Bank

Two inbound integrations with I&M Bank. Both create **IM Bank Transaction** records, distinguished by the `source` field.

### DocTypes

| DocType | Type | Purpose |
|---|---|---|
| IM Bank Settings | Single | Global config: enabled flag, default company, customer ref validation mode |
| IM Bank Mpesa Account | Regular | Maps a M-Pesa `accountRef` to an ERPNext Company + Bank Account |
| IM Bank Transaction | Submittable | Unified record for both Business Connect and Mpesa Push transactions |

### IM Bank Settings

Navigate to **IM Bank Settings** to configure:

- **Enabled** – enable/disable the integration
- **Customer Ref Validation Mode**
  - `Non-strict` *(default)* – `customerRef` is stored as a reference only; payment is always accepted
  - `Strict` – `customerRef` must match an existing Customer record; payment is rejected if not found
- **Default Company** – fallback company used when creating Payment Entries

### IM Bank Mpesa Account

Create one record per M-Pesa paybill/till, mapping:
- **Account Ref** – the `accountRef` value sent by I&M Bank (must match exactly)
- **Company** – the ERPNext company to post against
- **Bank Account** – the ERPNext bank account to receive funds into

---

### API 1 – I&M Bank Business Connect (Collections API v2.0)

The bank calls these two endpoints to validate customers and notify of incoming payments.

#### Validate Customer

```
POST /api/method/cecypo_bank_integrations.im_bank.api.business_connect.validate
```

Request:
```json
{ "customerRef": "C1012" }
```

Success response (`200`):
```json
{ "resultCode": 0, "message": "Customer found", "customerName": "Clark Kent", "customerRef": "C1012" }
```

Not found (`404`):
```json
{ "resultCode": 1, "message": "Customer not found", "customerName": "", "customerRef": "" }
```

#### Payment Notification

```
POST /api/method/cecypo_bank_integrations.im_bank.api.business_connect.payment
```

Request:
```json
{
  "paymentType": "MPESA",
  "transactionReference": "S44998347",
  "transactionDate": "2025-08-15T10:30:00",
  "amount": 2500.00,
  "currency": "KES",
  "shortCode": "123456",
  "additions": {
    "customerRef": "C1012",
    "externalRefNumber": "QHJ7XXXXXX",
    "payerName": "John Doe",
    "payerMobileNumber": "254712345678"
  }
}
```

Supported `paymentType` values: `MPESA`, `RTGS`, `PESALINK`, `OTG`, `BRANCH`, `CHEQUE`.

Success response (`200`):
```json
{ "resultCode": 0, "resultDesc": "Payment received successfully", "erpRefId": "IM-TXN-2026-00001" }
```

---

### API 2 – I&M Bank Mpesa Push

The bank calls this endpoint to push M-Pesa payment notifications.

#### Process Push

```
POST /api/method/cecypo_bank_integrations.im_bank.api.mpesa_push.process
```

Request:
```json
{
  "transRef": "TXN123456",
  "mpesaRef": "QHJ7XXXXXX",
  "MSISDN": "254712345678",
  "amount": 1500.00,
  "narration": "Payment for invoice",
  "accountRef": "ACC001",
  "sortCode": "01"
}
```

Success response (`200`):
```json
{ "statusCode": "0", "statusDescription": "Success", "mpesaRef": "QHJ7XXXXXX" }
```

---

### Authentication

All endpoints require a valid Frappe user session. The bank should authenticate using one of:

- **API Key + Secret** – recommended for server-to-server; pass as `Authorization: token <api_key>:<api_secret>`
- **Basic Auth** – `Authorization: Basic base64(username:password)`

Create a dedicated Frappe user with the **System Manager** role for I&M Bank and issue API keys via **User → API Access**.

---

### Payment Entry Creation

Once an **IM Bank Transaction** is submitted, a **Create Payment Entry** button appears on the form. This creates a `Receive` Payment Entry against the resolved Customer. Enable **Auto-Submit Payment Entry** on the transaction to have it submitted automatically.

---

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/cecypo_bank_integrations
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade

### License

GNU General Public License v3.0 or later. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
Copyright (C) 2026 Cecypo Tech.
