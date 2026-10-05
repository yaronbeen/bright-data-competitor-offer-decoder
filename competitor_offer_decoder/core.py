"""Validation and deterministic offer analysis."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from .url_safety import validate_https_url


PROJECT = "competitor-offer-decoder"
PROVENANCE_NOTICE = "A self-asserted receipt does not authenticate provider origin."
ID_RE = re.compile(r"[a-z][a-z0-9_-]{0,63}\Z")
UTC_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z\Z")
UNIT_RE = re.compile(r"[a-z]{1,32}\Z")
CURRENCIES = {"USD", "EUR", "GBP", "AUD", "CAD"}
SOURCE_KEYS = {
    "id", "kind", "role", "url", "title", "text", "status", "observed_at",
    "published_at", "provider_date", "record_id", "record_id_origin", "provenance",
}
PRICE_RE = re.compile(
    r"(?:(?P<currency>USD|EUR|GBP|AUD|CAD) |(?P<dollar>\$))(?P<amount>0|[1-9]\d{0,6})(?:\.(?P<cents>\d{1,2}))? per "
    r"(?P<unit>[a-z]+)/(?P<period>month|year)(?:, billed (?P<billed>monthly|annually))?\.\Z"
)
MINIMUM_RE = re.compile(r"Minimum (?P<count>[1-9]\d{0,5}) (?P<unit>[a-z]+)\.\Z")


def _error(message: str) -> ValueError:
    return ValueError(message)


def _exact_keys(value: dict, required: set[str], optional: set[str] = set()) -> None:
    if set(value) - required - optional:
        raise _error("unknown object key")
    if required - set(value):
        raise _error("missing required field")


def _string(value: Any, minimum: int, maximum: int, name: str) -> str:
    if not isinstance(value, str) or not (minimum <= len(value) <= maximum) or not value.strip():
        raise _error(f"invalid {name}")
    return value


def _identifier(value: Any, name: str = "id") -> str:
    if not isinstance(value, str) or not ID_RE.fullmatch(value):
        raise _error(f"invalid {name}")
    return value


def _utc(value: Any, name: str) -> datetime:
    if not isinstance(value, str) or not UTC_RE.fullmatch(value):
        raise _error(f"invalid {name}")
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00").astimezone(timezone.utc)
    except ValueError as exc:
        raise _error(f"invalid {name}") from exc


def _https_url(value: Any, *, nullable: bool = False) -> str | None:
    return validate_https_url(value, nullable=nullable)


def normalize_text(text: str) -> tuple[str, list[dict[str, Any]]]:
    if not isinstance(text, str):
        raise _error("text must be a string")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if any(ord(char) < 32 and char not in "\t\n" for char in text):
        raise _error("source text contains unsupported controls")
    probe = text.strip().casefold()
    if probe.startswith(("<!doctype html", "<html", "<body")):
        raise _error("unsupported_content_format")
    raw_blocks: list[tuple[str, int | None]] = []
    for group in re.split(r"\n[\t ]*\n+", text):
        group = group.strip()
        if not group:
            continue
        lines = group.split("\n")
        current: list[str] = []
        for line in lines:
            heading = re.fullmatch(r"[ \t]*(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*", line)
            if heading:
                if current:
                    raw_blocks.append(("\n".join(current), None))
                    current = []
                raw_blocks.append((heading.group(2), len(heading.group(1))))
            else:
                current.append(line)
        if current:
            raw_blocks.append(("\n".join(current), None))
    blocks = []
    for index, (raw, level) in enumerate(raw_blocks, 1):
        canonical = re.sub(r"\s+", " ", raw, flags=re.UNICODE).strip()
        if canonical:
            blocks.append({"id": f"b{index:04d}", "text": canonical, "heading_level": level})
    return "\n\n".join(block["text"] for block in blocks), blocks


def _validate_source(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _error("source must be an object")
    _exact_keys(value, SOURCE_KEYS)
    source = dict(value)
    _identifier(source["id"])
    if source["kind"] not in {"page", "operator_note"}:
        raise _error("unsupported source kind")
    if source["role"] not in {"offer_page", "terms_page", "context_note"}:
        raise _error("unsupported source role")
    expected_kind = "operator_note" if source["role"] == "context_note" else "page"
    if source["kind"] != expected_kind:
        raise _error("source kind/role mismatch")
    source["url"] = _https_url(source["url"], nullable=source["kind"] == "operator_note")
    _string(source["title"], 1, 200, "source title")
    if not isinstance(source["text"], str):
        raise _error("invalid source text")
    text_limit = 2000 if source["kind"] == "operator_note" else 50000
    if len(source["text"]) > text_limit:
        raise _error("source text too long")
    if source["status"] not in {"collected", "empty", "unavailable", "pending"}:
        raise _error("invalid source status")
    if source["status"] == "collected" and not source["text"].strip():
        raise _error("collected source requires text")
    if source["status"] != "collected" and source["text"] != "":
        raise _error("non-collected source must have empty text")
    _utc(source["observed_at"], "observed_at")
    if source["published_at"] is not None:
        _utc(source["published_at"], "published_at")
    if source["provider_date"] is not None and (not isinstance(source["provider_date"], str) or len(source["provider_date"]) > 100):
        raise _error("invalid provider_date")
    if source["record_id_origin"] not in {"provider", "operator", "content_hash", "none"}:
        raise _error("invalid record_id_origin")
    if source["record_id_origin"] == "none":
        if source["record_id"] is not None:
            raise _error("record_id must be null")
    elif not isinstance(source["record_id"], str) or not (1 <= len(source["record_id"]) <= 200):
        raise _error("record_id required")
    if source["provenance"] not in {"synthetic_fixture", "operator_supplied", "operator_claimed_bright_data"}:
        raise _error("invalid provenance")
    canonical, blocks = normalize_text(source["text"])
    source["text"] = canonical
    source["_blocks"] = blocks
    source["_hash"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return source


def _validate(payload: Any) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not isinstance(payload, dict):
        raise _error("input must be an object")
    try:
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise _error("input is not JSON-compatible") from exc
    if len(encoded) > 2 * 1024 * 1024:
        raise _error("input exceeds 2 MiB")
    _exact_keys(payload, {"schema_version", "project", "sources", "scenario", "companies"}, {"as_of"})
    if payload["schema_version"] != "1.0" or payload["project"] != PROJECT:
        raise _error("unsupported schema or project")
    scenario = payload["scenario"]
    if not isinstance(scenario, dict):
        raise _error("scenario must be an object")
    _exact_keys(scenario, {"quantity", "unit", "billing_preference", "required_inclusion"})
    if isinstance(scenario["quantity"], bool) or not isinstance(scenario["quantity"], int) or not (1 <= scenario["quantity"] <= 100000):
        raise _error("invalid quantity")
    if not isinstance(scenario["unit"], str) or not UNIT_RE.fullmatch(scenario["unit"]):
        raise _error("invalid unit")
    if scenario["billing_preference"] not in {"monthly", "annual", "either"}:
        raise _error("invalid billing preference")
    _string(scenario["required_inclusion"], 1, 80, "required inclusion")
    if not isinstance(payload["sources"], list) or len(payload["sources"]) > 100:
        raise _error("invalid sources")
    sources = [_validate_source(item) for item in payload["sources"]]
    if len({item["id"] for item in sources}) != len(sources):
        raise _error("duplicate source id")
    if sum(item["role"] == "context_note" for item in sources) > 5:
        raise _error("too many context notes")
    source_map = {item["id"]: item for item in sources}
    companies = payload["companies"]
    if not isinstance(companies, list) or not (1 <= len(companies) <= 4):
        raise _error("invalid companies")
    company_ids: set[str] = set()
    own_count = 0
    for company in companies:
        if not isinstance(company, dict):
            raise _error("company must be an object")
        _exact_keys(company, {"id", "name", "role", "plans"})
        cid = _identifier(company["id"], "company id")
        if cid in company_ids:
            raise _error("duplicate company id")
        company_ids.add(cid)
        _string(company["name"], 1, 100, "company name")
        if company["role"] not in {"own", "competitor"}:
            raise _error("invalid company role")
        own_count += company["role"] == "own"
        if not isinstance(company["plans"], list) or not (1 <= len(company["plans"]) <= 3):
            raise _error("invalid plans")
        plan_ids: set[str] = set()
        offer_ids: set[str] = set()
        terms_ids: set[str] = set()
        for plan in company["plans"]:
            if not isinstance(plan, dict):
                raise _error("plan must be an object")
            _exact_keys(plan, {"id", "name", "offer_source_id", "heading", "terms_source_ids", "currency_hint"})
            pid = _identifier(plan["id"], "plan id")
            if pid in plan_ids:
                raise _error("duplicate plan id")
            plan_ids.add(pid)
            _string(plan["name"], 1, 80, "plan name")
            offer_id = _identifier(plan["offer_source_id"], "offer_source_id")
            if offer_id not in source_map or source_map[offer_id]["role"] != "offer_page":
                raise _error("invalid offer source reference")
            offer_ids.add(offer_id)
            if plan["heading"] is not None:
                _string(plan["heading"], 1, 120, "heading")
            if not isinstance(plan["terms_source_ids"], list) or len(plan["terms_source_ids"]) > 1 or len(set(plan["terms_source_ids"])) != len(plan["terms_source_ids"]):
                raise _error("invalid terms source references")
            for source_id in plan["terms_source_ids"]:
                _identifier(source_id, "terms source id")
                if source_id not in source_map or source_map[source_id]["role"] != "terms_page":
                    raise _error("invalid terms source reference")
                terms_ids.add(source_id)
            if plan["currency_hint"] is not None and plan["currency_hint"] not in CURRENCIES:
                raise _error("invalid currency hint")
        if len(offer_ids) > 1 or len(terms_ids) > 1:
            raise _error("at most one offer and terms page per company")
    if own_count != 1:
        raise _error("exactly one own company is required")
    if "as_of" in payload:
        _utc(payload["as_of"], "as_of")
    return payload, sources


def _scope(source: dict[str, Any], heading: str | None, *, allow_unheaded: bool = False) -> tuple[list[dict[str, Any]], str | None]:
    blocks = source["_blocks"]
    headings = [index for index, block in enumerate(blocks) if block["heading_level"] is not None]
    if heading is None:
        return (blocks, None) if not headings else ([], "ambiguous_scope")
    if allow_unheaded and not headings:
        return blocks, None
    matches = [index for index in headings if blocks[index]["text"] == heading]
    if len(matches) != 1:
        return [], "ambiguous_scope"
    start = matches[0]
    level = blocks[start]["heading_level"]
    end = len(blocks)
    for index in range(start + 1, len(blocks)):
        next_level = blocks[index]["heading_level"]
        if next_level is not None and next_level <= level:
            end = index
            break
    return [block for block in blocks[start + 1:end] if block["heading_level"] is None], None


def _cite(source: dict[str, Any], block: dict[str, Any]) -> dict[str, str]:
    return {"source_id": source["id"], "block_id": block["id"], "quote": block["text"][:240]}


def _money(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _phrase(feature: str) -> str:
    return re.escape(re.sub(r"\s+", " ", feature.casefold()).strip())


def _analyze_plan(company: dict[str, Any], plan: dict[str, Any], scenario: dict[str, Any], sources: dict[str, dict[str, Any]]) -> dict[str, Any]:
    selected = [sources[plan["offer_source_id"]]] + [sources[item] for item in plan["terms_source_ids"]]
    scoped: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []
    scope_errors = []
    unavailable = False
    for source in selected:
        if source["status"] != "collected":
            unavailable = True
            continue
        blocks, error = _scope(source, plan["heading"], allow_unheaded=source["role"] == "terms_page")
        if error:
            scope_errors.append(error)
        else:
            scoped.append((source, blocks))

    candidates: list[dict[str, Any]] = []
    unsupported_candidates: list[dict[str, Any]] = []
    unsupported_price = bool(scope_errors)
    for source, blocks in scoped:
        for block in blocks:
            text = block["text"]
            match = PRICE_RE.fullmatch(text)
            price_like = bool(re.search(r"(?:USD|EUR|GBP|AUD|CAD|\$)\s*\d", text, re.I) and re.search(r"/(?:month|year)", text, re.I))
            if match:
                amount_text = match.group("amount") + (("." + match.group("cents")) if match.group("cents") else "")
                amount = Decimal(amount_text)
                if amount > Decimal("1000000"):
                    unsupported_price = True
                    unsupported_candidates.append({"text": text, "citation": _cite(source, block)})
                    continue
                candidates.append({
                    "currency_token": match.group("currency") or "$", "amount": amount,
                    "unit": match.group("unit"), "period": match.group("period"),
                    "billed": match.group("billed"), "citation": _cite(source, block), "text": text,
                })
            elif price_like:
                unsupported_price = True
                unsupported_candidates.append({"text": text, "citation": _cite(source, block)})
    unique: list[dict[str, Any]] = []
    seen = set()
    for item in candidates:
        key = (item["currency_token"], item["amount"], item["unit"], item["period"], item["billed"])
        if key not in seen:
            seen.add(key)
            unique.append(item)

    rate_state = "source_unavailable" if unavailable and not scoped else "unsupported_or_ambiguous_price"
    chosen = None
    incompatible_unit = False
    unsupported_billing = False
    currency_conflict = False
    if not unsupported_price and len(unique) == 1:
        chosen = unique[0]
        if chosen["unit"] != scenario["unit"]:
            incompatible_unit = True
            chosen = None
        elif chosen["period"] == "year" and chosen["billed"] == "monthly":
            unsupported_billing = True
            chosen = None
        elif chosen["currency_token"] == "$" and plan["currency_hint"] is None:
            rate_state = "currency_unknown"
        elif chosen["currency_token"] != "$" and plan["currency_hint"] not in {None, chosen["currency_token"]}:
            currency_conflict = True
            chosen = None
        elif chosen["billed"] is None:
            rate_state = "rate_only_billing_unknown"
        else:
            rate_state = "supported"

    evidence: dict[str, list[dict[str, str]]] = {}
    if candidates:
        evidence["price"] = [item["citation"] for item in candidates]
    if unsupported_candidates:
        evidence["price_candidates"] = [item["citation"] for item in unsupported_candidates]
    requested = scenario["quantity"]
    effective = requested
    minimum_refs = []
    for source, blocks in scoped:
        for block in blocks:
            match = MINIMUM_RE.fullmatch(block["text"])
            if match and match.group("unit") == scenario["unit"]:
                effective = max(effective, int(match.group("count")))
                minimum_refs.append(_cite(source, block))
    if minimum_refs:
        evidence["minimum"] = minimum_refs

    feature = _phrase(scenario["required_inclusion"])
    positive_re = re.compile(rf"(?:Includes {feature}\.|{feature} included\.)\Z", re.I)
    negative_re = re.compile(rf"(?:{feature} not included\.|Does not include {feature}\.)\Z", re.I)
    positives, negatives = [], []
    for source, blocks in scoped:
        for block in blocks:
            if positive_re.fullmatch(block["text"]):
                positives.append(_cite(source, block))
            if negative_re.fullmatch(block["text"]):
                negatives.append(_cite(source, block))
    if positives:
        evidence["inclusion_positive"] = positives
    if negatives:
        evidence["inclusion_negative"] = negatives
    if positives and negatives:
        inclusion = "conflicting"
    elif positives:
        inclusion = "explicitly_included"
    elif negatives:
        inclusion = "explicitly_excluded"
    else:
        inclusion = "not_stated"

    currency = None
    observed_price = None
    price_period = None
    billed_period = None
    monthly = None
    due = None
    calculation = None
    if chosen:
        observed_price = _money(chosen["amount"])
        price_period = chosen["period"]
        billed_period = {"monthly": "monthly", "annually": "annual"}.get(chosen["billed"])
        currency = plan["currency_hint"] if chosen["currency_token"] == "$" else chosen["currency_token"]
        if rate_state != "currency_unknown":
            quantity = Decimal(effective)
            if chosen["period"] == "month":
                monthly_value = chosen["amount"] * quantity
                due_value = monthly_value if billed_period == "monthly" else monthly_value * Decimal(12) if billed_period == "annual" else None
            else:
                annual_value = chosen["amount"] * quantity
                monthly_value = annual_value / Decimal(12)
                due_value = annual_value if billed_period == "annual" else None
            monthly = _money(monthly_value)
            due = _money(due_value) if due_value is not None else None
            calculation = {
                "rate": observed_price, "unit": chosen["unit"], "quantity": effective,
                "price_period": price_period, "billed_period": billed_period,
                "monthly_equivalent_is_comparison_only": True,
            }

    compatible_billing = billed_period is not None and (
        scenario["billing_preference"] == "either" or scenario["billing_preference"] == billed_period
    )
    if incompatible_unit or inclusion == "explicitly_excluded" or (billed_period is not None and not compatible_billing):
        scenario_status = "fails_declared_checks"
    elif unavailable or scope_errors:
        scenario_status = "unknown"
    elif rate_state == "supported" and compatible_billing and inclusion == "explicitly_included":
        scenario_status = "meets_declared_checks"
    else:
        scenario_status = "unknown"
    unknown_terms = ["Taxes and fees are not stated in the selected scope.", "Discounts are not inferred."]
    if rate_state != "supported":
        unknown_terms.append("A supported base payment and commitment could not be established.")
    if inclusion in {"not_stated", "conflicting"}:
        unknown_terms.append(f"Whether {scenario['required_inclusion']} is included is not established.")
    if unavailable:
        unknown_terms.append("At least one selected offer or terms source is unavailable.")
    readiness_issues = []
    if scope_errors:
        readiness_issues.append("scope")
    if unavailable:
        readiness_issues.append("selected_source")
    if unsupported_price or len(unique) != 1 or rate_state == "currency_unknown" or currency_conflict:
        readiness_issues.append("price")
    if len(unique) == 1 and (unique[0]["billed"] is None or unsupported_billing):
        readiness_issues.append("billing")
    if inclusion in {"not_stated", "conflicting"}:
        readiness_issues.append("inclusion")
    observed_unit = unique[0]["unit"] if len(unique) == 1 else scenario["unit"]
    return {
        "company_id": company["id"], "company_name": company["name"], "role": company["role"],
        "plan_id": plan["id"], "plan_name": plan["name"],
        "scope": {"source_ids": [item["id"] for item in selected], "heading": plan["heading"]},
        "observed_price": observed_price, "price_candidates": [item["text"] for item in unsupported_candidates],
        "currency": currency, "unit": observed_unit,
        "price_period": price_period, "billed_period": billed_period,
        "requested_quantity": requested, "effective_quantity": effective,
        "rate_state": rate_state, "monthly_equivalent": monthly,
        "base_due_per_billing_period": due, "calculation": calculation,
        "inclusion_state": inclusion, "scenario_status": scenario_status,
        "readiness_issues": readiness_issues, "unknown_terms": unknown_terms, "evidence": evidence,
    }


def _analyze(payload: dict) -> dict:
    payload, normalized = _validate(payload)
    source_map = {item["id"]: item for item in normalized}
    selected_ids = []
    for company in payload["companies"]:
        for plan in company["plans"]:
            for source_id in [plan["offer_source_id"], *plan["terms_source_ids"]]:
                if source_id not in selected_ids:
                    selected_ids.append(source_id)
    selected_set = set(selected_ids)
    selected = [item for item in normalized if item["id"] in selected_set]
    unreferenced = [item for item in normalized if item["id"] not in selected_set]
    rows = []
    for company in payload["companies"]:
        for plan in company["plans"]:
            rows.append(_analyze_plan(company, plan, payload["scenario"], source_map))
    as_of_value = payload.get("as_of")
    if as_of_value is None and selected:
        as_of_value = max(selected, key=lambda item: _utc(item["observed_at"], "observed_at"))["observed_at"]
    warnings = []
    if unreferenced:
        warnings.append({
            "code": "unreferenced_source", "source_ids": [item["id"] for item in unreferenced],
            "note": "These supplied sources were not selected by any plan and were excluded from analysis counts and status.",
        })
    if as_of_value:
        as_of = _utc(as_of_value, "as_of")
        stale = [item["id"] for item in selected if as_of - _utc(item["observed_at"], "observed_at") > timedelta(days=30)]
        if stale:
            warnings.append({"code": "stale_source", "source_ids": stale, "note": "Selected snapshots are more than 30 days older than as_of."})
    if (
        any(item["status"] != "collected" for item in selected)
        or any(row["readiness_issues"] for row in rows)
    ):
        status = "needs_review"
    else:
        status = "ok"
    own_notes = []
    feature = payload["scenario"]["required_inclusion"]
    for row in rows:
        if row["role"] != "own":
            continue
        if row["inclusion_state"] == "not_stated":
            own_notes.append(f"State whether {feature} is included.")
        elif row["inclusion_state"] == "conflicting":
            own_notes.append(f"Resolve conflicting statements about whether {feature} is included.")
        if row["rate_state"] != "supported":
            own_notes.append("State a supported base rate and billing commitment for this scenario.")
    source_index = [{
        "id": item["id"], "role": item["role"], "url": item["url"], "status": item["status"],
        "observed_at": item["observed_at"], "published_at": item["published_at"],
        "provider_date": item["provider_date"], "record_id": item["record_id"],
        "record_id_origin": item["record_id_origin"], "content_sha256": item["_hash"],
        "provenance": item["provenance"],
    } for item in normalized]
    return {
        "schema_version": "1.0", "project": PROJECT, "analysis_method": "deterministic_rules_v1",
        "provenance_notice": PROVENANCE_NOTICE,
        "status": status, "decision": "scenario_worksheet",
        "scope": {"scenario": dict(payload["scenario"]), "source_ids": selected_ids, "as_of": as_of_value},
        "summary": {"analyzed_sources": len(selected), "excluded_sources": len(unreferenced), "output_rows": len(rows)},
        "warnings": warnings, "source_index": source_index, "offers": rows, "own_clarity_notes": own_notes,
    }


def analyze(payload: dict) -> dict:
    """Analyze caller-provided data; bright_data provenance is not trusted here."""
    return _analyze(payload)


def analyze_with_library(payload: dict, library: dict) -> dict:
    """Analyze an appended library, preserving provider origin only as an unverified claim."""
    if not isinstance(library, dict) or set(library) != {
        "schema_version", "project", "transport_contract_version", "provenance_notice", "sources", "receipt",
    }:
        raise _error("invalid source library")
    if (
        library["schema_version"] != "1.0"
        or library["project"] != PROJECT
        or library["transport_contract_version"] != "1.0"
        or library["provenance_notice"] != PROVENANCE_NOTICE
        or not isinstance(library["sources"], list)
        or not isinstance(library["receipt"], dict)
    ):
        raise _error("invalid source library")
    receipt = library["receipt"]
    receipt_keys = {
        "schema_version", "project", "manifest_sha256", "status", "requests_made",
        "returned_records", "retained_records", "excluded_records", "jobs", "warnings", "provider_cost_usd",
    }
    if (
        set(receipt) != receipt_keys
        or
        receipt.get("schema_version") != "1.0"
        or receipt.get("project") != PROJECT
        or receipt.get("status") not in {"complete", "partial"}
        or isinstance(receipt.get("requests_made"), bool)
        or not isinstance(receipt.get("requests_made"), int)
        or receipt["requests_made"] < 0
        or any(
            isinstance(receipt.get(key), bool) or not isinstance(receipt.get(key), int) or receipt[key] < 0
            for key in ("returned_records", "retained_records", "excluded_records")
        )
        or not isinstance(receipt.get("jobs"), list)
        or not isinstance(receipt.get("warnings"), list)
        or receipt.get("provider_cost_usd") is not None
        or (receipt.get("manifest_sha256") is not None and not re.fullmatch(r"[0-9a-f]{64}", str(receipt["manifest_sha256"])))
    ):
        raise _error("invalid collection receipt")
    completed_jobs = {}
    for job_receipt in receipt["jobs"]:
        if not isinstance(job_receipt, dict) or job_receipt.get("state") not in {"complete", "empty"}:
            continue
        original = job_receipt.get("original_job")
        if not isinstance(original, dict):
            continue
        source_id = original.get("source_id")
        if isinstance(source_id, str):
            completed_jobs[source_id] = (original.get("role"), original.get("url"), job_receipt.get("state"))
    has_claim = any(
        isinstance(source, dict) and source.get("provenance") == "operator_claimed_bright_data"
        for source in library["sources"]
    )
    if has_claim and (receipt["manifest_sha256"] is None or receipt["requests_made"] < 1):
        raise _error("provider-origin claim requires a non-offline collection receipt")
    for source in library["sources"]:
        if not isinstance(source, dict):
            continue
        if source.get("provenance") not in {"bright_data", "bright_data_transport", "operator_claimed_bright_data"}:
            continue
        match = completed_jobs.get(source.get("id"))
        if (
            match is None
            or match[0] != source.get("role")
            or match[1] != source.get("url")
            or (source.get("status") == "collected" and match[2] != "complete")
            or (source.get("status") == "empty" and match[2] not in {"complete", "empty"})
        ):
            raise _error("provider-origin claim lacks a matching successful receipt job")
    if not isinstance(payload, dict):
        raise _error("input must be an object")
    combined = dict(payload)
    base_sources = payload.get("sources")
    if not isinstance(base_sources, list):
        raise _error("invalid sources")
    base_ids = {item.get("id") for item in base_sources if isinstance(item, dict)}
    library_ids = {item.get("id") for item in library["sources"] if isinstance(item, dict)}
    if len(library_ids) != len(library["sources"]) or base_ids & library_ids:
        raise _error("duplicate source id")
    appended_sources = []
    for item in library["sources"]:
        source = dict(item)
        if source.get("provenance") in {"bright_data", "bright_data_transport"}:
            source["provenance"] = "operator_claimed_bright_data"
        appended_sources.append(source)
    combined["sources"] = base_sources + appended_sources
    if len(combined["sources"]) > 100:
        raise _error("too many sources")
    return _analyze(combined)
