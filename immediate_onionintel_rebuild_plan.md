# OnionIntel — local single-user rebuild decision and implementation plan

## A) Recommendation

Do not build a totally separate product from absolute zero.

Also do not keep extending the current pipeline as-is.

The right move is:

- keep this repo as the shell, container, and donor of a few useful modules
- replace the execution core almost completely
- keep Streamlit only as a frontend, not as the pipeline orchestrator

In plain terms: this should be a **new core inside the current repo**, not a clean-sheet product and not an incremental patch job.

### Why

Observed in repo:

- `ui.py` currently runs the whole flow itself: refine query -> search -> filter -> scrape -> extract -> summarize -> save (`ui.py:543-743`)
- search is fundamentally search-engine aggregation through `sources.yml` + `sources.py`, not a connector framework (`sources.py:123-157`, `sources.py:434-555`, `sources.yml:1-163`)
- scraping returns mostly `url -> truncated text`, not a rich document object (`scrape.py:185-238`)
- extraction is useful but flat and regex-only (`artifacts.py:72-114`)
- AI is mostly used for query rewriting, result index picking, and final prose generation (`llm.py:73-151`, `llm.py:318-352`)

Inference:

- the current system is strong enough to donate parts
- it is not the right architecture to keep building on directly if your real goal is much better sourcing, parsing, normalization, extraction, pivots, and synthesis

## What to keep, what to replace

### Keep and reuse

1. Tor/container bootstrap
- `Dockerfile`
- `entrypoint.sh`

2. Search parser helpers from `sources.py`
- `_extract_candidate_url()`
- `_parse_container_results()`
- `parse_search_html()`

3. Safe fetch ideas from `scrape.py`
- `_is_safe_http_url()`
- `_request_with_redirect_policy()`
- content caps and redirect caps

4. Deterministic extraction baseline from `artifacts.py`
- regex IOC extraction as first pass

5. Intent and query-planning ideas from `query_expansion.py`
- `classify_search_intent()`
- `_deterministic_initial_queries()`
- quality-term logic as a starting point

6. Model routing idea from `llm_utils.py`
- `build_model_routing_plan()`

### Replace or stop extending

1. `ui.py` as pipeline brain
2. `search.py` shim layer
3. `investigations.py` as the data model
4. `llm.filter_results()` index-picking approach
5. custom YAML parser in `sources.py`
6. flat `result/artifact/summary` flow as the main architecture

## B) Exact things to build, and how

## 1. Build a real in-memory domain model first

Create `domain/models.py`.

Use Pydantic models or dataclasses for:

- `RunConfig`
- `QueryPlan`
- `QueryTask`
- `SourceRecord`
- `SearchHit`
- `FetchRecord`
- `Document`
- `Artifact`
- `Entity`
- `Relationship`
- `EnrichmentRecord`
- `Claim`
- `SynthesisReport`
- `RunState`

Minimum shape:

```python
class SearchHit(BaseModel):
    hit_id: str
    source_id: str
    connector_id: str
    query: str
    title: str
    url: str
    raw_url: str | None = None
    snippet: str = ""
    discovered_at: datetime
    source_rank: int | None = None

class Document(BaseModel):
    doc_id: str
    source_id: str
    connector_id: str
    url: str
    final_url: str
    title: str
    content_type: str
    status_code: int | None = None
    raw_html: str = ""
    extracted_text: str = ""
    text_hash: str = ""
    outlinks: list[str] = []
    language: str | None = None
    metadata: dict = {}

class Artifact(BaseModel):
    artifact_id: str
    artifact_type: str
    value: str
    normalized_value: str
    doc_id: str
    evidence_text: str
    start_offset: int | None = None
    end_offset: int | None = None

class Entity(BaseModel):
    entity_id: str
    entity_type: str
    canonical_value: str
    raw_values: list[str]
    artifact_ids: list[str]
    enrichment: list[dict] = []
```

Why first:

- right now the system jumps from result dictionaries to final prose
- until you define the objects, everything else stays muddy

## 2. Replace the source registry with a real source catalog

Create:

- `registry/schema.py`
- `registry/loaders.py`
- `registry/sources/search_engines.yml`
- `registry/sources/public_feeds.yml`
- `registry/sources/site_monitors.yml`

Replace the current `SourceConfig` (`sources.py:46-53`) with something like:

```python
class SourceSpec(BaseModel):
    id: str
    name: str
    category: Literal["search_engine", "api_feed", "web_feed", "known_site"]
    access: Literal["tor", "direct", "api"]
    enabled: bool = True
    parser: str = "generic"
    timeout: int = 40
    rate_limit_per_minute: int | None = None
    tags: list[str] = []
    supports_query: bool = True
    notes: str = ""
```

How to use it:

- search engines stay in one registry file
- lawfully valuable feeds/APIs go in another
- each entry declares how it is collected

This is the first sourcing upgrade that matters.

## 3. Build a connector framework

Create:

