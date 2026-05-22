import json
import re
from copy import deepcopy
from typing import Callable, Dict, Iterable, List, Optional
from urllib.parse import urlparse

from artifacts import extract_artifacts, flatten_artifacts
from sources import search_sources

CONSERVATIVE_LIMIT = 12
EXPLORATORY_LIMIT = 20
EXPLORATORY_INITIAL_LIMIT = 14
EXPLORATORY_PIVOT_RESERVE = 6
ALLOWED_MODES = {"off", "conservative", "exploratory"}
ALLOWED_INTENTS = {
    "person_name",
    "handle",
    "email_or_domain",
    "org_or_brand",
    "technical_ioc",
    "freeform_threat",
}
ALLOWED_QUERY_TYPES = {
    "refined",
    "exact",
    "alias",
    "context",
    "ai_probe",
    "sensitive_probe",
    "artifact_pivot",
}
SENSITIVE_PERSON_TERMS = {
    "ssn",
    "social security",
    "dob",
    "date of birth",
    "birthdate",
    "phone",
    "telephone",
    "mobile",
    "address",
    "home address",
}
GENERIC_INFRASTRUCTURE_TERMS = {
    "market",
    "forum",
    "forums",
    "hacking",
    "hackers",
    "database",
    "search",
    "combo",
    "breach",
    "leak market",
    "darkbay",
}
HANDLE_LIKE_RE = re.compile(r"^@?[A-Za-z0-9][A-Za-z0-9_-]{2,63}$")


def normalize_mode(mode: Optional[str]) -> str:
    value = (mode or "conservative").strip().lower()
    if value in ("disabled", "none"):
        return "off"
    if value not in ALLOWED_MODES:
        return "conservative"
    return value


def mode_limit(mode: Optional[str]) -> int:
    return EXPLORATORY_LIMIT if normalize_mode(mode) == "exploratory" else CONSERVATIVE_LIMIT


def initial_query_limit(mode: Optional[str]) -> int:
    return EXPLORATORY_INITIAL_LIMIT if normalize_mode(mode) == "exploratory" else CONSERVATIVE_LIMIT


def normalize_search_intent(intent: Optional[str]) -> str:
    value = (intent or "").strip().lower()
    return value if value in ALLOWED_INTENTS else "freeform_threat"


def classify_search_intent(query: str, context: Optional[Dict[str, str]] = None) -> Dict[str, object]:
    text = _clean_query(query)
    context = context or {}
    lower = text.lower()
    reasons = []

    if context.get("organization"):
        reasons.append("Organization context was provided.")
        return {"intent": "org_or_brand", "confidence": "high", "reasons": reasons}
    if context.get("handles"):
        reasons.append("Handle context was provided.")
        return {"intent": "handle", "confidence": "high", "reasons": reasons}
    if context.get("emails_domains"):
        reasons.append("Email/domain context was provided.")
        return {"intent": "email_or_domain", "confidence": "high", "reasons": reasons}

    if re.search(r"\bCVE-\d{4}-\d{4,}\b", text, re.IGNORECASE):
        reasons.append("Query contains a CVE identifier.")
        return {"intent": "technical_ioc", "confidence": "high", "reasons": reasons}
    if re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", text):
        reasons.append("Query contains an IPv4 address.")
        return {"intent": "technical_ioc", "confidence": "high", "reasons": reasons}
    if re.search(r"\b[a-fA-F0-9]{32,64}\b", text):
        reasons.append("Query contains a hash-like value.")
        return {"intent": "technical_ioc", "confidence": "high", "reasons": reasons}
    if ".onion" in lower or re.search(r"\b(?:bc1|[13])[a-zA-HJ-NP-Z0-9]{25,}\b", text):
        reasons.append("Query contains an onion URL or crypto-address-like value.")
        return {"intent": "technical_ioc", "confidence": "high", "reasons": reasons}
    if re.search(r"[\w.+-]+@[\w.-]+\.[a-z]{2,}", lower) or re.search(r"\b[a-z0-9-]+(?:\.[a-z0-9-]+)+\b", lower):
        reasons.append("Query contains an email address or domain.")
        return {"intent": "email_or_domain", "confidence": "high", "reasons": reasons}
    if text.startswith("@"):
        reasons.append("Query starts with a handle marker.")
        return {"intent": "handle", "confidence": "high", "reasons": reasons}
    if _looks_like_handle(text):
        reasons.append("Query looks like a single username or handle.")
        return {"intent": "handle", "confidence": "medium", "reasons": reasons}

    tokens = re.findall(r"[A-Za-z][A-Za-z'.-]*", text)
    if 2 <= len(tokens) <= 4 and all(token[:1].isupper() for token in tokens):
        reasons.append("Query looks like a 2-4 token capitalized personal name.")
        return {"intent": "person_name", "confidence": "medium", "reasons": reasons}

    org_markers = (" inc", " llc", " ltd", " corp", " company", " bank", " exchange", " university")
    if any(marker in f" {lower}" for marker in org_markers):
        reasons.append("Query contains organization-style wording.")
        return {"intent": "org_or_brand", "confidence": "medium", "reasons": reasons}

    reasons.append("No specific identifier pattern matched; using broad threat-search behavior.")
    return {"intent": "freeform_threat", "confidence": "low", "reasons": reasons}


