
import base64
import streamlit as st
from datetime import datetime
from artifacts import flatten_artifacts
from domain.models import RunConfig
from investigations import load_investigations
from pipeline import run_pipeline
from query_expansion import (
    ALLOWED_INTENTS,
    build_expansion_context,
    classify_search_intent,
)
from scrape import scrape_multiple_documents
from search import get_source_count, search_sources
from llm_utils import BufferedStreamingHandler, build_model_routing_plan, get_model_choices
from llm import get_llm, PRESET_PROMPTS
from config import (
    OPENAI_API_KEY,
    ANTHROPIC_API_KEY,
    GOOGLE_API_KEY,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    OLLAMA_BASE_URL,
    LLAMA_CPP_BASE_URL,
)
from health import check_llm_health, check_search_engines, check_tor_proxy


def _render_pipeline_error(stage: str, err: Exception) -> None:
    message = str(err).strip() or err.__class__.__name__
    lower_msg = message.lower()
    hints = [
        "- Confirm the relevant API key is set in your `.env` or shell before launching Streamlit.",
        "- Keys copied from dashboards often include hidden spaces; re-copy if authentication keeps failing.",
        "- Restart the app after updating environment variables so the new values are picked up.",
    ]

    if any(token in lower_msg for token in ("anthropic", "x-api-key", "invalid api key", "authentication")):
        hints.insert(0, "- Claude/Anthropic models require a valid `ANTHROPIC_API_KEY`.")
    elif "openrouter" in lower_msg or "user not found" in lower_msg or "code: 401" in lower_msg:
        hints.insert(0, "- OpenRouter 401/User not found usually means the API key is invalid/expired or has leading/trailing characters.")
        hints.insert(1, "- Set `OPENROUTER_API_KEY` without extra spaces and verify the key is active in your OpenRouter account.")
        hints.insert(2, "- Keep `OPENROUTER_BASE_URL` as `https://openrouter.ai/api/v1` unless you intentionally use a custom gateway.")
    elif "openai" in lower_msg or "gpt" in lower_msg:
        hints.insert(0, "- OpenAI models require `OPENAI_API_KEY` with access to the chosen model.")
    elif "google" in lower_msg or "gemini" in lower_msg:
        hints.insert(0, "- Google Gemini models need `GOOGLE_API_KEY` or Application Default Credentials.")

    st.error(
        "❌ Failed to {}.\n\nError: {}\n\n{}".format(
            stage,
            message,
            "\n".join(hints),
        )
    )
    st.stop()


# Cache expensive backend calls
@st.cache_data(ttl=200, show_spinner=False)
def cached_search_results(refined_query: str, threads: int):
    return search_sources(refined_query, max_workers=threads)


@st.cache_data(ttl=200, show_spinner=False)
def cached_scrape_multiple(filtered: list, threads: int):
    return scrape_multiple_documents(filtered, max_workers=threads)


def _status_label(status: str) -> str:
    labels = {
        "success": "ok",
        "zero_results": "empty",
        "up": "up",
        "down": "down",
        "timeout": "timeout",
        "http_error": "http",
        "tor_error": "tor",
        "request_error": "request",
        "parse_failure": "parse",
        "disabled": "disabled",
        "skipped_unhealthy": "skipped",
    }
    return labels.get(status, status or "unknown")


def render_source_status(statuses: list, host=st):
    if not statuses:
        host.caption("No source status captured yet.")
        return
    unique_sources = {}
    for item in statuses:
        name = item.get("name") or "unknown"
        bucket = unique_sources.setdefault(
            name,
            {"Source": name, "Queries": 0, "Results": 0, "Successes": 0, "Needs attention": 0},
        )
        bucket["Queries"] += 1
        bucket["Results"] += int(item.get("result_count") or 0)
        if item.get("status") == "success":
            bucket["Successes"] += 1
        elif item.get("status") != "zero_results":
            bucket["Needs attention"] += 1
    if len(unique_sources) < len(statuses):
        host.caption(f"{len(unique_sources)} unique sources checked across {len(statuses)} per-query source attempts.")
        host.dataframe(list(unique_sources.values()), use_container_width=True, hide_index=True)
    rows = [
        {
            "Query": item.get("query", ""),
            "Source": item.get("name"),
            "Status": _status_label(item.get("status")),
            "Results": item.get("result_count", 0),
            "Truncated": item.get("truncated_result_count", 0),
            "Latency ms": item.get("latency_ms"),
            "Error": item.get("error") or "",
        }
        for item in statuses
    ]
    host.dataframe(rows, use_container_width=True, hide_index=True)


