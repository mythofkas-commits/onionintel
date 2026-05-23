from __future__ import annotations

from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, Field

from domain.models import RunConfig
from llm import get_llm
from llm_utils import build_model_routing_plan, get_model_choices
from pipeline import run_pipeline
from storage.repository import (
    export_investigation_json,
    export_investigation_markdown,
    get_run_payload,
    list_investigations,
    list_source_health,
)

app = FastAPI(title="OnionIntel API", version="0.1.0")


class RunCreateRequest(BaseModel):
    query: str
    model: str
    preset: str = "threat_intel"
    preset_label: str = "Threat Intel"
    custom_instructions: str = ""
    expansion_mode: Literal["off", "conservative", "exploratory"] = "conservative"
    selected_search_intent: str = "freeform_threat"
    expansion_context: dict[str, Any] = Field(default_factory=dict)
    max_results: int = 50
    max_scrape: int = 10
    search_workers: int = 12
    scrape_workers: int = 4
    auto_model_routing: bool = True


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/runs")
def create_run(request: RunCreateRequest) -> dict[str, Any]:
    model_choices = get_model_choices()
    routing = build_model_routing_plan(request.model, request.auto_model_routing, model_choices)
    try:
        state = run_pipeline(
            RunConfig(
                query=request.query,
                model=request.model,
                preset=request.preset,
                preset_label=request.preset_label,
                custom_instructions=request.custom_instructions,
                expansion_mode=request.expansion_mode,
                selected_search_intent=request.selected_search_intent,
                expansion_context=request.expansion_context,
                model_routing=routing,
                max_results=request.max_results,
                max_scrape=request.max_scrape,
                search_workers=request.search_workers,
                scrape_workers=request.scrape_workers,
            ),
            refine_llm=get_llm(routing["query_refinement"]),
            expansion_llm=get_llm(routing["query_expansion"]),
            triage_llm=get_llm(routing["result_triage"]),
            report_llm=get_llm(routing["final_report"]),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return state.model_dump(mode="json")


@app.get("/runs/{run_id}")
def read_run(run_id: str) -> dict[str, Any]:
    payload = get_run_payload(run_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="run not found")
    return payload


@app.get("/investigations")
def read_investigations() -> list[dict[str, Any]]:
    return list_investigations()


@app.get("/runs/{run_id}/documents")
def read_run_documents(run_id: str) -> list[dict[str, Any]]:
    payload = get_run_payload(run_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="run not found")
    return payload.get("documents", []) or []


@app.get("/runs/{run_id}/entities")
def read_run_entities(run_id: str) -> list[dict[str, Any]]:
    payload = get_run_payload(run_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="run not found")
    return payload.get("entities", []) or []


@app.get("/runs/{run_id}/claims")
def read_run_claims(run_id: str) -> list[dict[str, Any]]:
    payload = get_run_payload(run_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="run not found")
    return payload.get("claims", []) or []


@app.get("/sources/health")
def read_source_health() -> list[dict[str, Any]]:
    return list_source_health()


@app.get("/runs/{run_id}/export.json")
def export_json(run_id: str) -> dict[str, Any]:
    payload = export_investigation_json(run_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="run not found")
    return payload


@app.get("/runs/{run_id}/export.md")
def export_markdown(run_id: str) -> Response:
    markdown = export_investigation_markdown(run_id)
    if markdown is None:
        raise HTTPException(status_code=404, detail="run not found")
    return Response(content=markdown, media_type="text/markdown")
