"""Extraction templates for the audit evidence extraction demo.

Each template is a list of attributes written in natural language. The JSON schema sent to
the Nutrient Vision structured extraction is generated from this list, so adding an attribute
is one line: name, type, semantic description.
"""

CLASSIFICATION_LABELS = {
    "soc_report": (
        "An independent service auditor's assurance report (SOC 1, SOC 2, SOC 3, ISAE 3402, "
        "ISAE 3000) with an opinion on a service organization's controls, a system description "
        "and a management assertion."
    ),
    "invoice": (
        "A commercial invoice or bill issued by a supplier to a customer, with invoice number, "
        "line items, amounts, taxes, a total due and payment or bank details."
    ),
    "other": "Any other document type: contract, policy, letter, presentation, spreadsheet.",
}

TEMPLATES = {
    "soc_report": {
        "label": "SOC / ISAE assurance report",
        "instructions": (
            "This is an independent service auditor's report. Read Section I (the auditor's "
            "report) first. Report values exactly as printed in the document. Use null when an "
            "attribute is genuinely absent."
        ),
        "attributes": [
            {
                "name": "auditing_standard_applied",
                "type": "string",
                "description": (
                    "The attestation or auditing standard the service auditor applied, e.g. "
                    "'SSAE No. 18 / No. 21, AT-C Section 320', 'ISAE 3000 (Revised)', "
                    "'ISAE 3402', 'TSP Section 100 / 2017 Trust Services Criteria'. "
                    "Null if the report never names a standard."
                ),
            },
            {
                "name": "period_covered",
                "type": "string",
                "description": (
                    "The period the report covers. For a Type II report the date range "
                    "(e.g. 'October 1, 2025 to September 30, 2026'); for a Type I report the "
                    "single 'as of' date."
                ),
            },
            {
                "name": "auditor_signoff_date",
                "type": "string",
                "description": (
                    "The date the service auditor signed the report: the date printed with the "
                    "audit firm's name and city at the end of the auditor's report section. "
                    "Not the period end date and not the management assertion date."
                ),
            },
            {
                "name": "opinion",
                "type": "string",
                "enum": ["unqualified", "qualified", "adverse", "disclaimer"],
                "description": (
                    "The type of opinion expressed by the service auditor. 'unqualified' when "
                    "the auditor states that the description fairly presents the system and "
                    "controls were suitably designed (and operated effectively for Type II) "
                    "in all material respects, with no 'except for' wording."
                ),
            },
            {
                "name": "opinion_statement",
                "type": "string",
                "description": (
                    "The sentence that opens the auditor's opinion, quoted verbatim, "
                    "starting with 'In our opinion'."
                ),
            },
            {
                "name": "service_auditor",
                "type": "string",
                "description": "Name of the independent service auditor firm that issued the report.",
            },
            {
                "name": "service_organization",
                "type": "string",
                "description": "Name of the service organization whose controls were examined.",
            },
            {
                "name": "report_type",
                "type": "string",
                "description": "Kind of report, e.g. 'SOC 1 Type I', 'SOC 2 Type II', 'ISAE 3000 Type II'.",
            },
            {
                "name": "exceptions_noted",
                "type": "boolean",
                "description": (
                    "True if the auditor reports any control exceptions, deviations or "
                    "deficiencies in the testing results; false if none were noted."
                ),
            },
        ],
    },
    "invoice": {
        "label": "Supplier invoice",
        "instructions": (
            "This is a supplier invoice addressed to a customer. Distinguish the supplier "
            "(issuer, top of the page) from the customer (bill-to block). Report values exactly "
            "as printed. Use null when an attribute is absent."
        ),
        "attributes": [
            {
                "name": "po_number",
                "type": "string",
                "description": (
                    "The customer's purchase order identifier referenced on the invoice, "
                    "e.g. 'PO-81204'. Only the identifier, without any description in "
                    "parentheses. Null when the invoice states there is no PO or is a "
                    "non-PO engagement."
                ),
            },
            {
                "name": "supplier_tax_id",
                "type": "string",
                "description": (
                    "The tax ID or VAT ID of the supplier who issued the invoice, usually in "
                    "the header next to the supplier's address. Not the customer's tax ID."
                ),
            },
            {
                "name": "customer_tax_id",
                "type": "string",
                "description": "The tax ID or VAT number printed in the bill-to / recipient block.",
            },
            {
                "name": "bank_account_number",
                "type": "string",
                "description": (
                    "The supplier's bank account number for payment: the IBAN if present, "
                    "otherwise the digits printed right after the label 'A/C', 'Account' or "
                    "'Acct'. A routing number, ABA, FedWire, BIC, SWIFT or sort code is NOT "
                    "an account number and belongs in bank_routing_code instead."
                ),
            },
            {
                "name": "bank_routing_code",
                "type": "string",
                "description": (
                    "The bank routing identifier if printed: ABA / routing number, BIC or "
                    "SWIFT code. Null if absent."
                ),
            },
            {
                "name": "total_due_incl_tax",
                "type": "number",
                "description": (
                    "The final amount payable including tax: 'Total due', 'Grand total', "
                    "'Net amount payable' or equivalent. A number without currency symbol."
                ),
            },
            {
                "name": "currency",
                "type": "string",
                "description": "ISO 4217 currency code of the total due (EUR, USD, GBP...).",
            },
            {
                "name": "invoice_number",
                "type": "string",
                "description": "The supplier's invoice number.",
            },
            {
                "name": "supplier_name",
                "type": "string",
                "description": "Legal name of the supplier who issued the invoice.",
            },
        ],
    },
}


def schema_from(attributes: list[dict]) -> dict:
    properties = {}
    for attribute in attributes:
        spec = {"type": attribute.get("type", "string"), "description": attribute.get("description", "")}
        if attribute.get("enum"):
            spec["enum"] = list(attribute["enum"])
        properties[attribute["name"]] = spec
    return {"type": "object", "properties": properties}