def render_query_audit(query_plan: dict, query_runs: list, host=st):
    queries = (query_plan or {}).get("queries", [])
    if not queries and not query_runs:
        host.caption("No AI query expansion audit captured.")
        return
    if queries:
        inferred = (query_plan or {}).get("inferred_intent", {}) or {}
        host.markdown(
            f"**Mode:** `{(query_plan or {}).get('mode', 'off')}` &nbsp;&nbsp; "
            f"**Intent:** `{(query_plan or {}).get('selected_intent', 'freeform_threat')}` &nbsp;&nbsp; "
            f"**Inferred:** `{inferred.get('intent', 'unknown')}`"
        )
        host.caption(
            "Initial budget: {} | Pivot reserve: {} | Sensitive probes used: {} | Suppressed: {}".format(
                (query_plan or {}).get("initial_query_limit", ""),
                (query_plan or {}).get("artifact_pivot_reserve", 0),
                (query_plan or {}).get("sensitive_probes_used", 0),
                (query_plan or {}).get("sensitive_probes_suppressed", 0),
            )
        )
        warnings = (query_plan or {}).get("warnings", [])
        if warnings:
            host.warning(" | ".join(str(item) for item in warnings))
        host.dataframe(
            [
                {
                    "Phase": item.get("phase", "initial"),
                    "Type": item.get("query_type", ""),
                    "Intent": item.get("intent", (query_plan or {}).get("selected_intent", "")),
                    "Origin": item.get("origin", ""),
                    "Sensitive": bool(item.get("sensitive")),
                    "Query": item.get("query", ""),
                    "Reason": item.get("reason", ""),
                }
                for item in queries
            ],
            use_container_width=True,
            hide_index=True,
        )
    if query_runs:
        host.dataframe(
            [
                {
                    "Phase": item.get("phase", "initial"),
                    "Type": item.get("query_type", ""),
                    "Intent": item.get("intent", ""),
                    "Origin": item.get("origin", ""),
                    "Sensitive": bool(item.get("sensitive")),
                    "Query": item.get("query", ""),
                    "Results": item.get("result_count", 0),
                    "Status counts": item.get("status_counts", {}),
                }
                for item in query_runs
            ],
            use_container_width=True,
            hide_index=True,
        )


def render_artifacts(artifacts: dict, host=st):
    rows = flatten_artifacts(artifacts or {})
    if not rows:
        host.caption("No deterministic artifacts extracted.")
        return
    host.dataframe(rows, use_container_width=True, hide_index=True)


def _source_names_for_result(item: dict) -> str:
    names = item.get("found_by_sources", []) or [item.get("source", "unknown")]
    return ", ".join(str(name or "unknown") for name in names)


# Streamlit page configuration
st.set_page_config(
    page_title="Robin: AI-Powered Dark Web OSINT Tool",
    page_icon="🕵️‍♂️",
    initial_sidebar_state="expanded",
)

# Custom CSS for styling
st.markdown(
    """
    <style>
            .aStyle {
                font-size: 18px;
                font-weight: bold;
                padding: 5px;
                padding-left: 0px;
                text-align: left;
            }
    </style>""",
    unsafe_allow_html=True,
)


# Sidebar
st.sidebar.title("Robin")
st.sidebar.text("AI-Powered Dark Web OSINT Tool")
st.sidebar.markdown(
    """Made by [Apurv Singh Gautam](https://www.linkedin.com/in/apurvsinghgautam/)"""
)
st.sidebar.subheader("Settings")
def _env_is_set(value) -> bool:
    return bool(value and str(value).strip() and "your_" not in str(value))

model_options = get_model_choices()
default_model_index = (
    next(
        (
            idx
            for idx, name in enumerate(model_options)
            if name.lower() in {"gpt-5.4-mini", "gpt-4.1"}
        ),
        0,
    )
    if model_options
    else 0
)