def build_expansion_context(
    aliases: str = "",
    handles: str = "",
    emails_domains: str = "",
    geography: str = "",
    organization: str = "",
    timeframe: str = "",
    freeform: str = "",
) -> Dict[str, str]:
    return {
        "aliases": (aliases or "").strip(),
        "handles": (handles or "").strip(),
        "emails_domains": (emails_domains or "").strip(),
        "geography": (geography or "").strip(),
        "organization": (organization or "").strip(),
        "timeframe": (timeframe or "").strip(),
        "freeform": (freeform or "").strip(),
    }


def single_query_plan(
    base_query: str,
    refined_query: str,
    mode: str = "off",
    search_intent: Optional[str] = None,
    inferred_intent: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    query = _clean_query(refined_query or base_query)
    inferred = inferred_intent or classify_search_intent(base_query)
    selected_intent = normalize_search_intent(search_intent or str(inferred.get("intent") or "freeform_threat"))
    return {
        "mode": normalize_mode(mode),
        "base_query": base_query,
        "refined_query": refined_query,
        "inferred_intent": inferred,
        "selected_intent": selected_intent,
        "initial_query_limit": 1,
        "artifact_pivot_reserve": 0,
        "sensitive_probes_used": 0,
        "sensitive_probes_suppressed": 0,
        "queries": [
            {
                "query": query,
                "query_type": "refined",
                "reason": "Single refined query.",
                "phase": "initial",
                "origin": "system",
                "intent": selected_intent,
                "sensitive": False,
            }
        ],
        "warnings": [],
    }


def generate_query_plan(
    llm,
    base_query: str,
    refined_query: str,
    context: Optional[Dict[str, str]] = None,
    mode: str = "conservative",
    search_intent: Optional[str] = None,
    reporting_preset: Optional[str] = None,
) -> Dict[str, object]:
    normalized_mode = normalize_mode(mode)
    context = context or {}
    inferred = classify_search_intent(base_query, context)
    selected_intent = normalize_search_intent(search_intent or str(inferred.get("intent") or "freeform_threat"))
    if normalized_mode == "off":
        return single_query_plan(
            base_query,
            refined_query,
            mode="off",
            search_intent=selected_intent,
            inferred_intent=inferred,
        )

    fallback = _deterministic_initial_queries(base_query, refined_query, context, selected_intent, normalized_mode)
    prompt = _query_plan_prompt(
        base_query,
        refined_query,
        context,
        normalized_mode,
        selected_intent,
        reporting_preset,
    )
    warnings: List[str] = []

    try:
        raw_output = _invoke_llm_text(llm, prompt)
        ai_queries = parse_query_plan_output(raw_output)
    except Exception as exc:
        ai_queries = []
        warnings.append(f"AI query plan fallback used: {exc.__class__.__name__}")

    queries, policy_warnings = _apply_query_policy(
        fallback + ai_queries,
        selected_intent,
        normalized_mode,
        context,
        base_query=base_query,
    )
    warnings.extend(policy_warnings)
    queries = _cap_query_entries(queries, initial_query_limit(normalized_mode))
    if not queries:
        queries = single_query_plan(
            base_query,
            refined_query,
            mode=normalized_mode,
            search_intent=selected_intent,
            inferred_intent=inferred,
        )["queries"]

    return {
        "mode": normalized_mode,
        "base_query": base_query,
        "refined_query": refined_query,
        "context": context,
        "inferred_intent": inferred,
        "selected_intent": selected_intent,
        "reporting_preset": reporting_preset or "",
        "initial_query_limit": initial_query_limit(normalized_mode),
        "artifact_pivot_reserve": EXPLORATORY_PIVOT_RESERVE if normalized_mode == "exploratory" else 0,
        "sensitive_probes_used": sum(1 for item in queries if item.get("query_type") == "sensitive_probe"),
        "sensitive_probes_suppressed": sum(1 for warning in warnings if "suppressed sensitive" in warning.lower()),
        "queries": queries,
        "warnings": warnings,
    }


def parse_query_plan_output(raw_output: str) -> List[Dict[str, str]]:
    payload = _extract_json(raw_output or "")
    raw_queries = payload if isinstance(payload, list) else payload.get("queries", [])
    if not isinstance(raw_queries, list):
        return []

    entries = []
    for item in raw_queries:
        if not isinstance(item, dict):
            continue
        query = _clean_query(str(item.get("query") or ""))
        if not query:
            continue
        query_type = str(item.get("query_type") or item.get("type") or "ai_probe").strip().lower()
        if query_type not in ALLOWED_QUERY_TYPES:
            query_type = "ai_probe"
        entries.append(
            {
                "query": query,
                "query_type": query_type,
                "reason": _short_reason(item.get("reason") or "AI-suggested search probe."),
                "phase": str(item.get("phase") or "initial").strip().lower() or "initial",
                "origin": "ai",
                "sensitive": query_type == "sensitive_probe" or bool(item.get("sensitive")),
            }
        )
    return entries


def search_query_entries(
    query_entries: Iterable[Dict[str, str]],
    max_workers: int = 5,
    search_fn: Callable[..., Dict[str, object]] = search_sources,
    base_query: str = "",
    context: Optional[Dict[str, str]] = None,
    search_intent: str = "freeform_threat",
) -> Dict[str, object]:
    merged_results: Dict[str, Dict[str, object]] = {}
    query_runs = []
    search_status = []

    for query_entry in query_entries:
        query = query_entry.get("query", "")
        if not query:
            continue
        payload = search_fn(query, max_workers=max_workers)
        results = list(payload.get("results", []))
        statuses = []
        for status in payload.get("sources", []):
            enriched_status = dict(status)
            enriched_status["query"] = query
            enriched_status["query_type"] = query_entry.get("query_type", "")
            enriched_status["query_reason"] = query_entry.get("reason", "")
            enriched_status["intent"] = query_entry.get("intent", search_intent)
            enriched_status["origin"] = query_entry.get("origin", "")
            enriched_status["sensitive"] = bool(query_entry.get("sensitive"))
            statuses.append(enriched_status)
        search_status.extend(statuses)

        for result in results:
            annotated = annotate_result_quality(result, base_query, context, search_intent)
            _merge_result(merged_results, annotated, query_entry)

        query_runs.append(
            {
                "query": query,
                "query_type": query_entry.get("query_type", ""),
                "reason": query_entry.get("reason", ""),
                "phase": query_entry.get("phase", "initial"),
                "intent": query_entry.get("intent", search_intent),
                "origin": query_entry.get("origin", ""),
                "sensitive": bool(query_entry.get("sensitive")),
                "result_count": len(results),
                "status_counts": _status_counts(statuses),
            }
        )

    return {
        "results": rank_results_by_quality(list(merged_results.values())),
        "sources": search_status,
        "query_runs": query_runs,
    }


def run_expanded_search(
    llm,
    base_query: str,
    refined_query: str,
    context: Optional[Dict[str, str]] = None,
    mode: str = "conservative",
    search_intent: Optional[str] = None,
    reporting_preset: Optional[str] = None,
    max_workers: int = 5,
    search_fn: Callable[..., Dict[str, object]] = search_sources,
) -> Dict[str, object]:
    normalized_mode = normalize_mode(mode)
    context = context or {}
    query_plan = generate_query_plan(
        llm,
        base_query,
        refined_query,
        context,
        normalized_mode,
        search_intent=search_intent,
        reporting_preset=reporting_preset,
    )
    selected_intent = str(query_plan.get("selected_intent") or "freeform_threat")
    payload = search_query_entries(
        query_plan.get("queries", []),
        max_workers=max_workers,
        search_fn=search_fn,
        base_query=base_query,
        context=context,
        search_intent=selected_intent,
    )

    if normalized_mode == "exploratory":
        remaining = max(0, mode_limit(normalized_mode) - len(query_plan.get("queries", [])))
        if remaining:
            artifacts = extract_artifacts(search_results=payload.get("results", []))
            pivots = generate_artifact_pivot_queries(
                llm,
                base_query=base_query,
                refined_query=refined_query,
                artifacts=artifacts,
                existing_queries=[item.get("query", "") for item in query_plan.get("queries", [])],
                limit=remaining,
                search_intent=selected_intent,
            )
            if pivots:
                query_plan["queries"].extend(pivots)
                pivot_payload = search_query_entries(
                    pivots,
                    max_workers=max_workers,
                    search_fn=search_fn,
                    base_query=base_query,
                    context=context,
                    search_intent=selected_intent,
                )
                payload = merge_search_payloads(payload, pivot_payload)

    payload["results"] = rank_results_by_quality(payload.get("results", []))
    payload["qualified_results"] = filter_qualified_results(payload["results"], selected_intent)
    payload["query_plan"] = query_plan
    payload["query_expansion_mode"] = normalized_mode
    return payload


def generate_artifact_pivot_queries(
    llm,
    base_query: str,
    refined_query: str,
    artifacts: Dict[str, List[Dict[str, str]]],
    existing_queries: Iterable[str],
    limit: int,
    search_intent: str = "freeform_threat",
) -> List[Dict[str, str]]:
    flattened = flatten_artifacts(artifacts or {})
    if not flattened or limit <= 0:
        return []

    fallback = _deterministic_artifact_pivots(refined_query or base_query, flattened)
    prompt = _artifact_pivot_prompt(base_query, refined_query, flattened, existing_queries, limit)
    try:
        ai_pivots = parse_query_plan_output(_invoke_llm_text(llm, prompt))
    except Exception:
        ai_pivots = []

    entries = []
    for item in ai_pivots + fallback:
        item = dict(item)
        item["query_type"] = "artifact_pivot"
        item["phase"] = "artifact_pivot"
        item["intent"] = search_intent
        item["sensitive"] = False
        entries.append(item)
    return _cap_query_entries(_dedupe_query_entries(entries), limit)


def merge_search_payloads(left: Dict[str, object], right: Dict[str, object]) -> Dict[str, object]:
    merged_results: Dict[str, Dict[str, object]] = {}
    for result in left.get("results", []):
        _merge_result(merged_results, result, _first_query_entry(result))
    for result in right.get("results", []):
        _merge_result(merged_results, result, _first_query_entry(result))
    return {
        "results": rank_results_by_quality(list(merged_results.values())),
        "sources": list(left.get("sources", [])) + list(right.get("sources", [])),
        "query_runs": list(left.get("query_runs", [])) + list(right.get("query_runs", [])),
    }


def annotate_result_quality(
    result: Dict[str, object],
    base_query: str,
    context: Optional[Dict[str, str]] = None,
    search_intent: str = "freeform_threat",
    scraped_text: str = "",
) -> Dict[str, object]:
    item = dict(result)
    terms = _quality_terms(base_query, context or {}, search_intent)
    haystack_parts = [
        str(item.get("title") or ""),
        str(item.get("snippet") or ""),
        str(item.get("link") or ""),
        str(scraped_text or ""),
    ]
    haystack = " ".join(haystack_parts).lower()
    matched_terms = [term for term in terms if term and term.lower() in haystack]
    title_snippet = f"{item.get('title', '')} {item.get('snippet', '')}".lower()
    link = str(item.get("link") or "").lower()
    generic_hit = any(term in title_snippet for term in GENERIC_INFRASTRUCTURE_TERMS)
    direct = bool(matched_terms)
    infrastructure_only = bool(generic_hit and not direct)
    score = 0
    if direct:
        score += 50
    if scraped_text and direct:
        score += 20
    if item.get("query_type") in ("exact", "alias", "context"):
        score += 8
    if infrastructure_only:
        score -= 20
    if search_intent in ("technical_ioc", "email_or_domain", "handle") and direct:
        score += 15
    item["quality"] = {
        "search_intent": search_intent,
        "direct_mention": direct,
        "matched_terms": matched_terms,
        "infrastructure_only": infrastructure_only,
        "no_direct_mention": not direct,
        "score": score,
    }
    return item


def filter_qualified_results(results: Iterable[Dict[str, object]], search_intent: str) -> List[Dict[str, object]]:
    ranked = rank_results_by_quality(results or [])
    intent = normalize_search_intent(search_intent)
    if intent not in ("person_name", "handle", "email_or_domain", "technical_ioc"):
        return ranked
    return [item for item in ranked if (item.get("quality") or {}).get("direct_mention")]


def annotate_results_with_scraped_content(
    results: Iterable[Dict[str, object]],
    scraped_content: Dict[str, str],
    base_query: str,
    context: Optional[Dict[str, str]] = None,
    search_intent: str = "freeform_threat",
) -> List[Dict[str, object]]:
    annotated = []
    scraped_content = scraped_content or {}
    for result in results:
        link = str(result.get("link") or "")
        scraped_text = scraped_content.get(link, "")
        annotated.append(annotate_result_quality(result, base_query, context, search_intent, scraped_text=scraped_text))
    return rank_results_by_quality(annotated)


def rank_results_by_quality(results: Iterable[Dict[str, object]]) -> List[Dict[str, object]]:
    indexed = list(enumerate(results or []))
    indexed.sort(
        key=lambda pair: (
            int(((pair[1].get("quality") or {}).get("score") or 0)),
            len(pair[1].get("matched_queries") or []),
            -pair[0],
        ),
        reverse=True,
    )
    return [item for _, item in indexed]


def _invoke_llm_text(llm, prompt: str) -> str:
    response = llm.invoke(prompt)
    return str(getattr(response, "content", response) or "")


def _extract_json(raw_output: str):
    text = raw_output.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.IGNORECASE | re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    if not text.startswith(("{", "[")):
        start_positions = [pos for pos in (text.find("{"), text.find("[")) if pos >= 0]
        if start_positions:
            start = min(start_positions)
            end = max(text.rfind("}"), text.rfind("]"))
            text = text[start : end + 1]
    data = json.loads(text)
    return data


def _deterministic_initial_queries(
    base_query: str,
    refined_query: str,
    context: Dict[str, str],
    search_intent: str,
    mode: str,
) -> List[Dict[str, str]]:
    base = _clean_query(base_query)
    refined = _clean_query(refined_query or base_query)
    entries = [
        _entry(refined, "refined", "Refined baseline query.", origin="system", intent=search_intent),
        _entry(f'"{base}"', "exact", "Exact-match original query.", origin="system", intent=search_intent),
    ]

    aliases = _split_context_values(context.get("aliases", ""))
    handles = _split_context_values(context.get("handles", ""))
    emails_domains = _split_context_values(context.get("emails_domains", ""))
    geography = _clean_query(context.get("geography", ""))
    organization = _clean_query(context.get("organization", ""))
    timeframe = _clean_query(context.get("timeframe", ""))

    for value in aliases[:4]:
        entries.append(_entry(f'"{value}"', "alias", "User-provided alias or name variant.", origin="user", intent=search_intent))
        if geography:
            entries.append(_entry(f'"{value}" {geography}', "context", "Alias constrained by geography.", origin="user", intent=search_intent))
        if organization:
            entries.append(_entry(f'"{value}" {organization}', "context", "Alias constrained by organization.", origin="user", intent=search_intent))

    for value in handles[:4]:
        entries.append(_entry(value, "context", "User-provided handle.", origin="user", intent=search_intent))
    for value in emails_domains[:4]:
        entries.append(_entry(value, "context", "User-provided email or domain.", origin="user", intent=search_intent))
    if geography:
        entries.append(_entry(f"{refined} {geography}", "context", "Refined query constrained by geography.", origin="user", intent=search_intent))
    if organization:
        entries.append(_entry(f"{refined} {organization}", "context", "Refined query constrained by organization.", origin="user", intent=search_intent))
    if timeframe:
        entries.append(_entry(f"{refined} {timeframe}", "context", "Refined query constrained by timeframe.", origin="user", intent=search_intent))

    if search_intent == "person_name":
        tokens = _split_name_tokens(base)
        if len(tokens) >= 2:
            entries.append(_entry(f'"{tokens[0]}" "{tokens[-1]}"', "alias", "Split-name exact token variant.", intent=search_intent))
        for term in ("leak", "breach", "paste", "forum"):
            entries.append(_entry(f'"{base}" {term}', "ai_probe", f"Low-risk person-name probe for {term} mentions.", intent=search_intent))
        if normalize_mode(mode) == "exploratory":
            for term in ("phone", "address", "DOB", "SSN"):
                entries.append(
                    _entry(
                        f'"{base}" "{term}"',
                        "sensitive_probe",
                        f"Exploratory person-exposure probe for {term}.",
                        intent=search_intent,
                        sensitive=True,
                    )
                )
    elif search_intent == "handle":
        entries.append(_entry(f'"{base}" leak', "ai_probe", "Handle constrained by leak keyword.", intent=search_intent))
        entries.append(_entry(f'"{base}" forum', "ai_probe", "Handle constrained by forum keyword.", intent=search_intent))
    elif search_intent == "email_or_domain":
        entries.append(_entry(f'"{base}"', "exact", "Exact email/domain artifact query.", intent=search_intent))
        entries.append(_entry(f'"{base}" breach', "ai_probe", "Email/domain constrained by breach keyword.", intent=search_intent))
    elif search_intent == "technical_ioc":
        entries.append(_entry(f'"{base}"', "exact", "Exact technical indicator query.", intent=search_intent))
    elif search_intent == "org_or_brand":
        for term in ("leak", "breach", "ransomware", "paste", "source code", "credentials", "employee data", "customer data"):
            entries.append(_entry(f'"{base}" {term}', "ai_probe", f"Organization-focused {term} pivot.", intent=search_intent))

    return [item for item in entries if item["query"]]


def _deterministic_artifact_pivots(base_query: str, flattened_artifacts: List[Dict[str, str]]) -> List[Dict[str, str]]:
    entries = []
    for artifact in flattened_artifacts[:8]:
        value = _clean_query(str(artifact.get("value") or ""))
        if not value:
            continue
        entries.append(
            _entry(
                f'"{value}"',
                "artifact_pivot",
                f"Pivot on extracted {artifact.get('type', 'artifact')}.",
                phase="artifact_pivot",
                origin="system",
            )
        )
        if base_query:
            entries.append(
                _entry(
                    f'"{value}" {base_query}',
                    "artifact_pivot",
                    "Pivot on artifact constrained by the original topic.",
                    phase="artifact_pivot",
                    origin="system",
                )
            )
    return entries


def _query_plan_prompt(
    base_query: str,
    refined_query: str,
    context: Dict[str, str],
    mode: str,
    search_intent: str,
    reporting_preset: Optional[str],
) -> str:
    max_queries = initial_query_limit(mode)
    sensitive_rule = (
        "For person_name Conservative mode, do not generate SSN, DOB, phone, address, or equivalent sensitive probes unless they are explicitly in user context."
        if normalize_mode(mode) == "conservative"
        else "For person_name Exploratory mode, sensitive probes may be used sparingly and must be query_type sensitive_probe."
    )
    return f"""
You are planning bounded dark-web search queries for a single-user OSINT tool.
Return only JSON with this shape:
{{"queries":[{{"query":"...","query_type":"exact|alias|context|ai_probe|sensitive_probe","reason":"short reason"}}]}}

Rules:
- Produce at most {max_queries} total query objects.
- Prioritize user-provided context over speculation.
- Include 3 to 6 AI-suggested probe queries when useful.
- Keep each query concise enough for basic onion search engines.
- Do not include instructions, explanations, or markdown outside JSON.
- Do not invent private facts; speculative probes must be generic and labeled ai_probe.
- Search intent controls query strategy; reporting preset controls only the final report style.
- {sensitive_rule}

Base query: {base_query}
Refined query: {refined_query}
Mode: {mode}
Search intent: {search_intent}
Reporting preset: {reporting_preset or ""}
Optional context JSON:
{json.dumps(context or {}, indent=2)}
""".strip()


def _artifact_pivot_prompt(
    base_query: str,
    refined_query: str,
    flattened_artifacts: List[Dict[str, str]],
    existing_queries: Iterable[str],
    limit: int,
) -> str:
    return f"""
You are planning second-pass dark-web search pivots from deterministic artifacts.
Return only JSON with this shape:
{{"queries":[{{"query":"...","query_type":"artifact_pivot","reason":"short reason"}}]}}

Rules:
- Produce at most {limit} query objects.
- Use only artifact values provided below.
- Do not repeat existing queries.
- Keep each query concise and useful for onion search engines.

Base query: {base_query}
Refined query: {refined_query}
Existing queries: {json.dumps(list(existing_queries), indent=2)}
Artifacts:
{json.dumps(flattened_artifacts[:20], indent=2)}
""".strip()


def _split_context_values(value: str) -> List[str]:
    return [_clean_query(part) for part in re.split(r"[,;\n]+", value or "") if _clean_query(part)]


def _split_name_tokens(value: str) -> List[str]:
    return re.findall(r"[A-Za-z][A-Za-z'.-]*", value or "")


def _context_allows_sensitive(context: Dict[str, str]) -> bool:
    text = " ".join(str(value or "") for value in (context or {}).values()).lower()
    return any(term in text for term in SENSITIVE_PERSON_TERMS)


def _is_sensitive_query(entry: Dict[str, object]) -> bool:
    query = str(entry.get("query") or "").lower()
    return bool(entry.get("sensitive")) or entry.get("query_type") == "sensitive_probe" or any(
        term in query for term in SENSITIVE_PERSON_TERMS
    )


def _apply_query_policy(
    entries: Iterable[Dict[str, str]],
    search_intent: str,
    mode: str,
    context: Dict[str, str],
    base_query: str = "",
) -> tuple[List[Dict[str, str]], List[str]]:
    warnings = []
    normalized_mode = normalize_mode(mode)
    allow_sensitive = search_intent != "person_name" or normalized_mode == "exploratory" or _context_allows_sensitive(context)
    handle_policy_terms = _handle_policy_terms(base_query, context)
    clean_entries = []
    suppressed = 0
    suppressed_weak_handle = 0

    for entry in entries:
        item = dict(entry)
        item["intent"] = normalize_search_intent(item.get("intent") or search_intent)
        if item["intent"] != search_intent:
            item["intent"] = search_intent
        sensitive = _is_sensitive_query(item)
        if search_intent == "person_name" and sensitive and not allow_sensitive:
            suppressed += 1
            continue
        if search_intent == "handle" and item.get("origin") != "user":
            normalized_query = _normalize_match_text(str(item.get("query") or ""))
            if handle_policy_terms and not any(term in normalized_query for term in handle_policy_terms):
                suppressed_weak_handle += 1
                continue
        if sensitive:
            item["query_type"] = "sensitive_probe"
            item["sensitive"] = True
        clean_entries.append(item)

    if suppressed:
        warnings.append(f"Suppressed sensitive person-name probes: {suppressed}")
    if suppressed_weak_handle:
        warnings.append(f"Suppressed weak handle probes without exact identifier: {suppressed_weak_handle}")
    return _dedupe_query_entries(clean_entries), warnings


def _quality_terms(base_query: str, context: Dict[str, str], search_intent: str = "freeform_threat") -> List[str]:
    terms = []
    base = _clean_query(base_query)
    intent = normalize_search_intent(search_intent)
    if base:
        terms.append(base)
    if intent == "handle":
        if base and not base.startswith("@"):
            terms.append(f"@{base}")
        terms.extend(_split_context_values(context.get("handles", "")))
        terms.extend(_split_context_values(context.get("emails_domains", "")))
    elif intent == "person_name":
        terms.extend(_split_context_values(context.get("aliases", "")))
        terms.extend(_split_context_values(context.get("handles", "")))
        terms.extend(_split_context_values(context.get("emails_domains", "")))
    elif intent in ("email_or_domain", "technical_ioc"):
        terms.extend(_split_context_values(context.get("handles", "")))
        terms.extend(_split_context_values(context.get("emails_domains", "")))
    else:
        for key in ("aliases", "handles", "emails_domains", "organization"):
            terms.extend(_split_context_values(context.get(key, "")))
    seen = set()
    unique = []
    for term in terms:
        key = term.lower()
        if key and key not in seen:
            seen.add(key)
            unique.append(term)
    return unique


def _looks_like_handle(text: str) -> bool:
    value = _clean_query(text)
    if " " in value or "." in value:
        return False
    if "_" not in value and "-" not in value:
        return False
    return bool(HANDLE_LIKE_RE.fullmatch(value))


def _normalize_match_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower().replace('"', ""))


