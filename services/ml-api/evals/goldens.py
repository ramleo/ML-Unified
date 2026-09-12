"""The golden set: documents whose correct answers are known because we
wrote them.

Six documents, one per path worth watching. Each declares the doc_type it
must be classified as, the values a correct extraction should contain, and
whether the validator's arithmetic should complain.

What is deliberately NOT here:

- No assertion on how many fields come back. The extractor is asked to
  volunteer any extra sections it finds, so the count is a model's
  decision and moved 15 to 13 to 18 across providers. Only named values
  are checked.
- No assertion on phrasing. Values are compared as amounts, dates, or
  loosely-contained text — see _check.py.
- No scanned documents. That path needs a vision model, which is the paid
  key, and this suite must never reach it.

`must_flag` and `must_not_flag` are held to a hard standard rather than
scored, because they are arithmetic. Once the model has extracted the
three numbers, whether 1000 + 180 equals the stated total is not a matter
on which a model gets a vote.
"""
from __future__ import annotations

_INVOICE_BODY = [
    "Northwind Trading Ltd.",
    "14 Harbour Road, Bristol BS1 5TY, United Kingdom",
    "",
    "Invoice Number: INV-2026-0412",
    "Invoice Date: 2026-03-04",
    "Due Date: 2026-04-03",
    "Payment Terms: Net 30",
    "",
    "Bill To:",
    "Calder Robotics GmbH",
    "Sonnenallee 12, 10405 Berlin, Germany",
    "",
    "Description                    Qty     Unit price      Amount",
    "Servo controller SC-40          10         45.00       450.00",
    "Harness loom HL-2               22         25.00       550.00",
    "",
]