if not model_options:
    st.sidebar.error(
        "⛔ **No LLM models available.**\n\n"
        "No API keys or local providers are configured. "
        "Set at least one in your `.env` file and restart Robin.\n\n"
        "See **Provider Configuration** below for details."
    )
    st.stop()

model = st.sidebar.selectbox(
    "Select LLM Model",
    model_options,
    index=default_model_index,
    key="model_select",
)
if any(name not in {"gpt-5.4", "gpt-5.4-mini", "gpt-5.4-nano", "gpt-4.1", "claude-sonnet-4-5", "gemini-2.5-flash"} for name in model_options):
    st.sidebar.caption("Locally detected Ollama models are automatically added to this list.")
threads = st.sidebar.slider("Scraping Threads", 1, 16, 4, key="thread_slider")
search_workers = max(threads, 12)
max_results = st.sidebar.slider(
    "Max Results to Filter", 10, 100, 50, key="max_results_slider",
    help="Cap the number of raw search results passed to the LLM filter step.",
)
max_scrape = st.sidebar.slider(
    "Max Pages to Scrape", 3, 20, 10, key="max_scrape_slider",
    help="Cap the number of filtered results that get scraped for content.",
)

st.sidebar.divider()
st.sidebar.subheader("Provider Configuration")
_providers = [
    ("OpenAI",      OPENAI_API_KEY,     True),
    ("Anthropic",   ANTHROPIC_API_KEY,  True),
    ("Google",      GOOGLE_API_KEY,     True),
    ("OpenRouter",  OPENROUTER_API_KEY, True),
    ("Ollama",      OLLAMA_BASE_URL,    False),
    ("llama.cpp",   LLAMA_CPP_BASE_URL, False),
]
for name, value, is_cloud in _providers:
    if _env_is_set(value):
        st.sidebar.markdown(f"&ensp;✅ **{name}** — configured")
    elif is_cloud:
        st.sidebar.markdown(f"&ensp;⚠️ **{name}** — API key not set")
    else:
        st.sidebar.markdown(f"&ensp;🔵 **{name}** — not configured *(optional)*")

with st.sidebar.expander("⚙️ Prompt Settings"):
    preset_options = {
        "🔍 Dark Web Threat Intel": "threat_intel",
        "🦠 Ransomware / Malware Focus": "ransomware_malware",
        "👤 Personal / Identity Investigation": "personal_identity",
        "🏢 Corporate Espionage / Data Leaks": "corporate_espionage",
    }
    preset_placeholders = {
        "threat_intel": "e.g. Pay extra attention to cryptocurrency wallet addresses and exchange names.",
        "ransomware_malware": "e.g. Highlight any references to double-extortion tactics or known ransomware-as-a-service affiliates.",
        "personal_identity": "e.g. Flag any passport or government ID numbers and note which country they appear to be from.",
        "corporate_espionage": "e.g. Prioritize any mentions of source code repositories, API keys, or internal Slack/email dumps.",
    }
    selected_preset_label = st.selectbox(
        "Research Domain",
        list(preset_options.keys()),
        key="preset_select",
    )
    selected_preset = preset_options[selected_preset_label]
    st.text_area(
        "System Prompt",
        value=PRESET_PROMPTS[selected_preset].strip(),
        height=200,
        disabled=True,
        key="system_prompt_display",
    )
    custom_instructions = st.text_area(
        "Custom Instructions (optional)",
        placeholder=preset_placeholders[selected_preset],
        height=100,
        key="custom_instructions",
    )

# --- Health Checks ---
st.sidebar.divider()
st.sidebar.subheader("Health Checks")

# LLM Health Check
if st.sidebar.button("🔌 Check LLM Connection", use_container_width=True):
    with st.sidebar:
        with st.spinner(f"Testing {model}..."):
            result = check_llm_health(model)
        if result["status"] == "up":
            st.sidebar.success(
                f"✅ **{result['provider']}** — Connected ({result['latency_ms']}ms)"
            )
        else:
            st.sidebar.error(
                f"❌ **{result['provider']}** — Failed\n\n{result['error']}"
            )