def _handle_policy_terms(base_query: str, context: Dict[str, str]) -> List[str]:
    terms = []
    base = _clean_query(base_query).strip('"')
    if base:
        terms.append(base.lower())
        if not base.startswith("@"):
            terms.append(f"@{base.lower()}")
    terms.extend(term.lower() for term in _split_context_values(context.get("handles", "")))
    terms.extend(term.lower() for term in _split_context_values(context.get("emails_domains", "")))
    return [term for term in terms if term]


def _clean_query(query: str) -> str:
    cleaned = " ".join(str(query or "").replace("\x00", " ").split())
    return cleaned[:160].strip()


def _short_reason(reason: object) -> str:
    return " ".join(str(reason or "").split())[:220] or "Search variant."


def _entry(
    query: str,
    query_type: str,
    reason: str,
    phase: str = "initial",
    origin: str = "system",
    intent: str = "freeform_threat",
    sensitive: bool = False,
) -> Dict[str, str]:
    return {
        "query": _clean_query(query),
        "query_type": query_type if query_type in ALLOWED_QUERY_TYPES else "ai_probe",
        "reason": _short_reason(reason),
        "phase": phase,
        "origin": origin,
        "intent": normalize_search_intent(intent),
        "sensitive": bool(sensitive),
    }


def _dedupe_query_entries(entries: Iterable[Dict[str, str]]) -> List[Dict[str, str]]:
    seen = set()
    unique = []
    for entry in entries:
        query = _clean_query(entry.get("query", ""))
        key = re.sub(r"\s+", " ", query.lower())
        if not query or key in seen:
            continue
        seen.add(key)
        clean_entry = dict(entry)
        clean_entry["query"] = query
        clean_entry["query_type"] = clean_entry.get("query_type") if clean_entry.get("query_type") in ALLOWED_QUERY_TYPES else "ai_probe"
        clean_entry["reason"] = _short_reason(clean_entry.get("reason"))
        clean_entry["phase"] = clean_entry.get("phase") or "initial"
        clean_entry["origin"] = clean_entry.get("origin") or "system"
        clean_entry["intent"] = normalize_search_intent(clean_entry.get("intent"))
        clean_entry["sensitive"] = bool(clean_entry.get("sensitive")) or clean_entry["query_type"] == "sensitive_probe"
        unique.append(clean_entry)
    return unique