GOLDENS: list[dict] = [
    {
        "id": "invoice_consistent",
        "doc_type": "invoice",
        "lines": ["INVOICE"] + _INVOICE_BODY + [
            "Subtotal                                       1000.00",
            "VAT at 18%                                      180.00",
            "Total Due                                      1180.00",
        ],
        "values": {
            "vendor": ("text", "Northwind Trading"),
            "invoice_no": ("text", "INV-2026-0412"),
            "date": ("date", "2026-03-04"),
            "due_date": ("date", "2026-04-03"),
            "bill_to": ("text", "Calder Robotics"),
            "subtotal": ("amount", "1000.00"),
            "tax": ("amount", "180.00"),
            "total": ("amount", "1180.00"),
            "payment_terms": ("text", "Net 30"),
        },
        "must_not_flag": ["total"],
        "must_flag": [],
    },
    {
        "id": "invoice_total_does_not_add_up",
        "doc_type": "invoice",
        # Same document, one number changed. 1000 + 180 is not 1500, and
        # the validator has to say so — this is the check that catches a
        # padded invoice, and the only golden here that is *supposed* to
        # come back with a complaint on it.
        "lines": ["INVOICE"] + _INVOICE_BODY + [
            "Subtotal                                       1000.00",
            "VAT at 18%                                      180.00",
            "Total Due                                      1500.00",
        ],
        "values": {
            "invoice_no": ("text", "INV-2026-0412"),
            "subtotal": ("amount", "1000.00"),
            "total": ("amount", "1500.00"),
        },
        "must_not_flag": [],
        "must_flag": ["total"],
    },
    {
        "id": "receipt",
        "doc_type": "receipt",
        # The classifier's hardest real distinction: a receipt is proof a
        # payment happened, an invoice is a request for one. Both carry a
        # vendor, a date, a subtotal, a tax line and a total. The signal is
        # the payment method and the absence of any due date.
        "lines": [
            "RECEIPT",
            "Ferngate Coffee House",
            "Store #218, 4 Mill Lane, Leeds LS1 6DL",
            "",
            "Date: 2026-02-19",
            "Served by: cashier 07",
            "",
            "2 x Flat white                                    7.00",
            "1 x Cardamom bun                                  3.90",
            "1 x Retail bag of beans 250g                      7.50",
            "",
            "Subtotal                                         18.40",
            "Tax                                               0.92",
            "Total                                            19.32",
            "",
            "Payment Method: Visa ending 4417",
            "Thank you for your purchase.",
        ],
        "values": {
            "merchant": ("text", "Ferngate Coffee House"),
            "date": ("date", "2026-02-19"),
            "subtotal": ("amount", "18.40"),
            "total": ("amount", "19.32"),
            "payment_method": ("text", "Visa"),
        },
        "must_not_flag": ["total"],
        "must_flag": [],
    },
    {
        "id": "bank_statement",
        "doc_type": "bank_statement",
        "lines": [
            "ACCOUNT STATEMENT",
            "Meridian Savings Bank",
            "",
            "Account Holder: Priya Raghavan",
            "Account Number: 8842 1190 3376",
            "Statement Period: 1 January 2026 to 31 January 2026",
            "",
            "Opening Balance                                5000.00",
            "Total Credits                                  2000.00",
            "Total Debits                                   1500.00",
            "Closing Balance                                5500.00",
            "",
            "Transaction history available on request.",
        ],
        "values": {
            "bank_name": ("text", "Meridian Savings Bank"),
            "account_holder": ("text", "Priya Raghavan"),
            "opening_balance": ("amount", "5000.00"),
            "total_credits": ("amount", "2000.00"),
            "total_debits": ("amount", "1500.00"),
            "closing_balance": ("amount", "5500.00"),
        },
        "must_not_flag": ["closing_balance"],
        "must_flag": [],
    },
    {
        "id": "purchase_order",
        "doc_type": "purchase_order",
        "lines": [
            "PURCHASE ORDER",
            "Alderman Engineering Ltd",
            "",
            "PO Number: PO-77310",
            "Order Date: 2026-01-22",
            "Delivery Date: 2026-02-16",
            "",
            "Supplier: Trent Metals Ltd",
            "Ship To: Unit 6, Cannock Industrial Park, Staffordshire",
            "",
            "Item                           Qty     Unit price     Amount",
            "Mild steel sheet 2mm           120          52.50    6300.00",
            "Aluminium angle 40x40           60          35.00    2100.00",
            "",
            "Total                                                8400.00",
            "Terms: FOB destination, 60 days",
        ],
        "values": {
            "buyer": ("text", "Alderman Engineering"),
            "supplier": ("text", "Trent Metals"),
            "po_number": ("text", "PO-77310"),
            "date": ("date", "2026-01-22"),
            "delivery_date": ("date", "2026-02-16"),
            "total": ("amount", "8400.00"),
        },
        "must_not_flag": [],
        "must_flag": [],
    },
    {
        "id": "resume",
        "doc_type": "resume",
        # The most-used document type on this tool, and the one with the
        # widest schema. Years of experience is deliberately not asserted:
        # it is computed prose, and the rule that computes it sums listed
        # roles rather than subtracting dates — already covered by a unit
        # test that does not need a model.
        "lines": [
            "CURRICULUM VITAE",
            "Amara Osei",
            "amara.osei@example.com  |  +44 7700 900412  |  Manchester, UK",
            "linkedin.com/in/amaraosei  |  github.com/amaraosei",
            "",
            "Senior Data Engineer",
            "",
            "WORK EXPERIENCE",
            "Senior Data Engineer, Halcyon Analytics, March 2021 to Present",
            "  Owned the batch ingestion platform and its on-call rota.",
            "Data Engineer, Brightlane Systems, June 2017 to February 2021",
            "  Built the warehouse migration from Redshift to Snowflake.",
            "",
            "EDUCATION",
            "MSc Computer Science, University of Manchester, 2017",
            "",
            "TECHNICAL SKILLS",
            "Python, Spark, dbt, Airflow, PostgreSQL, Terraform",
        ],
        "values": {
            "name": ("text", "Amara Osei"),
            "email": ("text", "amara.osei@example.com"),
            "location": ("text", "Manchester"),
            "github": ("text", "github.com/amaraosei"),
            "current_title": ("text", "Senior Data Engineer"),
            "technical_skills": ("text", "Python"),
            "education_summary": ("text", "University of Manchester"),
        },
        "must_not_flag": ["email"],
        "must_flag": [],
    },
]