# Search Engine Health Check
if st.sidebar.button("🔍 Check Search Engines", use_container_width=True):
    with st.sidebar:
        with st.spinner("Checking Tor proxy..."):
            tor_result = check_tor_proxy()
        if tor_result["status"] == "down":
            st.sidebar.error(
                f"❌ **Tor Proxy** — Not reachable\n\n{tor_result['error']}\n\n"
                "Ensure Tor is running: `sudo systemctl start tor`"
            )
        else:
            st.sidebar.success(
                f"✅ **Tor Proxy** — Connected ({tor_result['latency_ms']}ms)"
            )
            with st.spinner(f"Pinging {get_source_count()} search sources via Tor..."):
                engine_results = check_search_engines()
            up_count = sum(1 for r in engine_results if r["status"] == "up")
            total = len(engine_results)
            if up_count == total:
                st.sidebar.success(f"✅ **All {total} engines reachable**")
            elif up_count > 0:
                st.sidebar.warning(f"⚠️ **{up_count}/{total} engines reachable**")
            else:
                st.sidebar.error(f"❌ **0/{total} engines reachable**")

            for r in engine_results:
                if r["status"] == "up":
                    st.sidebar.markdown(
                        f"&ensp;🟢 **{r['name']}** — {r['latency_ms']}ms"
                    )
                else:
                    st.sidebar.markdown(
                        f"&ensp;🔴 **{r['name']}** — {r['error']}"
                    )

# --- Past Investigations ---
st.sidebar.divider()
st.sidebar.subheader("📂 Past Investigations")
saved_investigations = load_investigations()
if saved_investigations:
    inv_labels = [
        f"{inv['_filename'].replace('investigation_','').replace('.json','')} — {inv['query'][:40]}"
        for inv in saved_investigations
    ]
    selected_inv_label = st.sidebar.selectbox(
        "Load investigation", ["(none)"] + inv_labels, key="inv_select"
    )
    if selected_inv_label != "(none)":
        selected_inv_idx = inv_labels.index(selected_inv_label)
        if st.sidebar.button("📂 Load", use_container_width=True, key="load_inv_btn"):
            st.session_state["loaded_investigation"] = saved_investigations[selected_inv_idx]
            st.rerun()
else:
    st.sidebar.caption("No saved investigations yet.")


# Main UI - logo and input
_, logo_col, _ = st.columns(3)
with logo_col:
    st.image(".github/assets/robin_logo.png", width=200)

# Display text box and button. A plain button avoids Streamlit's transient
# "form has no submit button" warning while the frontend hydrates.
col_input, col_mode, col_intent, col_button = st.columns(
    [7, 1.7, 2.2, 1], vertical_alignment="bottom"
)
query = col_input.text_input(
    "Enter Dark Web Search Query",
    placeholder="Enter Dark Web Search Query",
    label_visibility="collapsed",
    key="query_input",
)
expansion_mode_label = col_mode.selectbox(
    "AI Mode",
    ["Conservative", "Exploratory", "Off"],
    index=0,
    key="query_expansion_mode",
)
intent_options = ["Auto"] + sorted(ALLOWED_INTENTS)
selected_intent_label = col_intent.selectbox(
    "Search Intent",
    intent_options,
    index=0,
    key="search_intent_select",
    help="Prompt Settings control report style. Search Intent controls query expansion.",
)
run_button = col_button.button("Run", type="primary", use_container_width=True)

with st.expander("AI Query Context", expanded=False):
    auto_model_routing = st.checkbox(
        "Auto model routing",
        value=True,
        key="auto_model_routing",
        help="Use cheaper/faster GPT models for expansion and triage, and gpt-5.4 for the final report when available.",
    )
    ctx_col1, ctx_col2, ctx_col3 = st.columns(3)
    with ctx_col1:
        expansion_aliases = st.text_area("Aliases / name variants", height=70, key="expansion_aliases")
        expansion_geography = st.text_input("Geography", key="expansion_geography")
    with ctx_col2:
        expansion_handles = st.text_area("Handles", height=70, key="expansion_handles")
        expansion_organization = st.text_input("Organization", key="expansion_organization")
    with ctx_col3:
        expansion_emails_domains = st.text_area("Emails / domains", height=70, key="expansion_emails_domains")
        expansion_timeframe = st.text_input("Dates / timeframe", key="expansion_timeframe")
    expansion_freeform = st.text_area("Other context", height=80, key="expansion_freeform")