- `connectors/base.py`
- `connectors/search_engine.py`
- `connectors/api_feed.py`
- `connectors/site_monitor.py`

Interface:

```python
class BaseConnector(Protocol):
    connector_id: str
    def collect(self, task: QueryTask, source: SourceSpec) -> list[SearchHit] | list[Document]: ...
```

Then implement:

### `SearchEngineConnector`
Use the good parts of `sources.py`:

- `_extract_candidate_url()`
- `_parse_container_results()`
- `parse_search_html()`

But stop returning raw dicts. Return `SearchHit` objects.

### `ApiFeedConnector`
For lawfully useful enrichment/collection, add connectors for:

- abuse.ch / URLhaus / ThreatFox / MalwareBazaar
- CISA KEV
- NVD
- OTX or MISP feeds
- urlscan
- public DNS/hosting enrichment sources you have access to
- Chainabuse / Etherscan-style wallet metadata if relevant

### `KnownSiteMonitorConnector`
For specific approved pages or known target pages:

- fetch page
- extract links
- compare content hash
- emit documents and outlinks

## 4. Build a real pipeline module and move orchestration out of `ui.py`

Create:

- `pipeline/run.py`
- `pipeline/stages.py`
- `pipeline/pivots.py`

Main flow:

```python
run_pipeline(run_config) -> RunState
    1. build_query_plan()
    2. collect_hits()
    3. dedupe_hits()
    4. select_fetch_targets()
    5. fetch_documents()
    6. parse_documents()
    7. extract_artifacts()
    8. normalize_entities()
    9. enrich_entities()
   10. generate_pivot_queries()
   11. run_second_pass_collection()
   12. extract_claims()
   13. synthesize_report()
```

Streamlit should only do:

```python
state = run_pipeline(config)
render_state(state)
```

That is the single most important structural change.

## 5. Upgrade scraping into document collection, not text collection

Current problem:

- `scrape_multiple()` returns a `dict[url] = content` and truncates internal return text to 2,000 chars (`scrape.py:221-229`)
- that is fine for display, bad for parsing/synthesis

What to do:

Refactor `scrape.py` into:

- `fetchers/http_fetch.py`
- `parsers/html_parser.py`
- `parsers/text_cleanup.py`
- `parsers/metadata.py`

Change fetch output from plain text to `FetchRecord` + `Document`.

Each fetched document should include:

- original URL
- final URL
- status code
- headers
- content type
- raw HTML/text
- extracted text
- title
- headings
- meta description
- outlinks
- content hash
- language guess

Keep the safety controls from current `scrape.py`, but do **not** truncate the internal text object to 2,000 chars. Only truncate in the UI.

## 6. Make extraction two-stage: deterministic first, normalized second

Current problem:

- `artifacts.py` extracts good baseline types, but outputs flat rows with `value`, `source_url`, `evidence`

What to build:

Create:

- `extractors/regex_iocs.py`
- `extractors/page_features.py`
- `normalize/canonicalize.py`
- `normalize/entities.py`

Stage 1 — deterministic artifact extraction:

Keep and extend the current patterns:

- onion URLs
- clearnet URLs
- emails
- domains
- IPv4s
- CVEs
- hashes
- crypto addresses
- handles

Add useful extras:

- usernames without `@` when strongly handle-like
- file paths
- PGP public key blocks/fingerprints
- Telegram/Matrix/Signal contact references where explicit
- onion hosts without scheme
- BTC/ETH transaction hashes if practical

Stage 2 — normalization:

- lower-case domains
- canonicalize URLs
- strip tracking/query noise when appropriate
- canonicalize emails
- normalize handles
- map URL -> domain / onion_service
- map email -> domain
- attach artifact offsets and evidence spans

This gives you actual entities instead of flat strings.

## 7. Add relationship extraction without needing a database yet

Create:

- `graph/build.py`
- `graph/render.py`

Relationships you can build deterministically right away:

- document `MENTIONS` entity
- URL `BELONGS_TO_DOMAIN` domain
- email `BELONGS_TO_DOMAIN` domain
- onion URL `BELONGS_TO_ONION_SERVICE` onion host
- entity `SEEN_WITH` entity in same document

Use `networkx` in memory for now.

Expose a graph tab in the UI.

This is a huge upgrade over the current flat source list.

## 8. Replace LLM result-picking with structured AI tasks

Current weak point:

- `filter_results()` asks the model to return a comma-separated list of indices (`llm.py:93-151`)
- that is brittle and low-value

Delete that pattern.

Instead create:

- `ai/tasks/relevance.py`
- `ai/tasks/translation.py`
- `ai/tasks/entity_extraction.py`
- `ai/tasks/claim_extraction.py`
- `ai/tasks/pivot_suggestions.py`
- `ai/tasks/report_synthesis.py`

Each task must return structured JSON.

Example claim extraction schema:

