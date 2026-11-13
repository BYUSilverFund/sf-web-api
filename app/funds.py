"""Canonical website fund IDs and reviewed aliases; never infer ownership from tickers."""

import re

FUND_ALIASES = {
    "undergrad": ("undergrad", "undergraduate", "undergrad fund", "undergraduate fund"),
    "quant": ("quant", "quant fund", "quantitative fund"),
    "brigham_capital": ("brigham_capital", "brigham capital"),
    "grad": ("grad", "graduate", "grad fund", "graduate fund"),
    "quant_paper": (
        "quant_paper",
        "quant paper",
        "quant paper fund",
        "quantitative paper fund",
    ),
}


def normalize_fund(value):
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ValueError("fund must be a string")
    value = value.strip().lower()
    for fund, aliases in FUND_ALIASES.items():
        if value in aliases:
            return fund
    raise ValueError("Unknown fund")


def mentioned_funds(question):
    aliases = {alias: fund for fund, names in FUND_ALIASES.items() for alias in names}
    pattern = (
        r"(?<!\w)(?:"
        + "|".join(re.escape(a) for a in sorted(aliases, key=len, reverse=True))
        + r")(?!\w)"
    )
    return {aliases[m.group().lower()] for m in re.finditer(pattern, question, re.I)}


def document_assignment(fund=None, document_scope=None):
    """Blank/unknown legacy metadata is unassigned, never shared."""
    try:
        canonical = normalize_fund(fund)
    except ValueError:
        canonical = None
    if document_scope == "shared":
        if fund and str(fund).strip():
            raise ValueError("Shared documents cannot also have a fund")
        return None, "shared"
    if canonical and document_scope in (None, "fund"):
        return canonical, "fund"
    if document_scope not in (None, "unassigned", "fund"):
        raise ValueError("Unknown document scope")
    if canonical and document_scope == "unassigned":
        raise ValueError("Unassigned documents cannot also have a fund")
    return None, "unassigned"