expansion_context = build_expansion_context(
    aliases=expansion_aliases,
    handles=expansion_handles,
    emails_domains=expansion_emails_domains,
    geography=expansion_geography,
    organization=expansion_organization,
    timeframe=expansion_timeframe,
    freeform=expansion_freeform,
)
inferred_intent_preview = classify_search_intent(query, expansion_context)
expansion_mode = expansion_mode_label.lower()
selected_search_intent = (
    inferred_intent_preview.get("intent", "freeform_threat")
    if selected_intent_label == "Auto"
    else selected_intent_label
)
model_routing_preview = build_model_routing_plan(model, auto_model_routing, model_options)
st.caption(
    "AI expansion: `{}` | search intent: `{}` | auto intent: `{}` ({})".format(
        expansion_mode,
        selected_search_intent,
        inferred_intent_preview.get("intent", "freeform_threat"),
        "; ".join(inferred_intent_preview.get("reasons", [])),
    )
)
if auto_model_routing:
    st.caption(
        "Model routing: refine `{}` | expand `{}` | triage `{}` | report `{}`".format(
            model_routing_preview.get("query_refinement"),
            model_routing_preview.get("query_expansion"),
            model_routing_preview.get("result_triage"),
            model_routing_preview.get("final_report"),
        )
    )

# Display loaded investigation (if any)
if "loaded_investigation" in st.session_state and not run_button:
    inv = st.session_state["loaded_investigation"]
    st.info(f"📂 **{inv['query']}** — {inv['timestamp'][:16]}")
    with st.expander("📋 Notes", expanded=False):
        st.markdown(f"**Refined Query:** `{inv['refined_query']}`")
        st.markdown(f"**Model:** `{inv['model']}` &nbsp;&nbsp; **Domain:** {inv['preset']}")
        routing = inv.get("model_routing", {}) or {}
        if routing.get("enabled"):
            st.markdown(
                "**Model Routing:** refine `{}` | expand `{}` | triage `{}` | report `{}`".format(
                    routing.get("query_refinement"),
                    routing.get("query_expansion"),
                    routing.get("result_triage"),
                    routing.get("final_report"),
                )
            )
        st.markdown(f"**Query Expansion:** `{inv.get('query_expansion_mode', 'off')}`")
        intent_metadata = inv.get("intent_metadata", {}) or {}
        st.markdown(f"**Search Intent:** `{intent_metadata.get('selected_intent', (inv.get('query_plan') or {}).get('selected_intent', 'unknown'))}`")
        st.markdown(f"**Sources:** {len(inv['sources'])}")
        st.markdown(f"**Scraped URLs:** {len(inv.get('scraped_urls', []))}")
    with st.expander(f"🔗 Sources ({len(inv['sources'])} results)", expanded=False):
        for i, item in enumerate(inv["sources"], 1):
            title = item.get("title", "Untitled")
            link = item.get("link", "")
            source_name = _source_names_for_result(item)
            matched_query = item.get("matched_query", "")
            quality = item.get("quality", {}) or {}
            quality_bits = []
            if quality.get("direct_mention"):
                quality_bits.append("direct mention")
            if quality.get("infrastructure_only"):
                quality_bits.append("infrastructure only")
            if quality.get("no_direct_mention"):
                quality_bits.append("no direct mention")
            quality_suffix = f" - `{', '.join(quality_bits)}`" if quality_bits else ""
            query_suffix = f" - query: `{matched_query}`" if matched_query else ""
            st.markdown(f"{i}. [{title}]({link}) - `{source_name}`{query_suffix}{quality_suffix}")
    st.subheader(":red[🔎 Findings]", anchor=None, divider="gray")
    with st.expander("Source Health Snapshot", expanded=False):
        render_source_status(inv.get("search_status", []))
    with st.expander("Deterministic Artifacts", expanded=False):
        render_artifacts(inv.get("artifacts", {}))
    with st.expander("AI Search Plan", expanded=False):
        render_query_audit(inv.get("query_plan", {}), inv.get("query_runs", []))
    st.markdown(inv["summary"])
    if st.button("✖ Clear"):
        del st.session_state["loaded_investigation"]
        st.rerun()

