"""Stable Markdown and CSV report renderers."""

from __future__ import annotations

import csv
import html
import io
import re
import unicodedata


CSV_COLUMNS = [
    "company_id", "plan_id", "role", "currency", "unit", "requested_quantity",
    "effective_quantity", "observed_rate", "price_period", "billed_period",
    "monthly_equivalent", "base_due_per_billing_period", "inclusion_state",
    "scenario_status", "unknown_terms", "evidence_source_ids", "evidence_urls",
    "provenance_notice",
]


def _safe(value: object) -> str:
    text = "" if value is None else re.sub(r"\s+", " ", str(value)).strip()
    text = html.escape(text, quote=False).replace("\\", "\\\\")
    for character in "[]()|`":
        text = text.replace(character, "\\" + character)
    return text


def _formula(value: object) -> object:
    if not isinstance(value, str):
        return value
    offset = 0
    while offset < len(value) and (value[offset].isspace() or unicodedata.category(value[offset]) in {"Cc", "Cf"}):
        offset += 1
    probe = value[offset:]
    return "'" + value if probe.startswith(("=", "+", "-", "@")) else value


def _refs(row: dict, report: dict) -> tuple[list[str], list[str]]:
    ids = []
    for values in row.get("evidence", {}).values():
        for citation in values:
            if citation["source_id"] not in ids:
                ids.append(citation["source_id"])
    urls_by_id = {item["id"]: item["url"] for item in report["source_index"]}
    return ids, [urls_by_id[item] for item in ids if urls_by_id.get(item)]


def render_csv(report: dict) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=CSV_COLUMNS, lineterminator="\n")
    writer.writeheader()
    for row in report["offers"]:
        ids, urls = _refs(row, report)
        values = {
            "company_id": row["company_id"], "plan_id": row["plan_id"], "role": row["role"],
            "currency": row["currency"], "unit": row["unit"], "requested_quantity": row["requested_quantity"],
            "effective_quantity": row["effective_quantity"], "observed_rate": row["observed_price"],
            "price_period": row["price_period"], "billed_period": row["billed_period"],
            "monthly_equivalent": row["monthly_equivalent"],
            "base_due_per_billing_period": row["base_due_per_billing_period"],
            "inclusion_state": row["inclusion_state"], "scenario_status": row["scenario_status"],
            "unknown_terms": ";".join(row["unknown_terms"]), "evidence_source_ids": ";".join(ids),
            "evidence_urls": ";".join(urls),
            "provenance_notice": report.get("provenance_notice", "A self-asserted receipt does not authenticate provider origin."),
        }
        writer.writerow({key: _formula(value) for key, value in values.items()})
    return stream.getvalue()


def render_markdown(report: dict) -> str:
    scenario = report["scope"]["scenario"]
    lines = [
        "# Competitor offer scenario worksheet", "",
    ]
    if any(source["provenance"] == "synthetic_fixture" for source in report["source_index"]):
        lines.extend(["> Synthetic fixture data: all synthetic-labeled sources are invented examples.", ""])
    lines.extend([
        f"**Method:** `{report['analysis_method']}`", "",
        f"**Bounded scenario:** {scenario['quantity']} {_safe(scenario['unit'])}; billing preference {_safe(scenario['billing_preference'])}; required inclusion {_safe(scenario['required_inclusion'])}.", "",
        "Monthly equivalents are comparison calculations, not monthly payment options. Taxes, fees, discounts, and unselected terms remain unknown. This worksheet does not select a winner.", "",
        _safe(report.get("provenance_notice", "A self-asserted receipt does not authenticate provider origin.")), "",
        "## Offers", "",
    ])
    for row in report["offers"]:
        observed = (
            f"{_safe(row['currency'])} {_safe(row['observed_price'])} per {_safe(row['unit'])}/{_safe(row['price_period'])}"
            if row["observed_price"] is not None else "unknown"
        )
        lines.extend([
            f"### {_safe(row['company_name'])}: {_safe(row['plan_name'])}", "",
            f"- Observed rate: {observed}",
            f"- Billing commitment: {_safe(row['billed_period']) if row['billed_period'] is not None else 'unknown'}",
            f"- Monthly equivalent: {_safe(row['monthly_equivalent']) if row['monthly_equivalent'] is not None else 'unknown'} (comparison only)",
            f"- Base due per billing period: {_safe(row['base_due_per_billing_period']) if row['base_due_per_billing_period'] is not None else 'unknown'}",
            f"- Required inclusion: {_safe(row['inclusion_state']).replace('_', ' ')}",
            f"- Declared-check result: {_safe(row['scenario_status']).replace('_', ' ')}", "",
        ])
        for candidate in row.get("price_candidates", []):
            lines.append(f"- Unsupported price candidate: {_safe(candidate)}")
        for unknown in row["unknown_terms"]:
            lines.append(f"- Unknown/limit: {_safe(unknown)}")
        lines.append("")
        for field, refs in row["evidence"].items():
            for ref in refs:
                lines.append(f"- Evidence ({_safe(field)}): `{ref['source_id']}/{ref['block_id']}`: “{_safe(ref['quote'])}”")
        lines.append("")
    if report["own_clarity_notes"]:
        lines.extend(["## Own-offer clarity checks", ""] + [f"- {_safe(note)}" for note in report["own_clarity_notes"]] + [""])
    lines.extend(["## Evidence appendix", ""])
    for source in report["source_index"]:
        lines.append(
            f"- `{source['id']}`: {_safe(source['url'])}; observed {_safe(source['observed_at'])}; "
            f"record {_safe(source['record_id'])}; SHA-256 `{source['content_sha256']}`; provenance `{source['provenance']}`."
        )
    lines.extend([
        "", "## Limits", "",
        "Selected pages and narrow literal grammar bound this report. Unknown means not established by the selected scope, not absent from the market or offer.", "",
        "Uses Bright Data for optional public-data retrieval. Analysis and decisions are local application logic. Not affiliated with or endorsed by Bright Data.", "",
    ])
    return "\n".join(lines)
