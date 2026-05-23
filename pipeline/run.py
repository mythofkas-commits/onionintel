from __future__ import annotations

import logging
from typing import Any, Callable

from ai.tasks.claim_extraction import extract_claims_with_llm_or_fallback
from ai.tasks.relevance import score_relevance_with_llm
from ai.tasks.report_synthesis import synthesize_report_from_claims
from domain.models import (
    Artifact,
    Document,
    FetchRecord,
    RelevanceScore,
    RunConfig,
    RunState,
    SearchHit,
    SourceRecord,
    SynthesisReport,
    stable_id,
    utc_now,
)
from extractors.document_artifacts import (
    extract_artifacts_from_documents,
    extract_artifacts_from_search_hits,
    merge_typed_artifacts,
    typed_artifacts_to_legacy_dict,
)
from graph.build import build_relationships
from health import check_tor_proxy
from investigations import save_investigation
from llm import filter_results, generate_summary, refine_query
from normalize.entities import artifacts_to_entities_v2
from connectors.runner import collect_sources
from pipeline.pivots import generate_pivot_candidates
from query_expansion import (
    annotate_results_with_scraped_content,
    classify_search_intent,
    filter_qualified_results,
    run_expanded_search,
    single_query_plan,
)
from ranking.relevance import rank_documents, rank_search_results
from scrape import scrape_multiple_documents

logger = logging.getLogger(__name__)


def _log_stage(run_id: str, stage: str, status: str, **metadata: Any) -> None:
    logger.info("run_id=%s stage=%s status=%s metadata=%s", run_id, stage, status, metadata)


def _model_list(model_cls, items: list[dict[str, Any]]) -> list[Any]:
    models = []
    for item in items or []:
        try:
            models.append(model_cls(**item))
        except Exception:
            logger.debug("Unable to hydrate %s from %s", model_cls.__name__, item, exc_info=True)
    return models