```python
class ClaimRecord(BaseModel):
    claim_text: str
    claim_type: str
    subject_entities: list[str]
    object_entities: list[str]
    evidence_doc_ids: list[str]
    evidence_quotes: list[str]
    confidence: float
```

Rules:

- AI never gets to output free-floating conclusions
- every claim must point to `doc_id`
- every claim should include short quoted evidence snippets
- deterministic extraction and enrichment happen first
- AI works on prepared evidence, not raw chaos

## 9. Build a proper pivot engine

Current repo already has first-pass and artifact-pivot ideas in `query_expansion.py`, but the pivoting is still shallow.

Build:

- `pipeline/pivots.py`

Scoring logic for pivots:

- high score: handle, email, onion URL, wallet, unique domain, CVE, malware hash
- medium score: unusual org name, alias, repeated phone/username pattern
- low score: generic words, generic forum terms, common domains

Second-pass rules:

- only pivot on the top N entities/artifacts
- no more than 2 passes
- keep a `seen_queries` set
- keep a `seen_entities` set
- prefer pivots that appear across multiple documents or sources

That gives you actual investigative expansion instead of just more search spam.

## 10. Add enrichment modules that actually improve intelligence quality

Create:

- `enrich/cve.py`
- `enrich/domain.py`
- `enrich/ip.py`
- `enrich/url.py`
- `enrich/wallet.py`
- `enrich/email_domain.py`

Examples:

- CVE -> NVD / CISA KEV metadata
- malicious URL/domain/hash -> abuse.ch family lookups
- URL/domain -> urlscan/public web context
- domain/IP -> DNS/hosting enrichment if you have APIs
- wallet -> public abuse metadata / chain explorer metadata
- domain/email -> breach-exposure metadata when lawfully authorized

This matters more than adding 20 more onion search engines.

## 11. Redesign synthesis so the final answer is built from claims, not raw pages

Current state:

- `generate_summary()` feeds sources, artifacts, query metadata, and raw scraped pages into one big prompt (`llm.py:318-352`)

Replace with:

1. `rank_documents_for_analysis()`
2. `extract_claims_from_documents()`
3. `group_claims_by_theme()`
4. `detect_conflicts_or_low-support_claims()`
5. `generate_case_brief_from_claims()`

Final report sections should be generated from:

- top entities
- top corroborated claims
- source groups
- pivot recommendations
- uncertainty / contradictions

Not directly from raw scraped text.

## 12. Redesign the Streamlit workflow around inspection, not just a final summary

Keep Streamlit, but change the tabs.

Recommended tabs:

1. Query plan
2. Source/connector results
3. Fetch status + parsed docs
4. Entities + artifacts
5. Relationships graph
6. AI claims
7. Pivot suggestions
8. Final synthesis

This is the right local single-user workflow.

## Exact file/folder shape I would build

```text
onionintel/
  app.py                       # Streamlit frontend only
  domain/
    models.py
  registry/
    schema.py
    loaders.py
    sources/
      search_engines.yml
      public_feeds.yml
      site_monitors.yml
  connectors/
    base.py
    search_engine.py
    api_feed.py
    site_monitor.py
  fetchers/
    http_fetch.py
  parsers/
    html_parser.py
    metadata.py
    text_cleanup.py
  extractors/
    regex_iocs.py
    page_features.py
  normalize/
    canonicalize.py
    entities.py
  enrich/
    cve.py
    domain.py
    ip.py
    url.py
    wallet.py
  ai/
    tasks/
      relevance.py
      translation.py
      entity_extraction.py
      claim_extraction.py
      pivot_suggestions.py
      report_synthesis.py
  graph/
    build.py
    render.py
  pipeline/
    run.py
    pivots.py
    stages.py
```

## What I would change first, in exact order

### Phase 1
1. Add `domain/models.py`
2. Build `pipeline/run.py`
3. Move orchestration out of `ui.py`
4. Keep current search engines temporarily

### Phase 2
5. Replace source loader/schema
6. Build connector framework
7. Refactor search results into `SearchHit`
8. Refactor scraping into `FetchRecord` and `Document`

### Phase 3
9. Upgrade extraction + normalization
10. Add relationships graph
11. Add pivot engine
12. Remove `llm.filter_results()` entirely

### Phase 4
13. Add enrichment connectors
14. Add structured AI tasks
15. Rebuild synthesis from claims, not raw pages
16. Redesign the Streamlit tabs around analysis objects

## Bottom line

For your stated goal, the answer is:

- do **not** start a brand-new product from absolute scratch
- do **not** keep the current UI-driven pipeline as the baseline either
- keep the repo, keep a handful of proven modules, and rebuild the core execution path inside it

That gives you the fastest route to a system that is materially better at:

- sourcing
- collection
- parsing
- extraction
- normalization
- pivots
- synthesis
- disciplined AI use

If you want the shortest version of the plan:

1. typed models
2. connector framework
3. pipeline module
4. rich document parsing
5. normalized entities/relationships
6. enrichment connectors
7. structured AI tasks
8. Streamlit as frontend only