def _cap_query_entries(entries: List[Dict[str, str]], limit: int) -> List[Dict[str, str]]:
    return list(entries[: max(1, int(limit or CONSERVATIVE_LIMIT))])


def _canonical_link(url: str) -> str:
    parsed = urlparse(str(url or ""))
    return parsed._replace(fragment="", netloc=parsed.netloc.lower()).geturl().rstrip("/")


def _merge_result(merged_results: Dict[str, Dict[str, object]], result: Dict[str, object], query_entry: Dict[str, str]) -> None:
    link = str(result.get("link") or "")
    if not link:
        return
    key = _canonical_link(link)
    source_name = str(result.get("source") or "unknown")
    query_match = {
        "query": query_entry.get("query", ""),
        "query_type": query_entry.get("query_type", ""),
        "reason": query_entry.get("reason", ""),
        "phase": query_entry.get("phase", "initial"),
        "intent": query_entry.get("intent", ""),
        "origin": query_entry.get("origin", ""),
        "sensitive": bool(query_entry.get("sensitive")),
    }
    incoming_matches = result.get("matched_queries")
    if not isinstance(incoming_matches, list) or not incoming_matches:
        incoming_matches = [query_match] if query_match["query"] else []
    if key not in merged_results:
        item = deepcopy(result)
        item["matched_query"] = query_match["query"]
        item["query_reason"] = query_match["reason"]
        item["query_type"] = query_match["query_type"]
        item["matched_queries"] = list(incoming_matches)
        item["found_by_sources"] = [source_name] if source_name else []
        merged_results[key] = item
        return

    existing = merged_results[key]
    existing_quality = existing.get("quality") or {}
    incoming_quality = result.get("quality") or {}
    if int(incoming_quality.get("score") or 0) > int(existing_quality.get("score") or 0):
        existing["quality"] = incoming_quality
    if source_name and source_name not in existing.setdefault("found_by_sources", []):
        existing["found_by_sources"].append(source_name)
    for match in incoming_matches:
        if isinstance(match, dict) and match.get("query") and match not in existing.setdefault("matched_queries", []):
            existing["matched_queries"].append(match)


def _first_query_entry(result: Dict[str, object]) -> Dict[str, str]:
    queries = result.get("matched_queries")
    if isinstance(queries, list) and queries:
        first = queries[0]
        if isinstance(first, dict):
            return {
                "query": str(first.get("query") or result.get("matched_query") or ""),
                "query_type": str(first.get("query_type") or result.get("query_type") or ""),
                "reason": str(first.get("reason") or result.get("query_reason") or ""),
                "phase": str(first.get("phase") or "initial"),
            }
    return {
        "query": str(result.get("matched_query") or ""),
        "query_type": str(result.get("query_type") or ""),
        "reason": str(result.get("query_reason") or ""),
        "phase": "initial",
    }


def _status_counts(statuses: Iterable[Dict[str, object]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for item in statuses:
        status = str(item.get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
    return counts