def run_pipeline(
    config: RunConfig,
    refine_llm,
    expansion_llm,
    triage_llm,
    report_llm,
    *,
    search_func: Callable[..., dict[str, Any]] = collect_sources,
    expanded_search_func: Callable[..., dict[str, Any]] = run_expanded_search,
    scrape_func: Callable[..., dict[str, Any]] = scrape_multiple_documents,
    tor_check_func: Callable[[], dict[str, Any]] = check_tor_proxy,
    summary_stream_handler=None,
    save_result: bool = True,
) -> RunState:
    state = RunState(
        run_id=config.run_id,
        created_at=config.created_at,
        query=config.query,
        model=config.model,
        preset=config.preset,
        preset_label=config.preset_label,
        model_routing=config.model_routing,
        query_expansion_mode=config.expansion_mode,
    )

    def mark(stage: str, status: str, **metadata: Any) -> None:
        state.add_stage(stage, status, **metadata)
        _log_stage(state.run_id, stage, status, **metadata)

    mark("refine_query", "started")
    state.refined_query = refine_query(refine_llm, config.query)
    mark("refine_query", "success", refined_query=state.refined_query)

    mark("search", "started", expansion_mode=config.expansion_mode)
    tor_health = tor_check_func()
    if tor_health.get("status") == "down":
        mark("search", "tor_down", error=tor_health.get("error"))
        raise RuntimeError(f"Tor is not ready for searches yet: {tor_health.get('error')}")

    if config.expansion_mode == "off":
        search_payload = search_func(state.refined_query, max_workers=config.search_workers)
        inferred_intent = classify_search_intent(config.query, config.expansion_context)
        search_payload["results"] = annotate_results_with_scraped_content(
            search_payload.get("results", []),
            {},
            config.query,
            config.expansion_context,
            config.selected_search_intent,
        )
        search_payload["qualified_results"] = filter_qualified_results(
            search_payload["results"],
            config.selected_search_intent,
        )
        search_payload["query_plan"] = single_query_plan(
            config.query,
            state.refined_query,
            mode="off",
            search_intent=config.selected_search_intent,
            inferred_intent=inferred_intent,
        )
        search_payload["query_runs"] = [
            {
                "query": state.refined_query,
                "query_type": "refined",
                "reason": "Single refined query.",
                "phase": "initial",
                "intent": config.selected_search_intent,
                "origin": "system",
                "sensitive": False,
                "result_count": len(search_payload.get("results", [])),
            }
        ]
        search_payload["query_expansion_mode"] = "off"
    else:
        search_payload = expanded_search_func(
            expansion_llm,
            base_query=config.query,
            refined_query=state.refined_query,
            context=config.expansion_context,
            mode=config.expansion_mode,
            search_intent=config.selected_search_intent,
            reporting_preset=config.preset,
            max_workers=config.search_workers,
        )

    state.raw_results = list(search_payload.get("results", []))
    state.qualified_results = list(search_payload.get("qualified_results", state.raw_results))
    state.search_status = list(search_payload.get("sources", []))
    state.source_records = [SourceRecord.from_status(item) for item in state.search_status]
    state.search_hits = [
        SearchHit.from_result(result, query=state.refined_query, rank=idx + 1)
        for idx, result in enumerate(state.raw_results)
    ]
    state.query_plan = search_payload.get("query_plan", {}) or {}
    state.query_runs = search_payload.get("query_runs", []) or []
    state.query_expansion_mode = search_payload.get("query_expansion_mode", config.expansion_mode)
    selected_intent = (state.query_plan or {}).get("selected_intent", config.selected_search_intent)
    state.intent_metadata = {
        "selected_intent": selected_intent,
        "inferred_intent": (state.query_plan or {}).get("inferred_intent", {}),
        "warnings": (state.query_plan or {}).get("warnings", []),
    }
    mark("search", "success", raw_results=len(state.raw_results), qualified_results=len(state.qualified_results))

    if not state.qualified_results:
        mark("pipeline", "no_results")
        state.completed_at = utc_now()
        return state

    state.qualified_results = state.qualified_results[: config.max_results]

    if config.use_legacy_llm_filter:
        mark("filter_results", "started", input_results=len(state.qualified_results), mode="legacy_llm")
        state.filtered_results = filter_results(triage_llm, state.refined_query, state.qualified_results)
        state.filtered_results = state.filtered_results[: config.max_scrape]
        mark("filter_results", "success", filtered_results=len(state.filtered_results))
    else:
        mark("rank_search_results", "started", input_results=len(state.qualified_results))
        ranked_results = rank_search_results(
            query=config.query,
            results=state.qualified_results,
            context=config.expansion_context,
            intent=selected_intent,
        )
        if config.enable_ai_relevance:
            ai_candidates = [
                {
                    "hit_id": stable_id("hit", item.get("source"), item.get("link") or item.get("url"), item.get("title")),
                    "title": item.get("title", ""),
                    "url": item.get("link") or item.get("url") or "",
                    "snippet": item.get("snippet", ""),
                    "deterministic_relevance": item.get("relevance", {}),
                }
                for item in ranked_results[:20]
            ]
            ai_scores = {
                decision.hit_id: decision
                for decision in score_relevance_with_llm(triage_llm, config.query, ai_candidates).decisions
            }
            for item in ranked_results:
                hit_id = stable_id("hit", item.get("source"), item.get("link") or item.get("url"), item.get("title"))
                decision = ai_scores.get(hit_id)
                if not decision:
                    continue
                relevance = item.setdefault("relevance", {})
                relevance["score"] = max(0.0, float(relevance.get("score") or 0.0) + ((decision.score - 0.5) * 10))
                relevance.setdefault("reasons", []).append(f"AI relevance: {decision.reason}")
                relevance["model_assisted"] = True
            ranked_results.sort(key=lambda item: item.get("relevance", {}).get("score", 0), reverse=True)
        state.relevance_scores = [
            RelevanceScore(
                target_id=stable_id("hit", item.get("source"), item.get("link") or item.get("url"), item.get("title")),
                target_type="hit",
                score=float((item.get("relevance") or {}).get("score") or 0.0),
                reasons=list((item.get("relevance") or {}).get("reasons") or []),
                matched_terms=list((item.get("relevance") or {}).get("matched_terms") or []),
                model_assisted=bool((item.get("relevance") or {}).get("model_assisted")),
                metadata={"stage": "pre_fetch_v1"},
            )
            for item in ranked_results
        ]
        state.filtered_results = ranked_results[: config.max_scrape]
        mark("rank_search_results", "success", filtered_results=len(state.filtered_results))

    mark("scrape", "started", input_results=len(state.filtered_results))
    scrape_payload = scrape_func(state.filtered_results, max_workers=config.scrape_workers)
    if "content" in scrape_payload:
        state.scraped_content = scrape_payload.get("content", {}) or {}
        state.scrape_status = scrape_payload.get("status", []) or []
        state.documents = _model_list(Document, scrape_payload.get("documents", []) or [])
        state.fetch_records = _model_list(FetchRecord, scrape_payload.get("fetches", []) or [])
    else:
        state.scraped_content = scrape_payload or {}
    mark("scrape", "success", scraped=len(state.scraped_content), documents=len(state.documents))

    mark("extract_document_artifacts", "started")
    document_artifacts = extract_artifacts_from_documents(state.documents)
    hit_artifacts = extract_artifacts_from_search_hits(state.search_hits)
    state.typed_artifacts = merge_typed_artifacts(document_artifacts, hit_artifacts)
    state.artifacts = typed_artifacts_to_legacy_dict(state.typed_artifacts)
    mark("extract_document_artifacts", "success", artifacts=len(state.typed_artifacts))

    mark("normalize_entities", "started")
    state.entities = artifacts_to_entities_v2(state.typed_artifacts)
    mark("normalize_entities", "success", entities=len(state.entities))

    mark("build_relationships", "started")
    state.relationships = build_relationships(state.typed_artifacts, state.entities)
    mark("build_relationships", "success", relationships=len(state.relationships))

    state.filtered_results = annotate_results_with_scraped_content(
        state.filtered_results,
        state.scraped_content,
        config.query,
        config.expansion_context,
        selected_intent,
    )
    mark("rank_documents", "started")
    state.ranked_documents, document_scores = rank_documents(
        config.query,
        state.documents,
        state.entities,
        state.typed_artifacts,
        config.expansion_context,
    )
    state.relevance_scores.extend(document_scores)
    mark("rank_documents", "success", ranked_documents=len(state.ranked_documents))

    if config.enable_pivot_suggestions:
        mark("pivot_suggestions", "started")
        state.pivot_suggestions = generate_pivot_candidates(state.entities)
        mark("pivot_suggestions", "success", pivots=len(state.pivot_suggestions))

    if config.enable_claim_extraction:
        mark("extract_claims", "started")
        state.claims = extract_claims_with_llm_or_fallback(
            report_llm,
            config.query,
            state.documents,
            state.entities,
            state.typed_artifacts,
            enable_llm=True,
        )
        mark("extract_claims", "success", claims=len(state.claims))

    mark("synthesize_from_claims", "started")
    if config.enable_claim_synthesis:
        state.synthesis_report = synthesize_report_from_claims(
            report_llm,
            config.query,
            state.claims,
            state.documents,
            state.entities,
            state.relationships,
            state.pivot_suggestions,
        )
    else:
        if summary_stream_handler is not None:
            report_llm.callbacks = [summary_stream_handler]
        summary = generate_summary(
            report_llm,
            config.query,
            state.scraped_content,
            preset=config.preset,
            custom_instructions=config.custom_instructions,
            artifacts=state.artifacts,
            sources=state.filtered_results,
            query_plan=state.query_plan,
            query_runs=state.query_runs,
        )
        state.synthesis_report = SynthesisReport(summary=summary, metadata={"synthesis_method": "legacy_fallback"})
    mark("synthesize_from_claims", "success", summary_chars=len(state.synthesis_report.summary or ""))

    if save_result:
        mark("save_investigation", "started")
        state.investigation_file = save_investigation(
            query=config.query,
            refined_query=state.refined_query,
            model=config.model,
            preset_label=config.preset_label,
            sources=state.filtered_results,
            source_provenance=state.raw_results,
            search_status=state.search_status,
            artifacts=state.artifacts,
            scraped_urls=list(state.scraped_content.keys()),
            query_plan=state.query_plan,
            query_runs=state.query_runs,
            query_expansion_mode=state.query_expansion_mode,
            model_routing=state.model_routing,
            intent_metadata=state.intent_metadata,
            summary=state.synthesis_report.summary,
            run_id=state.run_id,
            schema_version=state.schema_version,
            stage_status=state.stage_status,
            scrape_status=state.scrape_status,
            documents=[document.model_dump(mode="json") for document in state.documents],
            fetch_records=[record.model_dump(mode="json") for record in state.fetch_records],
            typed_artifacts=[artifact.model_dump(mode="json") for artifact in state.typed_artifacts],
            entities=[entity.model_dump(mode="json") for entity in state.entities],
            relationships=[relationship.model_dump(mode="json") for relationship in state.relationships],
            relevance_scores=[score.model_dump(mode="json") for score in state.relevance_scores],
            ranked_documents=state.ranked_documents,
            pivot_suggestions=[pivot.model_dump(mode="json") for pivot in state.pivot_suggestions],
            claims=[claim.model_dump(mode="json") for claim in state.claims],
            synthesis_report=state.synthesis_report.model_dump(mode="json"),
        )
        mark("save_investigation", "success", filename=state.investigation_file)

    state.completed_at = utc_now()
    mark("pipeline", "success")
    return state