# Status + result section placeholders
status_slot = st.empty()
notes_placeholder = st.empty()
sources_placeholder = st.empty()
findings_placeholder = st.empty()


# Process the query
if run_button and query:
    # Clear any loaded investigation and old pipeline state
    st.session_state.pop("loaded_investigation", None)
    for k in [
        "refined",
        "raw_results",
        "results",
        "filtered",
        "scraped",
        "streamed_summary",
        "search_status",
        "artifacts",
        "scrape_status",
        "query_plan",
        "query_runs",
        "query_expansion_mode_used",
        "search_intent_used",
        "model_routing_used",
    ]:
        st.session_state.pop(k, None)

    st.session_state.model_routing_used = build_model_routing_plan(
        model,
        auto_model_routing,
        model_options,
    )

    # Stage 1 - Load LLMs
    with status_slot.container():
        with st.spinner("🔄 Loading LLM..."):
            try:
                refine_llm = get_llm(st.session_state.model_routing_used["query_refinement"])
                expansion_llm = get_llm(st.session_state.model_routing_used["query_expansion"])
                triage_llm = get_llm(st.session_state.model_routing_used["result_triage"])
                report_llm = get_llm(st.session_state.model_routing_used["final_report"])
            except Exception as e:
                _render_pipeline_error("load the selected LLM routing plan", e)

    # Pipeline execution
    st.session_state.streamed_summary = ""

    with findings_placeholder.container():
        st.subheader(":red[Findings]", anchor=None, divider="gray")
        summary_slot = st.empty()

    def ui_emit(chunk: str):
        st.session_state.streamed_summary += chunk
        summary_slot.markdown(st.session_state.streamed_summary)

    pipeline_config = RunConfig(
        query=query,
        model=model,
        preset=selected_preset,
        preset_label=selected_preset_label,
        custom_instructions=custom_instructions,
        expansion_mode=expansion_mode,
        selected_search_intent=selected_search_intent,
        expansion_context=expansion_context,
        model_routing=st.session_state.model_routing_used,
        max_results=max_results,
        max_scrape=max_scrape,
        search_workers=search_workers,
        scrape_workers=threads,
    )

    with status_slot.container():
        with st.spinner("Running investigation pipeline..."):
            try:
                pipeline_state = run_pipeline(
                    pipeline_config,
                    refine_llm,
                    expansion_llm,
                    triage_llm,
                    report_llm,
                    search_func=cached_search_results,
                    scrape_func=cached_scrape_multiple,
                    summary_stream_handler=BufferedStreamingHandler(ui_callback=ui_emit),
                )
            except Exception as e:
                _render_pipeline_error("run the investigation pipeline", e)

    st.session_state.pipeline_state = pipeline_state.model_dump(mode="json")
    st.session_state.refined = pipeline_state.refined_query
    st.session_state.raw_results = pipeline_state.raw_results
    st.session_state.results = pipeline_state.qualified_results
    st.session_state.filtered = pipeline_state.filtered_results
    st.session_state.scraped = pipeline_state.scraped_content
    st.session_state.scrape_status = pipeline_state.scrape_status
    st.session_state.artifacts = pipeline_state.artifacts
    st.session_state.search_status = pipeline_state.search_status
    st.session_state.query_plan = pipeline_state.query_plan
    st.session_state.query_runs = pipeline_state.query_runs
    st.session_state.query_expansion_mode_used = pipeline_state.query_expansion_mode
    st.session_state.search_intent_used = pipeline_state.intent_metadata.get("selected_intent", selected_search_intent)
    st.session_state.streamed_summary = pipeline_state.synthesis_report.summary or st.session_state.streamed_summary
    _fname = pipeline_state.investigation_file

    if not st.session_state.results:
        with sources_placeholder.container():
            if st.session_state.raw_results:
                st.warning(
                    "Search engines returned links, but none had a direct target mention for this identifier. "
                    "Check Source Status and AI Search Plan for broad-source noise, timeouts, or weak query variants."
                )
            else:
                st.warning("No search results were returned. Check source status for timeouts, Tor errors, parse failures, or zero-result sources.")
            with st.expander("AI Search Plan", expanded=True):
                render_query_audit(st.session_state.query_plan, st.session_state.query_runs)
            with st.expander("Source Status", expanded=True):
                render_source_status(st.session_state.search_status)
        st.stop()

    # Render organized sections
    with notes_placeholder.container():
        with st.expander("📋 Notes", expanded=False):
            st.markdown(f"**Refined Query:** `{st.session_state.refined}`")
            st.markdown(f"**Model:** `{model}` &nbsp;&nbsp; **Domain:** {selected_preset_label}")
            routing = st.session_state.model_routing_used
            if routing.get("enabled"):
                st.markdown(
                    "**Model Routing:** refine `{}` | expand `{}` | triage `{}` | report `{}`".format(
                        routing.get("query_refinement"),
                        routing.get("query_expansion"),
                        routing.get("result_triage"),
                        routing.get("final_report"),
                    )
                )
            st.markdown(
                f"**Query Expansion:** `{st.session_state.query_expansion_mode_used}` &nbsp;&nbsp; "
                f"**Search Intent:** `{st.session_state.search_intent_used}` &nbsp;&nbsp; "
                f"**Queries Run:** {len(st.session_state.query_runs)}"
            )
            st.markdown(
                f"**Raw results:** {len(st.session_state.raw_results)} &nbsp;&nbsp; "
                f"**Qualified input:** {len(st.session_state.results)} &nbsp;&nbsp; "
                f"**Filtered to:** {len(st.session_state.filtered)} &nbsp;&nbsp; "
                f"**Scraped:** {len(st.session_state.scraped)}"
            )
            source_successes = sum(1 for item in st.session_state.search_status if item.get("status") == "success")
            source_failures = sum(1 for item in st.session_state.search_status if item.get("status") not in ("success", "zero_results"))
            st.markdown(f"**Sources with results:** {source_successes} &nbsp;&nbsp; **Sources needing attention:** {source_failures}")
            st.markdown(f"**Artifacts extracted:** {len(flatten_artifacts(st.session_state.artifacts))}")

    with sources_placeholder.container():
        with st.expander(f"🔗 Sources ({len(st.session_state.filtered)} results)", expanded=False):
            for i, item in enumerate(st.session_state.filtered, 1):
                title = item.get("title", "Untitled")
                link = item.get("link", "")
                source_name = _source_names_for_result(item)
                matched_query = item.get("matched_query", "")
                quality = item.get("quality", {}) or {}
                quality_bits = []
                if quality.get("direct_mention"):
                    quality_bits.append("direct mention")
                if quality.get("infrastructure_only"):
                    quality_bits.append("infrastructure only")
                if quality.get("no_direct_mention"):
                    quality_bits.append("no direct mention")
                quality_suffix = f" - `{', '.join(quality_bits)}`" if quality_bits else ""
                query_suffix = f" - query: `{matched_query}`" if matched_query else ""
                st.markdown(f"{i}. [{title}]({link}) - `{source_name}`{query_suffix}{quality_suffix}")
        with st.expander("Source Status", expanded=False):
            render_source_status(st.session_state.search_status)
        with st.expander("AI Search Plan", expanded=False):
            render_query_audit(st.session_state.query_plan, st.session_state.query_runs)
        with st.expander("Deterministic Artifacts", expanded=False):
            render_artifacts(st.session_state.artifacts)

    with findings_placeholder.container():
        st.subheader(":red[🔎 Findings]", anchor=None, divider="gray")
        st.markdown(st.session_state.streamed_summary)
        now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        fname = f"summary_{now}.md"
        b64 = base64.b64encode(st.session_state.streamed_summary.encode()).decode()
        href = f'<div class="aStyle">📥 <a href="data:file/markdown;base64,{b64}" download="{fname}">Download</a></div>'
        st.markdown(href, unsafe_allow_html=True)

    status_slot.success(f"✔️ Pipeline completed successfully! Investigation saved as `{_fname}`")
