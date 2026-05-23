from __future__ import annotations

import logging
from typing import Any, Callable

from artifacts import extract_artifacts
from domain.models import (
    Artifact,
    Document,
    FetchRecord,
    RunConfig,
    RunState,
    SearchHit,
    SourceRecord,
    SynthesisReport,
    utc_now,
)
from graph.build import artifacts_to_entities, build_relationships
from health import check_tor_proxy
from investigations import save_investigation
from llm import filter_results, generate_summary, refine_query
from query_expansion import (
    annotate_results_with_scraped_content,
    classify_search_intent,
    filter_qualified_results,
    run_expanded_search,
    single_query_plan,
)
from scrape import scrape_multiple_documents
from search import search_sources

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


def _typed_artifacts(artifacts: dict[str, list[dict[str, Any]]], documents: list[Document]) -> list[Artifact]:
    doc_by_url = {}
    for document in documents:
        doc_by_url[document.url] = document.doc_id
        doc_by_url[document.final_url] = document.doc_id
    typed = []
    for artifact_type, rows in (artifacts or {}).items():
        for row in rows or []:
            doc_id = doc_by_url.get(str(row.get("source_url") or ""), "")
            typed.append(Artifact.from_row(artifact_type, row, doc_id=doc_id))
    return typed


def run_pipeline(
    config: RunConfig,
    refine_llm,
    expansion_llm,
    triage_llm,
    report_llm,
    *,
    search_func: Callable[..., dict[str, Any]] = search_sources,
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

    mark("filter_results", "started", input_results=len(state.qualified_results))
    state.filtered_results = filter_results(triage_llm, state.refined_query, state.qualified_results)
    state.filtered_results = state.filtered_results[: config.max_scrape]
    mark("filter_results", "success", filtered_results=len(state.filtered_results))

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

    mark("extract_artifacts", "started")
    state.artifacts = extract_artifacts(
        search_results=state.filtered_results,
        scraped_content=state.scraped_content,
    )
    state.typed_artifacts = _typed_artifacts(state.artifacts, state.documents)
    state.entities = artifacts_to_entities(state.typed_artifacts)
    state.relationships = build_relationships(state.typed_artifacts, state.entities)
    state.filtered_results = annotate_results_with_scraped_content(
        state.filtered_results,
        state.scraped_content,
        config.query,
        config.expansion_context,
        selected_intent,
    )
    mark(
        "extract_artifacts",
        "success",
        artifacts=len(state.typed_artifacts),
        entities=len(state.entities),
        relationships=len(state.relationships),
    )

    mark("synthesize", "started")
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
    state.synthesis_report = SynthesisReport(summary=summary)
    mark("synthesize", "success", summary_chars=len(summary or ""))

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
        )
        mark("save_investigation", "success", filename=state.investigation_file)

    state.completed_at = utc_now()
    mark("pipeline", "success")
    return state
