&#x20;# Scope note



Below is a full inspection of the current OnionIntel project at current state, along with inferences, notes, and recommendations on how to turn it into a substantially more capable dark web OSINT platform. Reference this file consistently, but only when relevant to any changes.



\---



\# SECTION 1 — Executive verdict



\## What this platform currently appears to be



\*\*Observed in repo:\*\* OnionIntel is a Dockerized, Streamlit-based dark-web OSINT investigation assistant. The README describes it as a local app for Tor-backed onion search, configurable onion/clearnet dark-web search sources, source-health recording, deduplication/annotation, artifact extraction, optional LLM-assisted query planning/summarization, and JSON audit trail saving. Evidence: `README.md:3`, `README.md:11-26`, `README.md:30-37`.



\*\*Observed in repo:\*\* The actual implementation is a single Python/Streamlit application with supporting modules:



\* `ui.py` orchestrates the user workflow.

\* `sources.py` searches configured search engines over Tor.

\* `scrape.py` fetches discovered pages.

\* `artifacts.py` extracts basic indicators with regex.

\* `query\_expansion.py` creates deterministic/LLM query plans.

\* `llm.py` and `llm\_utils.py` handle model routing, query refinement, triage, and report generation.

\* `investigations.py` saves/loading investigation JSON files.

\* `sources.yml` contains 27 configured search sources, 23 enabled and 4 disabled.

\* `Dockerfile`, `docker-compose.yml`, and `entrypoint.sh` provide a single-container Tor + Streamlit runtime.



\*\*Inference:\*\* This is not yet a dark-web intelligence platform. It is a useful \*\*prototype investigation workbench\*\* that performs federated searches against onion/dark-web search engines, scrapes selected results, extracts simple artifacts, and asks an LLM to summarize.



\## Core strengths



\*\*Observed in repo:\*\*



1\. \*\*Docker-first local setup.\*\* The repo includes a `Dockerfile`, `docker-compose.yml`, and `entrypoint.sh` that install Tor, wait for SOCKS availability, verify Tor routing, then run Streamlit. Evidence: `Dockerfile:1-26`, `docker-compose.yml:1-18`, `entrypoint.sh:1-35`.



2\. \*\*Configurable source registry.\*\* Search engines are defined in `sources.yml`, with fields like `name`, `url\_template`, `enabled`, `parser`, `timeout`, and `notes`. Evidence: `sources.yml:2-163`; loader schema in `sources.py:46-53`, `sources.py:123-149`.



3\. \*\*Tor-backed collection.\*\* `get\_tor\_session()` uses SOCKS5h proxying through `127.0.0.1:9050`; `entrypoint.sh` starts Tor before Streamlit. Evidence: `sources.py:163-182`, `entrypoint.sh:3-35`.



4\. \*\*Some safety caps.\*\* The scraper limits downloads to 1 MB, extracted text to 50,000 characters, returned text to 2,000 characters, redirect hops to 3, and accepted content types to HTML/XHTML/plain text. Evidence: `scrape.py:27-31`, `scrape.py:94-117`, `scrape.py:147-172`, `scrape.py:221-229`.



5\. \*\*Basic artifact extraction.\*\* It extracts onion URLs, clearnet URLs, emails, CVEs, hashes, Bitcoin/Ethereum addresses, handles, domains, and IPv4s with deterministic regex logic. Evidence: `artifacts.py:6-23`, `artifacts.py:38-52`, `artifacts.py:72-114`.



6\. \*\*Some prompt-injection awareness.\*\* Report prompts explicitly tell the model scraped text is untrusted and to ignore instructions inside scraped pages. Evidence: `llm.py:210-221`, `llm.py:237-247`, `llm.py:264-273`, `llm.py:291-300`.



7\. \*\*Unit tests exist.\*\* Tests cover artifact extraction, investigation metadata, source parsing/deduping, query expansion policy, and scraper behavior. Evidence: `tests/test\_artifacts.py:6-41`, `tests/test\_sources.py:10-228`, `tests/test\_query\_expansion.py:33-223`, `tests/test\_scrape.py:35-80`.



\## Core limitations



\*\*Observed in repo:\*\*



1\. \*\*No database.\*\* Persistence is timestamped JSON files under `investigations/`. Evidence: `investigations.py:6`, `investigations.py:27-50`.



2\. \*\*No queue, scheduler, worker system, or event-driven pipeline.\*\* Search, scrape, triage, summarization, artifact extraction, and saving are orchestrated inside `ui.py` when a user clicks “Run Investigation.” Evidence: workflow in `ui.py:543-743`.



3\. \*\*No API service.\*\* There is no FastAPI/Flask backend or documented API surface. The only user-facing interface is Streamlit. Evidence: repo file map and Streamlit entrypoint in `entrypoint.sh:34-35`.



4\. \*\*No authentication, authorization, RBAC, analyst accounts, or audit logs.\*\* Streamlit binds to `0.0.0.0:8501`; no login layer appears in `ui.py`, Docker, or config. Evidence: `entrypoint.sh:34-35`, `docker-compose.yml:8-9`, absence of auth modules.



5\. \*\*No normalized intelligence model.\*\* Search result records contain fields like `title`, `link`, `source`, `raw\_url`, `discovered\_at`, and `snippet`; artifacts contain value/source/evidence, but there are no normalized entities, claims, relationships, cases, alerts, or confidence objects. Evidence: `sources.py:292-321`, `artifacts.py:46-52`, `investigations.py:31-48`.



6\. \*\*Acquisition is mostly search-engine querying, not collection.\*\* The source registry is composed of onion/clearnet search engines and directories; the app queries their result pages. Evidence: `sources.yml:2-163`, `sources.py:434-482`, `sources.py:524-555`.



7\. \*\*No durable provenance/chain-of-custody model.\*\* The saved investigation includes `source\_provenance`, `search\_status`, `artifacts`, `scraped\_urls`, `query\_plan`, `query\_runs`, and `summary`, but not immutable content hashes, raw response storage, parser versions, fetch IDs, screenshots, analyst review state, or evidence versioning. Evidence: `investigations.py:31-48`.



8\. \*\*No source reliability or claim-confidence scoring.\*\* Current quality scoring is based mainly on substring matches and generic-infrastructure penalties. Evidence: `query\_expansion.py:456-497`, `query\_expansion.py:500-534`.



9\. \*\*LLM use is not evidence-grade.\*\* The LLM filters result indices and generates narrative reports, but outputs are not stored as structured claims tied to evidence IDs with confidence, contradiction status, or human review state. Evidence: `llm.py:93-151`, `llm.py:318-352`.



\## Evolve or rebuild?



\*\*Recommendation:\*\* Substantially rebuild the architecture.



\*\*Reason:\*\* The current repo can be evolved only as a \*\*prototype shell\*\*. The platform’s mission—lawful dark-web intelligence gathering, enrichment, verification, and synthesis—requires durable ingestion, normalized storage, provenance, analyst workflow, access control, scheduled monitoring, source reliability, graph/link analysis, and operational isolation. The current design is UI-driven and file-backed. That is the wrong foundation for serious intelligence work.



\## Blunt overall verdict



\*\*Observed in repo:\*\* The implementation is a local Streamlit investigation assistant, not a production CTI platform.



\*\*Inference:\*\* It is useful as a proof of concept for Tor-backed search aggregation, basic scraping, artifact extraction, and LLM-assisted reporting.



\*\*Recommendation:\*\* Treat this repository as a prototype to mine for reusable pieces, not as the core architecture of the future platform. Keep selected modules, replace the system design.



\---



\# SECTION 2 — Repository / system audit



\## High-level map of the repo



| Area                        | Files / folders                                                                               | Observed responsibility                                                                                                                                                                                                                                                        |

| --------------------------- | --------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |

| UI / workflow orchestration | `ui.py`                                                                                       | Streamlit interface, model selection, query input, source health checks, investigation execution, rendering, downloads. Evidence: `ui.py:198-810`.                                                                                                                             |

| Source registry             | `sources.yml`, `sources.py`                                                                   | Source config loading, parser selection, Tor sessions, source searching, dedupe, source status tracking. Evidence: `sources.yml:2-163`, `sources.py:46-157`, `sources.py:434-555`.                                                                                             |

| Scraping                    | `scrape.py`                                                                                   | Fetch discovered URLs, enforce redirect/download/text caps, parse text, track scrape status. Evidence: `scrape.py:27-31`, `scrape.py:118-238`.                                                                                                                                 |

| Artifact extraction         | `artifacts.py`                                                                                | Regex extraction of onion URLs, URLs, emails, CVEs, hashes, crypto addresses, handles, domains, IPs. Evidence: `artifacts.py:6-23`, `artifacts.py:72-114`.                                                                                                                     |

| Query expansion             | `query\_expansion.py`                                                                          | Intent classification, deterministic/LLM query planning, source searches across multiple query variants, quality scoring, exploratory pivots. Evidence: `query\_expansion.py:82-131`, `query\_expansion.py:189-261`, `query\_expansion.py:348-409`, `query\_expansion.py:456-534`. |

| LLM integration             | `llm.py`, `llm\_utils.py`                                                                      | Provider/model selection, query refinement, result triage, report prompts, routing by task. Evidence: `llm.py:20-45`, `llm.py:73-151`, `llm.py:318-352`, `llm\_utils.py:56-198`, `llm\_utils.py:324-388`.                                                                        |

| Investigation persistence   | `investigations.py`, `investigations/`                                                        | Save/load JSON investigation records. Evidence: `investigations.py:6`, `investigations.py:27-75`.                                                                                                                                                                              |

| Health checks               | `health.py`                                                                                   | Tor proxy check, LLM check, search engine pings, unhealthy source marking. Evidence: `health.py:12-25`, `health.py:28-91`, `health.py:94-143`.                                                                                                                                 |

| Deployment                  | `Dockerfile`, `docker-compose.yml`, `entrypoint.sh`, `.env.example`, `.streamlit/config.toml` | Single container with Tor + Streamlit; environment-configured model keys; Streamlit dev-style config. Evidence: `Dockerfile:1-26`, `docker-compose.yml:1-18`, `entrypoint.sh:1-35`, `.env.example:1-7`, `.streamlit/config.toml:1-7`.                                          |

| Tests                       | `tests/`                                                                                      | Unit tests for parsers, artifacts, query expansion, scraping, investigation persistence, LLM utilities. Evidence: `tests/test\_sources.py:10-228`, `tests/test\_query\_expansion.py:33-223`, `tests/test\_scrape.py:35-80`.                                                        |



\---



\## Key services, modules, containers, and responsibilities



\### Streamlit app



\*\*Observed in repo:\*\* `ui.py` is the central orchestrator. It renders the sidebar, chooses LLM models, lets the analyst set query context, checks Tor/source/LLM health, runs search, scrapes results, extracts artifacts, streams a summary, saves the investigation, and renders downloads. Evidence: `ui.py:221-395`, `ui.py:405-482`, `ui.py:543-810`.



\*\*Inference:\*\* The UI is doing too much. It is acting as the frontend, backend controller, job runner, state manager, and report renderer.



\*\*Recommendation:\*\* Split UI from backend execution. The future app should have a durable backend API, job scheduler, worker pool, storage layer, and separate analyst UI.



\---



\### Source search layer



\*\*Observed in repo:\*\* `sources.py` defines a `SourceConfig` dataclass with fields for name, URL template, enabled state, parser, timeout, and notes. Evidence: `sources.py:46-53`.



\*\*Observed in repo:\*\* Source configs are loaded from `sources.yml`, validated for a name and `{query}` placeholder, and filtered by enabled state. Evidence: `sources.py:123-157`.



\*\*Observed in repo:\*\* Search uses a Tor-backed `requests.Session` via SOCKS5h and runs configured sources concurrently with `ThreadPoolExecutor`. Evidence: `sources.py:163-182`, `sources.py:524-555`.



\*\*Observed in repo:\*\* Search result parsing is mostly HTML anchor/container parsing, with special parser branches for Ahmia, Torch, VormWeb, Lantern, OnionFind, and TorSearch. Evidence: `sources.py:347-403`.



\*\*Observed in repo:\*\* Result deduplication is based on normalized result link only. Evidence: `sources.py:485-497`.



\*\*Inference:\*\* This is a search aggregator, not a source acquisition framework. It does not have durable connectors, source-specific collection contracts, scheduled jobs, content versioning, or connector health metrics over time.



\*\*Recommendation:\*\* Replace this with a connector framework that supports search engines, feeds, APIs, known source monitors, ransomware leak trackers, paste/code search, phishing feeds, malware IOC feeds, domain/DNS intelligence, and crypto intelligence.



\---



\### Scraper



\*\*Observed in repo:\*\* `scrape.py` limits content size and redirect count, rejects non-HTTP(S) schemes, rejects credentials in URLs, and only extracts HTML/XHTML/plain text. Evidence: `scrape.py:27-31`, `scrape.py:45-53`, `scrape.py:94-117`, `scrape.py:147-172`.



\*\*Observed in repo:\*\* Onion URLs are fetched through Tor; clearweb URLs are fetched directly. Evidence: `scrape.py:130-145`.



\*\*Observed in repo:\*\* `scrape\_url` silently falls back to returning title-only content on failures. Evidence: `scrape.py:175-183`.



\*\*Inference:\*\* The scraper is intentionally simple and bounded, which is good for a prototype. But it is not a production crawler. It lacks robots/TOS policy, per-source rate limiting, fetch attempts, retry policy records, raw-response storage, screenshots, MIME/file quarantine, malware scanning, and link extraction.



\*\*Recommendation:\*\* Keep the safe-fetch principles, but rebuild as isolated crawler workers with immutable raw evidence storage, per-source policies, strict content handling, and auditable fetch metadata.



\---



\### Artifact extraction



\*\*Observed in repo:\*\* `artifacts.py` extracts artifacts from result titles, links, raw URLs, snippets, source names, and scraped content. Evidence: `artifacts.py:72-99`.



\*\*Observed in repo:\*\* Artifact rows store only `value`, `source\_url`, and an evidence text snippet. Evidence: `artifacts.py:46-52`.



\*\*Inference:\*\* This is useful first-pass extraction, but too shallow for CTI. It has no normalization table, confidence score, source relationship, first/last seen timestamps, entity type ontology, or resolved canonical identity.



\*\*Recommendation:\*\* Convert extracted artifacts into typed entities and indicators with provenance, confidence, enrichment state, and relationships.



\---



\### Query expansion and search planning



\*\*Observed in repo:\*\* `query\_expansion.py` classifies intent into categories such as person, handle, email/domain, technical IOC, crypto, org, or general. Evidence: `query\_expansion.py:82-131`.



\*\*Observed in repo:\*\* It builds deterministic query variants and optionally asks an LLM to produce a bounded JSON query plan. Evidence: `query\_expansion.py:189-261`, `query\_expansion.py:557-625`, `query\_expansion.py:656-692`.



\*\*Observed in repo:\*\* It applies policy controls, including suppression of sensitive personal probes in conservative mode unless context allows them. Evidence: `query\_expansion.py:741-779`.



\*\*Observed in repo:\*\* Exploratory mode can derive artifact pivot queries from first-pass results. Evidence: `query\_expansion.py:348-409`, `query\_expansion.py:412-440`.



\*\*Inference:\*\* This is one of the more valuable pieces of the repo. The intent model and policy constraints are primitive but directionally right.



\*\*Recommendation:\*\* Reuse the concept, but move query planning into a structured backend service with persisted query plans, analyst approval gates for sensitive pivots, and per-query provenance.



\---



\### LLM integration



\*\*Observed in repo:\*\* The repo supports several providers through LangChain wrappers: OpenAI, Anthropic, Google, Ollama, OpenRouter, and llama.cpp-compatible endpoints. Evidence: `llm\_utils.py:1-8`, `llm\_utils.py:56-191`, `llm.py:20-45`.



\*\*Observed in repo:\*\* The LLM is used for query refinement, result filtering, query expansion, and report generation. Evidence: `llm.py:73-151`, `query\_expansion.py:189-261`, `llm.py:318-352`.



\*\*Observed in repo:\*\* Result filtering asks the model to select up to 20 result indices from a list; if parsing fails, it falls back to the first 20. Evidence: `llm.py:93-151`.



\*\*Observed in repo:\*\* Report generation sends query data, sources, deterministic artifacts, query plan, query runs, and scraped pages into a prompt. Evidence: `llm.py:318-352`.



\*\*Inference:\*\* The LLM layer is convenience-oriented, not intelligence-grade. It produces narrative output, but not a structured claim graph with evidence-backed confidence.



\*\*Recommendation:\*\* Replace report-only LLM usage with a structured AI pipeline: extraction, translation, summarization, relationship extraction, contradiction detection, lead scoring, and case brief generation—all constrained to evidence IDs and human review.



\---



\### Investigation persistence



\*\*Observed in repo:\*\* `save\_investigation()` writes JSON files named `investigation\_%Y%m%d\_%H%M%S.json`. Evidence: `investigations.py:27-50`.



\*\*Observed in repo:\*\* Saved fields include timestamp, query, refined query, model, preset, sources, source provenance, search status, artifacts, scraped URLs, query plan, query runs, query expansion mode, intent metadata, model routing, and summary. Evidence: `investigations.py:31-48`.



\*\*Observed in repo:\*\* `load\_investigations()` glob-loads JSON files and adds defaults for missing fields, swallowing exceptions. Evidence: `investigations.py:53-75`.



\*\*Inference:\*\* This is adequate for demo persistence, but not for evidence-grade auditability. JSON files are not a data model.



\*\*Recommendation:\*\* Move to normalized storage with immutable raw evidence objects and structured records for runs, fetches, documents, entities, claims, cases, alerts, analyst actions, and reports.



\---



\## Current ingestion pipeline



\*\*Observed in repo:\*\* The current pipeline is essentially:



1\. User enters query in Streamlit. Evidence: `ui.py:405-428`.

2\. User optionally enters AI context: aliases, geography, handles, organization, emails/domains, timeframe, freeform context. Evidence: `ui.py:430-482`.

3\. App builds model-routing plan. Evidence: `ui.py:564-568`, `llm\_utils.py:324-354`.

4\. App loads LLMs. Evidence: `ui.py:570-579`.

5\. App refines query with LLM. Evidence: `ui.py:581-587`, `llm.py:73-90`.

6\. App checks Tor. Evidence: `ui.py:589-591`, `health.py:12-25`.

7\. App searches sources. If expansion is off, it calls `cached\_search`; otherwise it calls `run\_expanded\_search`. Evidence: `ui.py:604-649`, `query\_expansion.py:348-409`.

8\. App optionally filters results with LLM. Evidence: `ui.py:668-673`, `llm.py:93-151`.

9\. App scrapes selected URLs. Evidence: `ui.py:678-685`, `scrape.py:185-238`.

10\. App extracts artifacts and annotates results with scraped direct mentions. Evidence: `ui.py:688-696`, `artifacts.py:72-114`, `query\_expansion.py:508-521`.

11\. App generates final LLM report. Evidence: `ui.py:698-720`, `llm.py:318-352`.

12\. App saves JSON investigation. Evidence: `ui.py:722-743`, `investigations.py:27-50`.



\*\*Inference:\*\* This is not an ingestion pipeline in the platform sense. It is an interactive synchronous workflow.



\*\*Recommendation:\*\* Future ingestion should be asynchronous, source-driven, scheduled, resumable, retryable, and independent from the analyst UI.



\---



\## Current storage model



\*\*Observed in repo:\*\* Storage is local JSON under `investigations/`. Evidence: `investigations.py:6`, `investigations.py:27-75`.



\*\*Observed in repo:\*\* There is no SQL schema, no migrations, no graph database config, no search index config, and no object store config in the repo.



\*\*Inference:\*\* Storage is the most serious technical gap. The platform cannot support historical tracking, cross-case search, entity resolution, source reliability, evidence traceability, or team workflows with local JSON files.



\*\*Recommendation:\*\* Use:



\* PostgreSQL for normalized intelligence records.

\* S3/MinIO-compatible object storage for raw evidence snapshots.

\* OpenSearch/Elasticsearch for full-text search.

\* Neo4j/ArangoDB/Postgres AGE for relationship graph.

\* Redis only for caching/queues, not as source of truth.



\---



\## Current enrichment / analysis logic



\*\*Observed in repo:\*\* Enrichment today consists of:



\* LLM query refinement. Evidence: `llm.py:73-90`.

\* LLM result triage. Evidence: `llm.py:93-151`.

\* Deterministic artifact extraction. Evidence: `artifacts.py:6-114`.

\* Quality annotation from query-term matching and generic-infrastructure penalties. Evidence: `query\_expansion.py:456-497`.

\* Scraped text direct-mention annotation. Evidence: `query\_expansion.py:508-521`.

\* LLM narrative summarization. Evidence: `llm.py:318-352`.



\*\*Inference:\*\* This is not enough for intelligence analysis. It lacks enrichment against public CTI feeds, domain/DNS history, malware reputation, wallet/transaction intelligence, entity resolution, clustering, temporal change detection, contradiction tracking, and confidence scoring.



\*\*Recommendation:\*\* Add deterministic enrichment first, then AI synthesis. AI should not be the backbone of trust scoring or evidence handling.



\---



\## Current UI / analyst workflow



\*\*Observed in repo:\*\* The analyst workflow is a Streamlit page with sidebar model/source controls, query input, context expansion, health checks, previous investigation selection, run button, results, source audit, artifacts, summary, JSON download, and markdown download. Evidence: `ui.py:221-395`, `ui.py:405-482`, `ui.py:485-533`, `ui.py:745-810`.



\*\*Observed in repo:\*\* Past investigations are loaded from local JSON files. Evidence: `ui.py:377-395`, `investigations.py:53-75`.



\*\*Inference:\*\* The workflow is “run a search and produce a report,” not “manage an investigation.” There are no cases, watchlists, saved entities, analyst assignments, evidence review queues, annotations, dispositions, escalations, or alerts.



\*\*Recommendation:\*\* Build a real analyst workflow: watchlists → alerts → triage → case → evidence review → claims → confidence → report.



\---



\## Current deployment / Docker / orchestration model



\*\*Observed in repo:\*\* One container installs Python, Tor, and app dependencies, copies source, exposes port 8501, and uses an entrypoint. Evidence: `Dockerfile:1-26`.



\*\*Observed in repo:\*\* `docker-compose.yml` runs a single service named `onionintel`, exposes `8501:8501`, mounts the repo into `/app`, and mounts `./investigations`. Evidence: `docker-compose.yml:1-18`.



\*\*Observed in repo:\*\* `entrypoint.sh` starts Tor in the same container, waits for `127.0.0.1:9050`, confirms Tor connectivity, and runs Streamlit on `0.0.0.0:8501`. Evidence: `entrypoint.sh:3-35`.



\*\*Observed in repo:\*\* The container does not define a non-root user, healthcheck, network policy, separate Tor service, separate worker, or orchestrated backend.



\*\*Inference:\*\* This is fine for local demo use. It is not production-safe.



\*\*Recommendation:\*\* Separate services:



\* UI

\* API

\* scheduler

\* ingestion workers

\* crawler/Tor workers

\* enrichment workers

\* AI workers

\* database

\* object store

\* search index

\* graph DB

\* metrics/logging



\---



\## Security findings



\*\*Observed in repo:\*\*



\* API keys are loaded from environment variables and `.env`; `.env.example` shows provider keys. Evidence: `config.py:1-26`, `.env.example:1-7`.

\* No secrets manager integration appears in the repo.

\* Streamlit binds to `0.0.0.0`. Evidence: `entrypoint.sh:34-35`.

\* No auth/RBAC code appears in `ui.py` or elsewhere.

\* The Docker container appears to run as root by default because no `USER` directive is set. Evidence: `Dockerfile:1-26`.

\* Tor and app run in the same container/process environment. Evidence: `Dockerfile:4-5`, `entrypoint.sh:3-35`.

\* `ui.py` uses `unsafe\_allow\_html=True` for injected CSS and download link rendering. Evidence: `ui.py:205-218`, `ui.py:804-808`.



\*\*Inference:\*\* The app should not be exposed to the internet or used by a team without hardening.



\*\*Recommendation:\*\* Add authentication, RBAC, audit logs, secrets management, crawler isolation, non-root containers, egress controls, encrypted storage, and prompt-injection defenses.



\---



\## Observability findings



\*\*Observed in repo:\*\*



\* Source search records per-source status in memory and saved investigations. Evidence: `sources.py:524-555`, `investigations.py:31-48`.

\* Scraping records last scrape status in memory. Evidence: `scrape.py:185-238`.

\* Health checks exist for Tor, LLM, and search engines. Evidence: `health.py:12-143`.



\*\*Observed in repo:\*\* There is no Prometheus/OpenTelemetry setup, no structured logs, no central logging, no per-job trace IDs, no retry metrics, no dead-letter queue, and no alerting.



\*\*Inference:\*\* The current observability is UI-local, not operational.



\*\*Recommendation:\*\* Add structured logging, OpenTelemetry traces, Prometheus metrics, job IDs, connector health dashboards, per-source error budgets, and alerting.



\---



\## Maintainability findings



\*\*Observed in repo:\*\*



\* Tests exist, which is positive.

\* The source registry parser is a custom “simple YAML” parser rather than a real YAML parser and schema validator. Evidence: `sources.py:83-120`.

\* Search parser logic is centralized in one file with branch-specific parser names. Evidence: `sources.py:347-403`.

\* Streamlit orchestrates backend logic directly. Evidence: `ui.py:543-743`.



\*\*Inference:\*\* The code is understandable but will become brittle as sources, parsers, workflows, and analyst features grow.



\*\*Recommendation:\*\* Move to modular connectors, formal schemas, typed models, backend services, and CI.



\---



\## Scalability findings



\*\*Observed in repo:\*\*



\* Search concurrency uses `ThreadPoolExecutor`, max workers capped at 16. Evidence: `sources.py:524-555`.

\* Scrape concurrency uses `ThreadPoolExecutor`, max workers capped at 16. Evidence: `scrape.py:185-238`.

\* UI caching uses `@st.cache\_data(ttl=200)` for search and scrape. Evidence: `ui.py:62-71`.



\*\*Inference:\*\* This scales only to small interactive investigations. It cannot support continuous monitoring, high-volume source ingestion, concurrent analysts, durable retries, or historical analytics.



\*\*Recommendation:\*\* Add queues, workers, persistence, job state, scaling policies, and backpressure.



\---



\## Missing or weak components



\*\*Observed in repo:\*\* Missing or weak components include:



\* Database/schema/migrations.

\* API backend.

\* Auth/RBAC.

\* Case management.

\* Watchlists and alerts.

\* Scheduler.

\* Queue/event bus.

\* Durable raw evidence store.

\* Source reliability scoring.

\* Claim confidence scoring.

\* Entity resolution.

\* Deduplication beyond URL.

\* Temporal tracking.

\* Graph/link analysis.

\* Analyst review workflow.

\* Multilingual pipeline.

\* Structured AI outputs.

\* CI/CD.

\* Secrets management.

\* Audit logs.

\* Production observability.

\* Crawler sandboxing/isolation.



\---



\# SECTION 3 — Gap analysis



\## Gap table



| Capability                          | Observed in repo                                                                                                                               | What is missing or weak                                                                                                                                         | Why it matters                                                                                                                        | Issue type                 |

| ----------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- | -------------------------- |

| Source acquisition layer            | Search sources are listed in `sources.yml`; queries are sent to configured URL templates. Evidence: `sources.yml:2-163`, `sources.py:434-482`. | No real connector framework, no source contracts, no API connectors, no feed ingestion, no source-type taxonomy, no legal/TOS metadata.                         | A serious platform needs repeatable, auditable collection across search engines, feeds, APIs, public trackers, and monitored sources. | Architecture + workflow    |

| Scheduling / crawling orchestration | Collection runs only when user clicks “Run Investigation.” Evidence: `ui.py:543-743`.                                                          | No scheduler, queue, job state, retries, backoff, dead-letter queue, source cadence, or crawl frontier.                                                         | Monitoring requires continuous collection, not one-off interactive searches.                                                          | Architecture               |

| Parsing / normalization             | Some HTML parsers exist for specific search sources and a generic parser. Evidence: `sources.py:347-403`.                                      | No parser versioning, normalized document model, source-specific schema, content-type pipeline, or parse confidence.                                            | Intelligence records must be comparable across sources and time.                                                                      | Code + data                |

| Metadata extraction                 | Basic artifacts are regex extracted. Evidence: `artifacts.py:6-114`.                                                                           | No page metadata, language, timestamps, authors, titles, redirects, canonical URLs, screenshots, HTTP headers, content hash, parser hash, or offset mapping.    | Metadata often determines whether evidence is trustworthy and current.                                                                | Data + architecture        |

| Entity resolution                   | None beyond raw artifact value dedupe. Evidence: `artifacts.py:46-52`.                                                                         | No canonical entity IDs, alias mapping, handle/email/person/org resolution, wallet clustering, infrastructure clustering, or source-independent identity model. | Without entity resolution, analysts drown in duplicates and miss relationships.                                                       | Architecture + data        |

| Deduplication / clustering          | Search result dedupe is by normalized link. Evidence: `sources.py:485-497`.                                                                    | No content hashing, near-duplicate detection, mirror clustering, canonical onion mapping, claim dedupe, or actor/listing clustering.                            | Dark-web content is frequently mirrored, copied, renamed, and reposted.                                                               | Architecture + data        |

| Trust scoring / source reliability  | No reliability model; unhealthy sources are in-process status only. Evidence: `sources.py:37-39`, `sources.py:508-521`.                        | No source reliability history, false-positive rate, moderation/source-type weighting, parser stability, or source lineage.                                      | Analysts need to know whether a source is primary, aggregator, stale, deceptive, or unreliable.                                       | Architecture + workflow    |

| Temporal tracking                   | `discovered\_at` appears on result objects. Evidence: `sources.py:292-321`.                                                                     | No first\_seen/last\_seen lifecycle per entity/claim/source, change detection, resurrection detection, stale scoring, or historical timelines.                    | Investigations depend on when something first appeared, changed, disappeared, or reappeared.                                          | Data + architecture        |

| Knowledge graph / link analysis     | None.                                                                                                                                          | No graph of entities, documents, claims, source relationships, wallets, infrastructure, handles, malware, orgs, cases.                                          | Relationship analysis is central to CTI and investigations.                                                                           | Architecture               |

| Alerting / watchlists               | None.                                                                                                                                          | No watchlists, scheduled matching, alert rules, alert severity, alert dedupe, suppression, or escalation.                                                       | Serious platforms monitor continuously and alert analysts when relevant changes occur.                                                | Workflow + architecture    |

| Analyst case management             | Past investigations can be loaded from JSON. Evidence: `ui.py:377-395`, `investigations.py:53-75`.                                             | No cases, assignments, notes, evidence review state, tags, dispositions, collaboration, report approvals.                                                       | Investigations are workflows, not single generated summaries.                                                                         | Workflow                   |

| Evidence traceability               | Saved JSON includes query/source/artifact metadata. Evidence: `investigations.py:31-48`.                                                       | No immutable raw evidence store, content hashes, screenshots, offsets, chain-of-custody, analyst actions, or evidence versioning.                               | Claims must be defensible and reproducible.                                                                                           | Architecture + data        |

| AI summarization                    | LLM generates summary from scraped pages and artifacts. Evidence: `llm.py:318-352`.                                                            | Narrative report is not structured around claim IDs/evidence IDs; no hallucination guardrail beyond prompt instructions.                                        | AI summaries can mislead unless tied to evidence and review.                                                                          | Code + workflow            |

| AI-assisted hypothesis generation   | Not explicit. Query expansion pivots exist. Evidence: `query\_expansion.py:348-440`.                                                            | No hypothesis object, competing hypotheses, evidence-for/against, analyst review, or confidence deltas.                                                         | Investigations need explicit reasoning, not hidden narrative leaps.                                                                   | Workflow + AI architecture |

| Contradiction detection             | None.                                                                                                                                          | No claim comparison, conflict detection, stale-vs-current resolution, or analyst adjudication.                                                                  | Dark-web data is often false, copied, deceptive, or outdated.                                                                         | Architecture + AI/data     |

| Multilingual support                | No language detection or translation pipeline.                                                                                                 | No language field, translation memory, original/translated evidence linkage, regional source handling.                                                          | Dark-web/fraud/CTI coverage is multilingual by nature.                                                                                | Architecture + data        |

| Operational security                | Tor exists. Evidence: `sources.py:163-182`, `entrypoint.sh:3-35`.                                                                              | No crawler isolation, separate Tor workers, egress policies, sandboxing, content quarantine, or operational compartmentalization.                               | Hostile content and deceptive sources create operational and legal risk.                                                              | Security architecture      |

| Secrets handling                    | Env vars and `.env`. Evidence: `config.py:19-26`, `.env.example:1-7`.                                                                          | No vault/secrets manager, rotation, per-service secret scopes, secret audit, or key leak prevention.                                                            | Production systems need accountable secret handling.                                                                                  | Security                   |

| Access controls                     | None visible.                                                                                                                                  | No authentication, RBAC, SSO, API tokens, analyst roles, case-level permissions.                                                                                | CTI data can include sensitive PII and legal-risk material.                                                                           | Security + workflow        |

| Observability                       | Health checks and status UI exist. Evidence: `health.py:12-143`, `ui.py:91-123`.                                                               | No central logs, metrics, tracing, source SLOs, job telemetry, retry dashboards, or alerts.                                                                     | Operators need to know what failed, when, why, and whether data is stale.                                                             | Ops architecture           |

| Error handling / retries            | Scraper has retries; source session disables retries. Evidence: `scrape.py:56-78`, `sources.py:173-181`.                                       | No durable retry state, DLQ, exponential backoff per source, or postmortem visibility.                                                                          | Collection failures are normal; systems must recover cleanly.                                                                         | Architecture + code        |



\## Blunt gap conclusion



\*\*Observed in repo:\*\* The current app has the beginnings of search, scraping, artifacts, LLM summary, source health, and JSON records.



\*\*Inference:\*\* It lacks almost every component that makes an intelligence platform serious: durable collection, normalized data, provenance, confidence, analyst workflow, graph analysis, monitoring, and security.



\*\*Recommendation:\*\* Do not try to patch this into production by adding more sources and another LLM prompt. Build the intelligence platform architecture first.



\---



\# SECTION 4 — Recommended future-state architecture



\## Design principle



\*\*Recommendation:\*\* Redesign the platform around this model:



> \*\*Source connectors collect evidence. Deterministic pipelines normalize and enrich it. AI helps extract, summarize, translate, and synthesize, but every claim must point back to immutable evidence. Analysts review and approve high-impact findings.\*\*



The current repo is built around a one-shot Streamlit workflow. The future-state system should be built around durable intelligence objects.



\---



\## Service boundaries



\### 1. Analyst UI



\*\*Recommendation:\*\* Keep Streamlit only for prototypes. For a serious platform, build a dedicated analyst UI.



Core views:



\* Watchlists.

\* Alerts.

\* Cases.

\* Evidence browser.

\* Entity graph.

\* Claim/confidence review.

\* Timeline view.

\* Source health.

\* Report builder.

\* Admin/source registry.



\*\*Why:\*\* `ui.py` currently mixes frontend and backend orchestration. Evidence: `ui.py:543-743`.



\---



\### 2. API service



\*\*Recommendation:\*\* Add a backend API, preferably FastAPI or similar.



Core API resources:



\* `/sources`

\* `/connectors`

\* `/collection-jobs`

\* `/fetches`

\* `/documents`

\* `/artifacts`

\* `/entities`

\* `/relationships`

\* `/claims`

\* `/watchlists`

\* `/alerts`

\* `/cases`

\* `/reports`

\* `/audit-events`



\*\*Why:\*\* The current repo has no API service. A serious platform needs stable interfaces for UI, jobs, integrations, and automation.



\---



\### 3. Source registry and compliance service



\*\*Recommendation:\*\* Replace `sources.yml` with a validated source registry.



Minimum source fields:



```text

source\_id

name

source\_type

access\_method

base\_url\_or\_api

requires\_auth

legal\_basis

terms\_notes

collection\_cadence

rate\_limit

parser\_id

risk\_level

enabled

last\_reviewed\_at

reviewed\_by

jurisdiction\_notes

allowed\_content\_types

retention\_policy

```



\*\*Observed in repo:\*\* Current source config only has name, URL template, enabled, parser, timeout, and notes. Evidence: `sources.py:46-53`, `sources.yml:2-163`.



\*\*Why:\*\* Dark-web and adjacent collection needs compliance controls, not just URL templates.



\---



\### 4. Connector runner service



\*\*Recommendation:\*\* Implement source-specific connectors as versioned modules.



Connector types:



\* Search-engine connector.

\* Public CTI feed connector.

\* API connector.

\* Ransomware/leak tracker connector.

\* Phishing feed connector.

\* Domain/DNS intelligence connector.

\* Crypto intelligence connector.

\* Paste/code search connector.

\* Known-source monitor.

\* Manual upload/import connector.



Each connector should output a common envelope:



```json

{

&#x20; "connector\_id": "urlhaus\_api",

&#x20; "connector\_version": "1.2.0",

&#x20; "source\_id": "abusech\_urlhaus",

&#x20; "collection\_job\_id": "...",

&#x20; "fetched\_at": "...",

&#x20; "raw\_artifact\_ref": "...",

&#x20; "content\_hash\_sha256": "...",

&#x20; "normalized\_documents": \[],

&#x20; "extracted\_entities": \[],

&#x20; "errors": \[]

}

```



\*\*Observed in repo:\*\* Current `sources.py` uses parser branches and `fetch\_source\_results()` for result pages. Evidence: `sources.py:347-482`.



\*\*Why:\*\* The repo’s parser model will not scale to dozens of source types.



\---



\### 5. Scheduler / orchestrator



\*\*Recommendation:\*\* Add a durable scheduler.



Good choices:



\* \*\*Celery + Redis/RabbitMQ\*\* for a practical near-term system.

\* \*\*Temporal\*\* if you need long-running, auditable workflows with retries, compensation, and complex state.

\* \*\*Prefect/Airflow\*\* if collection jobs are more batch-oriented.



Given this repo’s current state, start with \*\*Celery/RQ + Redis\*\* for 30–60 days, then evaluate Temporal when workflows become more complex.



\*\*Observed in repo:\*\* Collection is user-triggered in `ui.py`. Evidence: `ui.py:543-743`.



\---



\### 6. Queue / event-driven design



\*\*Recommendation:\*\* Use events between pipeline stages.



Example event flow:



```text

SourceScheduled

&#x20; -> CollectionJobCreated

&#x20; -> FetchAttemptCompleted

&#x20; -> RawEvidenceStored

&#x20; -> DocumentParsed

&#x20; -> ArtifactsExtracted

&#x20; -> EntitiesResolved

&#x20; -> EnrichmentRequested

&#x20; -> ClaimsExtracted

&#x20; -> AlertMatched

&#x20; -> AnalystReviewRequired

&#x20; -> ReportGenerated

```



\*\*Why:\*\* Intelligence collection is naturally asynchronous. Fetches fail, sources go down, parsers break, and enrichment may take time.



\---



\## Ingestion architecture



\### Current ingestion



\*\*Observed in repo:\*\* User query → source search → result filtering → scrape selected pages → extract artifacts → summarize → save JSON. Evidence: `ui.py:543-743`.



\### Future ingestion



\*\*Recommendation:\*\*



```text

Source Registry

&#x20; -> Scheduler

&#x20; -> Connector Runner

&#x20; -> Isolated Fetch Worker

&#x20; -> Raw Evidence Store

&#x20; -> Parser / Normalizer

&#x20; -> Artifact Extractor

&#x20; -> Entity Resolver

&#x20; -> Enrichment Pipeline

&#x20; -> Claim Extractor

&#x20; -> Search Index

&#x20; -> Graph Store

&#x20; -> Alert Engine

&#x20; -> Analyst Review

```



\### Job model



Use these durable objects:



```text

CollectionJob

FetchAttempt

RawEvidence

ParsedDocument

ExtractedArtifact

Entity

Relationship

Claim

EnrichmentResult

Alert

Case

Report

AuditEvent

```



\---



\## Source connector framework



\*\*Recommendation:\*\* Build connectors around a strict interface:



```python

class Connector:

&#x20;   connector\_id: str

&#x20;   version: str

&#x20;   source\_type: SourceType



&#x20;   def plan(self, source\_config, watchlist=None) -> list\[FetchRequest]:

&#x20;       ...



&#x20;   def fetch(self, request: FetchRequest) -> FetchResult:

&#x20;       ...



&#x20;   def parse(self, fetch\_result: FetchResult) -> list\[ParsedDocument]:

&#x20;       ...



&#x20;   def normalize(self, parsed: ParsedDocument) -> NormalizedDocument:

&#x20;       ...

```



Minimum connector features:



\* Per-source rate limit.

\* Retry policy.

\* Parser version.

\* Terms/compliance notes.

\* Supported content types.

\* Authentication method.

\* Error taxonomy.

\* Metrics emission.

\* Test fixtures.



\*\*Observed in repo:\*\* Current source loader validates only minimal fields and parses flat YAML-like data. Evidence: `sources.py:83-149`.



\---



\## Storage layers



\### 1. PostgreSQL



Use for normalized platform data:



\* Sources.

\* Connectors.

\* Jobs.

\* Fetch attempts.

\* Documents.

\* Artifacts.

\* Entities.

\* Relationships.

\* Claims.

\* Cases.

\* Alerts.

\* Reports.

\* Analyst actions.

\* Audit logs.



\*\*Why:\*\* You need transactions, constraints, history, permissions, and joins.



\---



\### 2. Object storage: S3 / MinIO



Use for immutable raw evidence:



\* Raw HTML/text.

\* HTTP response bodies.

\* Screenshots.

\* Extracted page text.

\* Downloaded public documents when lawful and allowed.

\* Parser outputs.

\* Model input/output artifacts.



Store with SHA-256 hashes and object versioning.



\*\*Why:\*\* JSON investigation files cannot serve as evidence storage. Evidence: current JSON-only save in `investigations.py:27-50`.



\---



\### 3. Search index: OpenSearch / Elasticsearch



Use for:



\* Full-text document search.

\* Artifact search.

\* Entity search.

\* Source search.

\* Case search.

\* Timeline queries.

\* Analyst filtering.



\*\*Why:\*\* Analysts need fast search across historical evidence.



\---



\### 4. Graph layer



Use Neo4j, ArangoDB, JanusGraph, or Postgres AGE.



Graph nodes:



\* Person.

\* Organization.

\* Handle.

\* Email.

\* Domain.

\* IP.

\* Onion service.

\* URL.

\* Crypto address.

\* Malware family.

\* CVE.

\* Threat actor.

\* Leak listing.

\* Marketplace listing.

\* Document.

\* Claim.

\* Source.

\* Case.



Graph edges:



\* `MENTIONED\_IN`

\* `USES`

\* `HOSTED\_ON`

\* `RESOLVES\_TO`

\* `SAME\_AS`

\* `ALIAS\_OF`

\* `CLAIMS`

\* `CORROBORATES`

\* `CONTRADICTS`

\* `FIRST\_SEEN\_IN`

\* `LAST\_SEEN\_IN`

\* `LINKS\_TO`

\* `PART\_OF\_CASE`



\*\*Why:\*\* The current repo has no relationship model. Serious investigations depend on links.



\---



\### 5. Vector store



Use cautiously.



\*\*Recommendation:\*\* Use embeddings for semantic search and clustering, not as the source of truth. Store embedding metadata with document IDs and evidence IDs. Use pgvector or OpenSearch k-NN before adding a separate vector DB.



\*\*Why:\*\* Vector search is useful for finding related posts/listings, but exact provenance and deterministic search remain mandatory.



\---



\## Search stack



\*\*Recommendation:\*\* Combine:



\* Exact search: keywords, IOCs, URLs, hashes, emails, handles.

\* Full-text search: OpenSearch/Elasticsearch.

\* Structured filters: source, time, confidence, entity type, case.

\* Graph traversal: relationships and link analysis.

\* Semantic search: similar claims/documents/listings.

\* Temporal search: first seen, last seen, changed since, disappeared.



\*\*Observed in repo:\*\* Current search is external source search plus local in-memory result ranking. Evidence: `sources.py:524-555`, `query\_expansion.py:456-534`.



\---



\## Graph / relationship layer



\*\*Recommendation:\*\* Build graph creation in stages:



1\. Deterministic edges:



&#x20;  \* URL → domain.

&#x20;  \* onion URL → onion service.

&#x20;  \* email → domain.

&#x20;  \* IP → ASN.

&#x20;  \* CVE → product/vendor from NVD/CISA.

&#x20;  \* crypto address → blockchain.

&#x20;  \* document → extracted artifact.



2\. Enriched edges:



&#x20;  \* domain → passive DNS.

&#x20;  \* IP → hosting provider.

&#x20;  \* URL → urlscan result.

&#x20;  \* malware hash → malware family/feed.

&#x20;  \* wallet → public abuse reports.



3\. AI-assisted edges:



&#x20;  \* actor alias.

&#x20;  \* claimed victim.

&#x20;  \* claimed breach.

&#x20;  \* relationship between handle and organization.

&#x20;  \* narrative event extraction.



4\. Analyst-approved edges:



&#x20;  \* attribution.

&#x20;  \* real-world identity.

&#x20;  \* high-risk PII claims.

&#x20;  \* fraud/criminal association.



\---



\## Enrichment pipeline



\*\*Recommendation:\*\* Deterministic enrichment should run before AI synthesis.



Examples:



\* URL canonicalization.

\* Hashing.

\* MIME detection.

\* Language detection.

\* IOC extraction.

\* CVE lookup.

\* CISA KEV lookup.

\* DNS/WHOIS/passive DNS enrichment.

\* ASN/hosting enrichment.

\* URL reputation.

\* Malware feed lookup.

\* Crypto abuse report lookup.

\* Phishing feed lookup.

\* Known source reliability lookup.

\* Temporal first/last seen.



\*\*Observed in repo:\*\* Current enrichment is regex artifacts plus substring quality scoring. Evidence: `artifacts.py:6-114`, `query\_expansion.py:456-497`.



\---



\## AI pipeline



\*\*Recommendation:\*\* AI should be a service, not embedded ad hoc in UI execution.



Pipeline:



```text

Document chunking

&#x20; -> language detection

&#x20; -> translation if needed

&#x20; -> entity extraction

&#x20; -> relationship extraction

&#x20; -> claim extraction

&#x20; -> claim-to-evidence linking

&#x20; -> contradiction detection

&#x20; -> synthesis / briefing

&#x20; -> analyst review

```



Each model output must include:



```json

{

&#x20; "task": "claim\_extraction",

&#x20; "model": "...",

&#x20; "model\_version": "...",

&#x20; "input\_evidence\_ids": \["..."],

&#x20; "output\_claims": \[

&#x20;   {

&#x20;     "claim\_text": "...",

&#x20;     "subject": "...",

&#x20;     "predicate": "...",

&#x20;     "object": "...",

&#x20;     "evidence\_ids": \["..."],

&#x20;     "confidence": 0.62,

&#x20;     "requires\_human\_review": true

&#x20;   }

&#x20; ],

&#x20; "errors": \[],

&#x20; "created\_at": "..."

}

```



\*\*Observed in repo:\*\* Current LLM outputs are mostly narrative or index lists. Evidence: `llm.py:93-151`, `llm.py:318-352`.



\---



\## Evidence / provenance model



\*\*Recommendation:\*\* Every piece of intelligence should trace to raw evidence.



Minimum evidence fields:



```text

evidence\_id

source\_id

connector\_id

connector\_version

collection\_job\_id

fetch\_attempt\_id

retrieval\_started\_at

retrieval\_finished\_at

url

canonical\_url

redirect\_chain

http\_status

content\_type

content\_length

raw\_object\_uri

raw\_sha256

text\_object\_uri

text\_sha256

screenshot\_object\_uri

screenshot\_sha256

parser\_id

parser\_version

language

first\_seen\_at

last\_seen\_at

legal\_policy\_id

retention\_policy\_id

```



\*\*Observed in repo:\*\* Current saved investigations include search status, artifacts, scraped URLs, query runs, and summary, but no immutable evidence IDs/hashes. Evidence: `investigations.py:31-48`.



\---



\## Analyst-facing workflow



\*\*Recommendation:\*\* Build the product around analyst tasks:



1\. \*\*Create watchlist\*\*



&#x20;  \* entities, keywords, domains, wallets, CVEs, org names, aliases.



2\. \*\*Scheduled monitoring\*\*



&#x20;  \* source-specific cadence and rate limits.



3\. \*\*Alert\*\*



&#x20;  \* matched evidence, severity, confidence, source reliability.



4\. \*\*Triage\*\*



&#x20;  \* false positive, needs review, escalate to case.



5\. \*\*Case\*\*



&#x20;  \* evidence board, graph, timeline, notes, assigned analyst.



6\. \*\*Verification\*\*



&#x20;  \* corroboration, contradiction review, stale-data checks.



7\. \*\*Report\*\*



&#x20;  \* generated from approved claims and evidence only.



8\. \*\*Audit\*\*



&#x20;  \* every analyst action logged.



\*\*Observed in repo:\*\* Current app has saved investigation browsing, but no case model. Evidence: `ui.py:377-395`, `investigations.py:53-75`.



\---



\## API design



\*\*Recommendation:\*\* API should expose stable, typed resources.



Example endpoints:



```text

POST /collection-jobs

GET  /collection-jobs/{id}



POST /watchlists

GET  /watchlists/{id}/alerts



GET  /documents/search

GET  /entities/{id}

GET  /entities/{id}/graph

GET  /claims/{id}

PATCH /claims/{id}/review



POST /cases

POST /cases/{id}/evidence

POST /cases/{id}/notes

POST /cases/{id}/reports



GET  /sources

PATCH /sources/{id}

GET  /sources/{id}/health



GET  /audit-events

```



Include service-to-service APIs for worker callbacks.



\---



\## Container and deployment strategy



\*\*Recommendation:\*\* Replace the single container with a multi-service deployment.



Minimum compose/Kubernetes services:



```text

api

ui

scheduler

worker-ingestion

worker-crawler-tor

worker-enrichment

worker-ai

postgres

redis/rabbitmq

opensearch

minio

graph-db

prometheus

grafana

otel-collector

```



Hardening:



\* Non-root containers.

\* Read-only filesystems where possible.

\* Separate Tor proxy containers.

\* Network policies.

\* Per-worker egress controls.

\* Resource limits.

\* Secrets injected from vault.

\* No bind-mounting source into production containers.



\*\*Observed in repo:\*\* Current Compose bind-mounts the repo into `/app` and runs one service. Evidence: `docker-compose.yml:11-18`.



\---



\## Monitoring and resilience model



\*\*Recommendation:\*\*



Metrics:



\* Per-source success/failure rate.

\* Fetch latency.

\* Parser failures.

\* Queue depth.

\* Retry count.

\* DLQ count.

\* Source staleness.

\* New entities per source.

\* Alert volume.

\* Analyst review backlog.

\* Model extraction error rate.

\* Hallucination/unsupported claim rate from sampled reviews.



Logs:



\* Structured JSON.

\* Collection job ID.

\* Source ID.

\* Connector version.

\* Evidence ID.

\* Error class.

\* Retry count.



Alerts:



\* Source down.

\* Parser breakage.

\* Abnormal source volume.

\* Suspicious poisoning spike.

\* Queue backlog.

\* Evidence storage failure.

\* Model output schema failures.



\*\*Observed in repo:\*\* Current source and scrape statuses are local/in-memory and rendered in UI. Evidence: `sources.py:508-555`, `scrape.py:185-238`, `ui.py:91-123`.



\---



\# SECTION 5 — Coverage expansion



\## Boundary



\*\*Recommendation:\*\* Expand coverage through lawful public sources, reputable feeds, commercial APIs where needed, and compliance-approved monitoring. Do \*\*not\*\* design the platform around joining closed criminal forums, buying stolen data, bypassing access controls, exploiting services, or downloading illegal material.



The repo currently focuses on onion/dark-web search engines from `sources.yml`. Evidence: `sources.yml:2-163`. That is narrow. A serious platform needs adjacent-source intelligence because many “dark-web” leads are corroborated through ransomware trackers, malware feeds, phishing feeds, DNS/hosting telemetry, blockchain abuse reports, paste/code search, public breach-notification APIs, and surface-web spillover.



\---



\## Specific source categories and recommended inputs



| Category                                  | Specific lawful sources / websites                                                                                                                                                                                                                                                                                                                                                                                                                                              | Investigative value                                                                                                                            | Data to collect                                                                                                                          | Cadence                                                                                | Verification / confidence challenges                                                               | Legal / operational caveats                                                                                                             |

| ----------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |

| Onion-site discovery / monitoring         | Existing repo sources include Ahmia, Torch, VormWeb, Lantern, OnionFind, TorSearch variants, Haystak, Not Evil, TorDex, Bobby, OnionLand, Find Tor, Excavator, Onionway, Tor66, OSS, Torgol, The Deep Searches. Evidence: `sources.yml:2-163`. Add public-source monitoring around Ahmia’s clearnet interface and source-health verification; Ahmia describes itself as a search engine for Tor hidden services and states that abuse-material sites are filtered. (\[Ahmia]\[1]) | Discover onion services, search mentions of entities/IOCs, identify newly indexed pages.                                                       | Source result pages, result metadata, discovered onion URLs, titles, snippets, first/last seen, source-status records.                   | Daily for broad watchlists; hourly only for high-priority watchlists with rate limits. | Onion search engines are incomplete, stale, spammy, and often mirror-heavy. Results are not proof. | Respect source terms and do not list or prioritize illicit service addresses in reports unless legally necessary and access-controlled. |

| Ransomware / leak monitoring              | Ransomware.live. Its API exposes ransomware intelligence, including group/victim-oriented endpoints, with free/pro tiers and documented rate limits. (\[Ransomware Live]\[2])                                                                                                                                                                                                                                                                                                     | Track claimed victims, leak-site posts, group names, timelines, sectors, countries, and URLs without directly scraping every actor site first. | Group, victim, sector, country, post date, discovered URL, leak status, screenshots/metadata when legally permissible, source timestamp. | Every 1–6 hours for active watchlists; daily for background.                           | Ransomware actors lie, repost, and exaggerate. Victim names need corroboration.                    | Avoid downloading stolen files. Treat claims as allegations until verified.                                                             |

| Public CTI sharing feeds                  | MISP default feeds and communities; MISP is an open-source threat-intelligence sharing platform, and its feed format is widely used for OSINT threat data. (\[MISP Threat Intelligence Platform]\[3]) AlienVault OTX pulse/API ecosystem for public threat indicators. (\[LevelBlue Open Threat Exchange]\[4])                                                                                                                                                                      | Corroborate IOCs, malware, campaigns, threat actors, and infrastructure from community intelligence.                                           | Indicators, threat types, tags, galaxy/ATT\&CK mappings, source feed, confidence, first/last seen.                                        | Every 1–24 hours depending on feed.                                                    | Feed quality varies; duplicates and stale IOCs are common.                                         | Respect feed licenses and sharing restrictions.                                                                                         |

| Malware / IOC intelligence                | abuse.ch platform, including URLhaus, MalwareBazaar, ThreatFox, Feodo Tracker, SSLBL, and YARAify. abuse.ch describes these as operational threat-intel platforms for malware/IOC tracking. (\[abuse.ch]\[5]) URLhaus provides malware URL intelligence and database dumps generated at short intervals; its API and dumps have usage expectations. (\[URLhaus]\[6]) Feodo Tracker provides botnet C2 IOCs. (\[Feodo Tracker]\[7])                                                    | Corroborate URLs, hashes, malware distribution infrastructure, botnet C2s, and campaign indicators.                                            | URLs, domains, IPs, hashes, malware family, tags, status, first/last seen, source feed.                                                  | URLhaus: every 5–15 minutes if using dumps within policy; other feeds hourly/daily.    | Malware IOCs age quickly; sinkholes and takedowns create stale indicators.                         | Do not fetch live malware samples except in a controlled malware-analysis environment.                                                  |

| Vulnerability / exploitation context      | CISA Known Exploited Vulnerabilities catalog provides CSV/JSON outputs. (\[CISA]\[8]) NVD provides vulnerability records and APIs. (\[NIST]\[9]) MITRE ATT\&CK provides a knowledge base of adversary tactics and techniques. (\[MITRE ATT\&CK]\[10]) ATT\&CK also publishes STIX/TAXII resources. (\[MITRE ATT\&CK]\[11])                                                                                                                                                                  | Prioritize mentions of CVEs, exploited products, malware techniques, and actor behavior.                                                       | CVE, vendor/product, KEV status, exploitation date, ATT\&CK techniques, affected platforms.                                               | Daily for NVD/KEV; on-demand for case enrichment.                                      | CVE mentions in forums may be hype, not evidence of exploitation.                                  | Do not turn vulnerability intelligence into exploit guidance in analyst-facing outputs.                                                 |

| Crypto / wallet intelligence              | Chainabuse API for reports of malicious crypto addresses, URLs, domains, and scam categories. (\[Chainabuse]\[12]) OFAC Sanctions List Search for sanctions screening. (\[OFAC]\[13]) Etherscan API for public Ethereum-compatible blockchain transaction/address data. (\[Etherscan]\[14])                                                                                                                                                                                           | Corroborate ransom wallets, scam wallets, sanctions exposure, transaction timing, and reuse of addresses.                                      | Wallet address, chain, report category, reporter confidence, sanctions hits, transaction metadata, first/last seen.                      | On-demand for every wallet; daily for watchlisted wallets.                             | Wallet ownership attribution is risky. Public reports can be false or duplicated.                  | Avoid implying ownership without corroboration. Sanctions screening needs legal review.                                                 |

| Scam / fraud infrastructure indicators    | PhishTank open API for phishing URL submissions. (\[PhishTank]\[15]) OpenPhish feeds for phishing intelligence. (\[OpenPhish]\[16]) AbuseIPDB API for abusive IP reports and confidence scores. (\[AbuseIPDB]\[17]) Spamhaus DROP/EDROP for routed malicious netblocks. (\[The Spamhaus Project]\[18])                                                                                                                                                                                  | Connect dark-web leads to phishing kits, scam domains, abusive IPs, and known fraud infrastructure.                                            | URLs, domains, IPs, report counts, categories, confidence, source, timestamps.                                                           | Every 15–60 minutes for phishing; daily for IP/netblock lists.                         | Community-submitted abuse data has false positives and reporting bias.                             | Respect API limits; avoid automated takedown actions without human verification.                                                        |

| URL / web scanning intelligence           | urlscan.io API/search. urlscan exposes scan result metadata including domains, IPs, ASNs, links, hashes, and page info. (\[Urlscan]\[19])                                                                                                                                                                                                                                                                                                                                         | Analyze surface-web spillover, landing pages, phishing infrastructure, screenshots, redirects, and hosted artifacts.                           | URL, scan ID, screenshot, DOM metadata, redirects, IP, ASN, hashes, linked domains.                                                      | On-demand for URLs; daily for watchlisted domains.                                     | Public scans may expose sensitive queries if configured incorrectly.                               | Use private scans where required; avoid scanning sites where it creates legal/operational risk.                                         |

| Domain / DNS / hosting intelligence       | SecurityTrails API for current/historical DNS, WHOIS, IP, and company-associated data. (\[SecurityTrails Developer Hub]\[20]) Censys for internet-exposed host/service search and monitoring. (\[Censys]\[21]) Shodan for internet-connected device/service intelligence, with API restrictions around scanning endpoints. (\[Shodan Developer]\[22]) Certificate Transparency ecosystem for transparent, verifiable certificate issuance logs. (\[Certificate Transparency]\[23])      | Link domains to infrastructure, hosting, certificates, historical DNS, exposed services, and related domains.                                  | Domains, subdomains, A/AAAA, NS, MX, TXT, WHOIS, certs, ASN, hosting provider, observed services.                                        | Daily for watchlisted domains; on-demand for enrichment.                               | Shared hosting, CDNs, privacy services, and fast-flux can mislead.                                 | Do not scan aggressively. Use API data and passive sources first.                                                                       |

| Forum / marketplace monitoring categories | Do not hardcode illicit forum/marketplace URLs. Use lawful public indexes, source-health verified onion search, first-party public statements, ransomware trackers, public researcher reports, and approved vendor/API sources.                                                                                                                                                                                                                                                 | Identify mentions of brands, handles, IOCs, fraud kits, account shops, exploit chatter, and leaked-document claims.                            | Titles, snippets, post metadata where public, source category, first/last seen, access method, evidence hash.                            | Daily for broad coverage; more frequent for specific investigations.                   | Criminal forums are full of deception, resellers, copied leaks, and false claims.                  | No account compromise, no purchasing, no bypassing access controls, no downloading stolen datasets.                                     |

| Breach / exposure monitoring              | Have I Been Pwned API for breach and paste exposure metadata; HIBP documents API classes for breach/account/paste/subscription/domain operations. (\[Have I Been Pwned]\[24]) HIBP’s service is oriented around checking exposure in known breaches. (\[Have I Been Pwned]\[25])                                                                                                                                                                                                    | Determine whether emails/domains/orgs appear in known breach corpuses without collecting stolen data.                                          | Breach name, date, affected domain, exposed data classes, verified/unverified status, paste metadata.                                    | On-demand for case entities; daily/weekly for approved domain monitoring.              | Exposure metadata is not full breach evidence; names can collide.                                  | Requires authorization for domain-wide monitoring. Do not ingest raw stolen credential dumps.                                           |

| Multilingual / regional intelligence      | Regional CERT advisories, national CSIRT feeds, MISP communities, local-language public threat reports, regional abuse feeds, public Telegram/web spillover where terms allow.                                                                                                                                                                                                                                                                                                  | Capture non-English threat chatter, regional fraud infrastructure, localized victim claims, and actor aliases.                                 | Source language, original text, translation, entities, country/region tags, source reliability.                                          | Daily/hourly depending on source.                                                      | Translation errors and cultural context can distort meaning.                                       | Respect platform terms and privacy law; human review for sensitive claims.                                                              |

| Social / surface-web spillover            | Public web/news, GitHub/GitLab search where terms allow, Reddit/forum public pages, threat-research blogs, security vendor reports. GitHub’s REST API supports repository/search-style integration; GitLab’s search API requires authentication for authenticated search. (\[GitHub Docs]\[26])                                                                                                                                                                                   | Dark-web claims often spill into public posts, code leaks, scam ads, or researcher writeups.                                                   | Public posts, repo hits, code references, actor aliases, IOCs, timestamps, author/source metadata.                                       | Daily for watchlists; on-demand for cases.                                             | Public claims can be rumors; code search can produce benign matches.                               | Respect API terms, copyright, privacy, and platform rules.                                                                              |

| Document / paste / code leak sources      | GitHub/GitLab APIs, HIBP paste metadata, public paste services with terms-compliant APIs, vendor leak-monitoring APIs, court/regulatory filings, public breach notifications.                                                                                                                                                                                                                                                                                                   | Find accidental exposures, leaked configs, copied documents, credential references, and public breach confirmations.                           | File paths, snippets, commit metadata, paste metadata, hash, author if public, first/last seen, takedown state.                          | Daily for watchlisted orgs/domains; near-real-time for high-risk entities.             | Snippets may be copied, fabricated, or old.                                                        | Avoid collecting secrets beyond defensible metadata; implement secret redaction and legal review.                                       |



\---



\## Coverage expansion priority



\*\*Recommendation:\*\* Add sources in this order:



1\. \*\*Ransomware/live leak trackers\*\* — high investigative relevance, relatively structured data.

2\. \*\*Malware/IOC feeds\*\* — immediate enrichment value for URLs, hashes, domains, IPs.

3\. \*\*Phishing/fraud infrastructure feeds\*\* — useful for fraud and brand-abuse investigations.

4\. \*\*Domain/DNS/hosting intelligence\*\* — critical for infrastructure correlation.

5\. \*\*Crypto abuse/sanctions/transaction metadata\*\* — important for ransomware/scam cases.

6\. \*\*Breach exposure metadata\*\* — valuable but sensitive; requires strict authorization boundaries.

7\. \*\*Multilingual/regional sources\*\* — high value once the core pipeline is stable.

8\. \*\*Code/paste/document search\*\* — useful, but requires stronger legal and secret-handling controls.



\---



\# SECTION 6 — AI redesign



\## Where AI belongs



AI should help analysts process and synthesize information. It should not be the system of record, the evidence authority, or the sole basis for high-risk claims.



\## Where AI should not be used



\*\*Recommendation:\*\* Do not use AI for:



\* Cryptographic hashing.

\* URL canonicalization.

\* IOC regex extraction where deterministic extraction works.

\* Source availability measurement.

\* Legal approval.

\* Autonomous access to restricted sources.

\* Purchasing, posting, interacting, or logging into illicit services.

\* Final attribution without human review.

\* Chain-of-custody.

\* Evidence integrity.

\* Sanctions/legal determinations.



\*\*Observed in repo:\*\* Current AI is used for query refinement, result filtering, and summary. Evidence: `llm.py:73-151`, `llm.py:318-352`.



\---



\## AI use-case matrix



| AI use                   | Model task                                                                         | Input shape                                                                    | Output shape                                                                | Hallucination risk                  | Human review requirement                                                   | Evaluation metric                                                               |

| ------------------------ | ---------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ | --------------------------------------------------------------------------- | ----------------------------------- | -------------------------------------------------------------------------- | ------------------------------------------------------------------------------- |

| Summarization            | Summarize evidence for an analyst.                                                 | Evidence IDs, source metadata, extracted text chunks, artifacts, case context. | Bullet summary with every sentence tied to evidence IDs.                    | Medium: model may overstate claims. | Required before external report.                                           | Unsupported-claim rate; citation precision; analyst correction rate.            |

| Translation              | Translate non-English evidence while preserving original.                          | Original text chunk, language, evidence ID.                                    | Translation, detected language, uncertainty notes.                          | Medium: nuance loss.                | Required for legal/high-risk claims.                                       | BLEU/COMET where available; analyst review accuracy; named-entity preservation. |

| Entity extraction        | Extract people, orgs, handles, domains, wallets, malware, CVEs, locations.         | Evidence chunk + deterministic artifacts.                                      | Structured JSON entities with spans/offsets/evidence IDs.                   | Medium.                             | Required for person/PII attribution; optional for low-risk technical IOCs. | Precision/recall against labeled set; span accuracy.                            |

| Relationship extraction  | Identify relationships such as handle→wallet, actor→victim claim, domain→campaign. | Evidence chunk, known entities, source metadata.                               | Subject-predicate-object triples with evidence IDs and confidence.          | High for implicit relationships.    | Required for attribution, victim claims, real-world identity.              | Triple precision; unsupported-edge rate.                                        |

| Cross-source synthesis   | Combine multiple evidence items into coherent finding.                             | Claims, evidence, source reliability, timestamps.                              | Synthesis note with supporting and contradicting evidence.                  | High if evidence is weak.           | Required.                                                                  | Analyst acceptance rate; contradiction omission rate.                           |

| Contradiction detection  | Compare claims for conflict.                                                       | Claim set with subject/predicate/object/time/source.                           | Conflict objects: claim A vs claim B, reason, severity.                     | Medium.                             | Required for unresolved conflicts.                                         | Conflict detection precision/recall; false conflict rate.                       |

| Lead prioritization      | Rank alerts/leads.                                                                 | Watchlist match, source reliability, recency, corroboration, entity risk.      | Priority score + explanation + evidence IDs.                                | Medium.                             | Required for severe/legal escalations.                                     | Analyst “useful lead” rate; false-positive reduction.                           |

| Analyst copilot          | Help query evidence, explain graph, draft hypotheses.                              | Case state, authorized evidence, analyst question.                             | Answer with citations/evidence IDs.                                         | Medium-high.                        | Analyst controls output; no autonomous action.                             | Citation support rate; task completion time; analyst satisfaction.              |

| Case brief generation    | Draft report from reviewed claims.                                                 | Approved claims, evidence IDs, analyst notes, confidence levels.               | Structured brief: executive summary, timeline, entities, evidence appendix. | Medium.                             | Required before sharing.                                                   | Unsupported statement count; review edits per report.                           |

| False-positive reduction | Classify whether a match is likely irrelevant.                                     | Watchlist term, matched document, context, source type.                        | FP probability + reason.                                                    | Medium.                             | Required when suppressing high-value alerts; optional for low severity.    | Precision at suppression threshold; missed true-positive rate.                  |

| Trust scoring support    | Suggest factors that affect confidence.                                            | Source history, evidence, corroboration, contradictions.                       | Suggested score components, not final score.                                | Medium.                             | Required.                                                                  | Calibration error; analyst override rate.                                       |

| Report generation        | Generate final narrative from approved claims.                                     | Approved claim objects only.                                                   | Report with citations, confidence labels, caveats.                          | Medium.                             | Always required.                                                           | Unsupported-claim rate must be near zero.                                       |



\---



\## How to restructure current LLM functions



\### Current `refine\_query`



\*\*Observed in repo:\*\* `refine\_query()` asks an LLM to produce a cleaned query of five words or fewer. Evidence: `llm.py:73-90`.



\*\*Recommendation:\*\* Keep this, but store the original query, refined query, model, prompt version, and analyst approval. Do not use refined queries invisibly.



\---



\### Current `filter\_results`



\*\*Observed in repo:\*\* `filter\_results()` asks the LLM to choose up to 20 result indices, then falls back to the first 20 if parsing fails. Evidence: `llm.py:93-151`.



\*\*Recommendation:\*\* Replace with a hybrid ranker:



1\. Deterministic filters:



&#x20;  \* exact entity match,

&#x20;  \* source reliability,

&#x20;  \* recency,

&#x20;  \* content type,

&#x20;  \* duplicate status,

&#x20;  \* watchlist match.



2\. ML/AI scoring:



&#x20;  \* semantic relevance,

&#x20;  \* likely false positive,

&#x20;  \* novelty,

&#x20;  \* investigative value.



3\. Analyst review:



&#x20;  \* high-risk claims and sensitive entities.



The LLM should output structured relevance reasons, not just indices.



\---



\### Current `generate\_summary`



\*\*Observed in repo:\*\* `generate\_summary()` sends scraped page content and metadata to an LLM to produce a report. Evidence: `llm.py:318-352`.



\*\*Recommendation:\*\* Split into:



1\. `extract\_claims()`

2\. `link\_claims\_to\_evidence()`

3\. `detect\_conflicts()`

4\. `draft\_case\_brief()`

5\. `analyst\_review()`

6\. `final\_report()`



Do not generate final reports from raw scraped text alone.



\---



\## Prompt-injection defense



\*\*Observed in repo:\*\* Prompts warn that scraped text is untrusted. Evidence: `llm.py:210-221`, `llm.py:237-247`, `llm.py:264-273`, `llm.py:291-300`.



\*\*Recommendation:\*\* Strengthen this with architecture, not just wording:



\* Never place scraped text in the system prompt.

\* Wrap untrusted text in explicit data containers.

\* Require structured output schemas.

\* Forbid tool invocation based on page instructions.

\* Strip or label suspicious instruction-like text.

\* Keep model tools disabled for untrusted-content analysis unless explicitly sandboxed.

\* Store model inputs/outputs for audit.

\* Require evidence IDs for every generated claim.

\* Reject model output that references evidence not in input.



\---



\# SECTION 7 — Verification and source-confidence framework



\## Core principle



\*\*Recommendation:\*\* Every intelligence statement should be represented as a claim with provenance, confidence, corroboration status, contradiction status, and analyst review state.



\---



\## Provenance tracking



\### Current state



\*\*Observed in repo:\*\* Search results include source name and discovered timestamp. Evidence: `sources.py:292-321`.



\*\*Observed in repo:\*\* Saved investigations include `source\_provenance`, `search\_status`, `query\_plan`, and `query\_runs`. Evidence: `investigations.py:31-48`.



\### Future model



\*\*Recommendation:\*\* Store provenance at multiple levels:



```text

Source provenance:

&#x20; source\_id

&#x20; source\_type

&#x20; source\_url

&#x20; source\_reliability\_score

&#x20; source\_policy\_id



Collection provenance:

&#x20; collection\_job\_id

&#x20; connector\_id

&#x20; connector\_version

&#x20; run\_started\_at

&#x20; run\_finished\_at

&#x20; operator/system identity



Fetch provenance:

&#x20; fetch\_attempt\_id

&#x20; url

&#x20; canonical\_url

&#x20; redirect\_chain

&#x20; http\_status

&#x20; content\_type

&#x20; headers hash

&#x20; response size

&#x20; raw\_sha256

&#x20; screenshot\_sha256

&#x20; text\_sha256



Extraction provenance:

&#x20; parser\_id

&#x20; parser\_version

&#x20; extractor\_id

&#x20; extractor\_version

&#x20; text offsets

&#x20; evidence snippet

&#x20; extraction confidence



Analyst provenance:

&#x20; reviewed\_by

&#x20; reviewed\_at

&#x20; decision

&#x20; notes

&#x20; override reason

```



\---



\## Per-source reliability scoring



\*\*Recommendation:\*\* Score sources separately from claims.



Example source reliability components:



| Component                   | Description                                                                                               |

| --------------------------- | --------------------------------------------------------------------------------------------------------- |

| Source type                 | Primary actor site, public feed, aggregator, search engine, community report, vendor report, public post. |

| Historical accuracy         | Prior claims later confirmed or refuted.                                                                  |

| Uptime and parser stability | Whether collection is reliable.                                                                           |

| Freshness                   | Whether source updates frequently or returns stale mirrors.                                               |

| Transparency                | Whether source provides timestamps, methodology, or references.                                           |

| Independence                | Whether it is independent or copies other sources.                                                        |

| Abuse/deception risk        | Spam, scams, fake leaks, impersonation, SEO poisoning.                                                    |

| Legal/compliance status     | Approved, restricted, disallowed, needs review.                                                           |



\*\*Observed in repo:\*\* Current “unhealthy source” logic tracks failures only in process and can clear/retrieve last status. Evidence: `sources.py:508-521`.



\*\*Recommendation:\*\* Replace this with durable source health and reliability tables.



\---



\## Per-claim confidence scoring



Represent every claim as:



```json

{

&#x20; "claim\_id": "...",

&#x20; "subject": "Example Corp",

&#x20; "predicate": "claimed\_victim\_of",

&#x20; "object": "Ransomware Group X",

&#x20; "claim\_text": "Example Corp is listed as a claimed victim...",

&#x20; "evidence\_ids": \["..."],

&#x20; "source\_ids": \["..."],

&#x20; "first\_seen\_at": "...",

&#x20; "last\_seen\_at": "...",

&#x20; "confidence\_score": 0.64,

&#x20; "confidence\_level": "medium",

&#x20; "corroboration\_status": "single\_source",

&#x20; "contradiction\_status": "none\_found",

&#x20; "staleness\_status": "current",

&#x20; "review\_status": "needs\_review"

}

```



Confidence factors:



\* Directness of evidence.

\* Source reliability.

\* Number of independent corroborating sources.

\* Recency.

\* Specificity.

\* Whether original evidence is accessible.

\* Whether source is primary or aggregator.

\* Whether contradiction exists.

\* Whether analyst reviewed it.



\---



\## Corroboration logic



\*\*Recommendation:\*\* Treat corroboration as independence-weighted, not count-weighted.



Rules:



\* Same content copied across mirrors is \*\*one\*\* evidence family.

\* Search engine result + indexed source page is not independent corroboration.

\* Public CTI feed + original actor post may be partly independent if the feed has its own validation.

\* Victim self-confirmation, regulatory filing, or official notification is stronger than forum chatter.

\* Ransomware leak-site claim is a claim, not proof of breach scope.

\* Crypto address in a ransom note + Chainabuse report + blockchain activity may corroborate address relevance, not necessarily actor identity.



\---



\## Conflict / contradiction handling



\*\*Recommendation:\*\* Add a `ClaimConflict` object:



```json

{

&#x20; "conflict\_id": "...",

&#x20; "claim\_a": "...",

&#x20; "claim\_b": "...",

&#x20; "conflict\_type": "victim\_status|date|actor|wallet|domain\_ownership|identity",

&#x20; "severity": "low|medium|high",

&#x20; "status": "unresolved|analyst\_resolved|stale|false\_conflict",

&#x20; "resolution\_note": "...",

&#x20; "resolved\_by": "...",

&#x20; "resolved\_at": "..."

}

```



Examples:



\* One source says a leak was posted on May 1; another says May 5.

\* A wallet is associated with two unrelated actors.

\* A domain is reported malicious by one feed and benign by another.

\* A paste claims credentials for a company, but HIBP or domain verification does not support it.



\---



\## Stale-data handling



\*\*Recommendation:\*\* Every entity, indicator, and claim needs freshness metadata.



Suggested TTLs:



| Data type               | Staleness rule                                                           |

| ----------------------- | ------------------------------------------------------------------------ |

| Phishing URL            | Stale quickly; recheck daily or faster.                                  |

| Malware URL             | Stale quickly; recheck frequently.                                       |

| IP reputation           | Stale quickly, especially cloud/CDN/shared hosting.                      |

| Domain registration     | Medium-term; recheck weekly/monthly.                                     |

| CVE metadata            | Stable but enrich with exploitation status updates.                      |

| Ransomware victim claim | Claim remains historical; status may change.                             |

| Forum/listing mention   | Historical evidence remains, but relevance decays.                       |

| Wallet address          | Historical transactions remain; abuse association confidence may change. |



\---



\## Chain-of-custody / evidence traceability



\*\*Recommendation:\*\* For every raw artifact:



\* Store immutable object.

\* Compute SHA-256.

\* Store retrieval timestamp.

\* Store connector version.

\* Store parser version.

\* Store analyst access logs.

\* Never overwrite raw evidence.

\* Store derived text separately.

\* Store screenshots where lawful and useful.

\* Version reports.

\* Require reason for deletion/redaction.

\* Keep append-only audit log.



\*\*Observed in repo:\*\* Current JSON records are mutable files and do not contain raw evidence hashes. Evidence: `investigations.py:27-50`.



\---



\## Analyst override workflow



\*\*Recommendation:\*\* Analysts should be able to override:



\* Source reliability score.

\* Claim confidence.

\* Entity resolution decision.

\* False-positive status.

\* Alert severity.

\* Report inclusion.



Every override must include:



```text

old\_value

new\_value

reason

analyst\_id

timestamp

case\_id

evidence\_ids

```



\---



\# SECTION 8 — Security and operational hardening



\## Secrets management



\*\*Observed in repo:\*\* Secrets are loaded through `.env`/environment variables. Evidence: `config.py:19-26`, `.env.example:1-7`.



\*\*Recommendation:\*\*



\* Use Vault, AWS Secrets Manager, GCP Secret Manager, Azure Key Vault, or Doppler/1Password Secrets Automation.

\* Scope secrets per service.

\* Rotate API keys.

\* Never render secrets in UI.

\* Add secret scanning in CI.

\* Keep `.env` only for local development.



\---



\## Access control



\*\*Observed in repo:\*\* No auth/RBAC appears in `ui.py` or deployment config.



\*\*Recommendation:\*\*



\* Require authentication.

\* Add RBAC:



&#x20; \* viewer,

&#x20; \* analyst,

&#x20; \* senior analyst,

&#x20; \* case manager,

&#x20; \* source admin,

&#x20; \* system admin.

\* Add case-level permissions.

\* Add source-level restrictions.

\* Require stronger permission for PII, breach exposure, and sensitive sources.

\* Use SSO/OIDC for teams.



\---



\## Audit logs



\*\*Recommendation:\*\* Log every high-impact action:



\* Login.

\* Source config change.

\* Watchlist change.

\* Collection job creation.

\* Evidence access.

\* Case creation.

\* Claim override.

\* Report export.

\* Data deletion/redaction.

\* API key use.

\* Failed access attempt.



Current JSON investigation saving is not audit logging. Evidence: `investigations.py:27-50`.



\---



\## Sandboxing / isolation



\*\*Recommendation:\*\* Isolate risky collection and parsing.



\* Separate crawler workers from API/UI.

\* Run crawlers as non-root.

\* Use read-only filesystems where possible.

\* Apply seccomp/AppArmor.

\* Disable unnecessary capabilities.

\* Use network policies.

\* Quarantine unknown binary content.

\* Avoid executing JavaScript unless using a sandboxed browser worker.

\* Treat every fetched page as hostile.



\*\*Observed in repo:\*\* Tor and Streamlit run in the same container. Evidence: `Dockerfile:4-5`, `entrypoint.sh:3-35`.



\---



\## Crawler isolation



\*\*Recommendation:\*\*



\* Dedicated Tor proxy containers.

\* Separate crawler identity pools by source category.

\* Per-source egress/rate policy.

\* No direct access from crawler to internal databases except through queue/object-store credentials scoped narrowly.

\* Store raw evidence via signed upload or restricted service account.

\* Block crawler access to internal metadata endpoints.

\* Disable local network access unless explicitly required.



\*\*Observed in repo:\*\* `scrape.py` fetches onion URLs through Tor and clearweb directly. Evidence: `scrape.py:130-145`.



\---



\## Abuse prevention



\*\*Recommendation:\*\*



\* No autonomous interactions with forums/marketplaces.

\* No purchase flows.

\* No posting.

\* No credential use except authorized API keys.

\* No exploit execution.

\* No downloading stolen datasets.

\* No malware retrieval outside approved sandbox.

\* Per-source legal policy enforcement.

\* Analyst approval for sensitive pivots.



\---



\## Storage encryption



\*\*Recommendation:\*\*



\* Encrypt databases at rest.

\* Encrypt object storage.

\* Use TLS between services.

\* Store hashes separately.

\* Use object lock/versioning for evidence.

\* Redact secrets/PII in lower-trust views.

\* Add retention and deletion policies.



\---



\## Backup / recovery



\*\*Recommendation:\*\*



\* Automated database backups.

\* Object storage versioning.

\* Restore testing.

\* Disaster recovery plan.

\* Evidence immutability rules.

\* Separate backup encryption keys.

\* Backup audit logs.



\---



\## Rate limiting



\*\*Recommendation:\*\*



\* Per-source request limits.

\* Per-connector concurrency.

\* Global crawler budget.

\* API rate limits.

\* Analyst export limits.

\* Abuse monitoring.

\* Queue backpressure.



\*\*Observed in repo:\*\* Source and scrape concurrency are thread-capped, but not source-policy-driven. Evidence: `sources.py:524-555`, `scrape.py:185-238`.



\---



\## Detection of poisoned / deceptive sources



\*\*Recommendation:\*\* Add poisoning detection signals:



\* Sudden source content shift.

\* Same claim appearing across many mirrors with identical text.

\* High-volume spam from one source.

\* New source with high severity claims but no corroboration.

\* Suspicious SEO patterns.

\* Mismatched timestamps.

\* Actor impersonation markers.

\* Conflicting wallet/domain claims.

\* Known fake leak patterns.

\* LLM prompt-injection content.



\---



\## Prompt injection / model manipulation defenses



\*\*Observed in repo:\*\* The current prompts warn that scraped text is untrusted. Evidence: `llm.py:210-221`, `llm.py:237-247`, `llm.py:264-273`, `llm.py:291-300`.



\*\*Recommendation:\*\* Add systemic controls:



\* Treat fetched content as data, never instructions.

\* Use structured schemas.

\* Validate all model output.

\* Require evidence IDs.

\* Keep tools disabled for summarization/extraction.

\* Reject output that invents unsupported sources.

\* Add prompt-injection classifiers for suspicious text.

\* Store model input/output for audit.

\* Use separate prompts for extraction vs synthesis.

\* Never let an AI agent decide to browse or pivot into restricted sources without policy checks.



\---



\# SECTION 9 — Prioritized roadmap



\## Immediate fixes: 0–14 days



| Item                                                                                                        | Impact | Difficulty | Dependencies                                   | Why this phase                                                                                                       |

| ----------------------------------------------------------------------------------------------------------- | -----: | ---------: | ---------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |

| Declare the current app a prototype and document lawful-use boundaries                                      |   High |        Low | None                                           | Prevents misuse and mispositioning as production CTI.                                                                |

| Add basic auth or deployment warning; do not expose Streamlit publicly                                      |   High | Low-Medium | Streamlit deployment config                    | App binds to `0.0.0.0:8501` with no visible auth. Evidence: `entrypoint.sh:34-35`.                                   |

| Add `schema\_version`, `run\_id`, and content hashes to saved investigations                                  |   High | Low-Medium | `investigations.py`, `scrape.py`               | Improves auditability immediately over current JSON saves. Evidence: `investigations.py:31-48`.                      |

| Add structured logging with job/source IDs                                                                  |   High |     Medium | Python logging changes                         | Current observability is UI/status-based.                                                                            |

| Replace custom simple YAML parser with schema-validated YAML                                                | Medium | Low-Medium | PyYAML or ruamel.yaml, pydantic                | Current parser is intentionally limited. Evidence: `sources.py:83-120`.                                              |

| Add `last\_checked\_at`, `last\_success\_at`, `source\_type`, `risk\_level`, and `legal\_notes` to source registry |   High |     Medium | Source schema update                           | Current source notes are not enough for compliance. Evidence: `sources.py:46-53`.                                    |

| Harden Docker basics: non-root user, healthcheck, no production bind mount                                  |   High | Low-Medium | Dockerfile/Compose edits                       | Current Dockerfile has no `USER`; Compose bind-mounts repo. Evidence: `Dockerfile:1-26`, `docker-compose.yml:11-18`. |

| Move untrusted scraped text out of prompt-adjacent freeform formatting and into structured evidence blocks  |   High |     Medium | `llm.py`                                       | Current prompts warn about untrusted text but still rely on prompt compliance. Evidence: `llm.py:318-352`.           |

| Add CI to run tests with dependencies installed                                                             | Medium |        Low | GitHub Actions or equivalent                   | Tests exist but no workflow appears in repo.                                                                         |

| Add source result raw snapshot option                                                                       |   High |     Medium | `sources.py`, `scrape.py`, file/object storage | Enables evidence preservation before DB migration.                                                                   |



\---



\## Near-term upgrades: 30–60 days



| Item                                                                                                   |    Impact |  Difficulty | Dependencies              | Why this phase                                                                         |

| ------------------------------------------------------------------------------------------------------ | --------: | ----------: | ------------------------- | -------------------------------------------------------------------------------------- |

| Move orchestration out of Streamlit into a backend service                                             | Very high | Medium-High | FastAPI or similar        | `ui.py` currently orchestrates the whole pipeline. Evidence: `ui.py:543-743`.          |

| Add PostgreSQL normalized schema                                                                       | Very high |      Medium | Backend service           | JSON files cannot support intelligence workflows. Evidence: `investigations.py:27-50`. |

| Add object storage for raw evidence                                                                    | Very high |      Medium | MinIO/S3, hash model      | Needed for chain-of-custody.                                                           |

| Add OpenSearch/Elasticsearch                                                                           |      High |      Medium | Normalized documents      | Needed for historical search.                                                          |

| Add queue and worker model                                                                             | Very high |      Medium | Redis/RabbitMQ, Celery/RQ | Needed for retries, scheduling, concurrency, and decoupling.                           |

| Build first source connector framework                                                                 | Very high |      Medium | Source registry schema    | Replaces ad hoc parser branches. Evidence: `sources.py:347-403`.                       |

| Add lawful public CTI connectors: URLhaus, abuse.ch feeds, CISA KEV, NVD, OTX/MISP, PhishTank, urlscan |      High |      Medium | API keys/licensing review | Adds real enrichment beyond onion search.                                              |

| Add watchlists                                                                                         |      High |      Medium | DB, API                   | Turns one-off search into monitoring.                                                  |

| Add alert objects                                                                                      |      High |      Medium | Watchlists, scheduler     | Enables analyst workflow.                                                              |

| Add structured AI extraction outputs                                                                   |      High |      Medium | AI service, schemas       | Moves from narrative to evidence-linked claims.                                        |



\---



\## Medium-term architecture changes: 60–120 days



| Item                                        |    Impact |  Difficulty | Dependencies                        | Why this phase                                                  |

| ------------------------------------------- | --------: | ----------: | ----------------------------------- | --------------------------------------------------------------- |

| Add graph database or graph extension       | Very high |        High | Entities/relationships schema       | Link analysis becomes possible after normalized entities exist. |

| Add claim-confidence model                  | Very high |        High | Evidence, source reliability, graph | Core to serious intelligence.                                   |

| Add source reliability model                | Very high | Medium-High | Source health history               | Separates source trust from claim trust.                        |

| Add case management                         | Very high |        High | Auth, DB, claims, evidence          | Turns product into an analyst platform.                         |

| Add contradiction detection                 |      High |        High | Claim model, AI pipeline            | Important once many sources are ingested.                       |

| Add multilingual pipeline                   |      High | Medium-High | Language detection, AI service      | Expands coverage meaningfully.                                  |

| Add analyst review queues                   | Very high |      Medium | Cases, claims, RBAC                 | Human review is mandatory for high-risk intelligence.           |

| Add audit log service                       | Very high |      Medium | Auth, backend                       | Required for production and sensitive data.                     |

| Add OpenTelemetry/Prometheus/Grafana        |      High |      Medium | Service split                       | Necessary for operations.                                       |

| Add crawler sandboxing and network policies | Very high |        High | Deployment architecture             | Needed before scaling collection.                               |



\---



\## Major strategic bets



| Strategic bet                              |    Impact | Difficulty | Dependencies                       | Why it matters                                                                    |

| ------------------------------------------ | --------: | ---------: | ---------------------------------- | --------------------------------------------------------------------------------- |

| Evidence-first claim graph                 | Very high |  Very high | Evidence store, graph, claims      | This is what separates a serious intelligence platform from a search/report tool. |

| Human-in-the-loop verification workbench   | Very high |       High | Cases, claims, audit logs          | Reduces false positives and supports defensible reporting.                        |

| Source reliability and deception detection | Very high |       High | Source history, corroboration data | Dark-web data is adversarial and unreliable.                                      |

| Compliance-aware connector marketplace     |      High |       High | Source registry, legal review      | Lets coverage expand without reckless source collection.                          |

| AI copilot with citation enforcement       |      High |       High | Evidence IDs, schemas, evals       | Useful only after the evidence model exists.                                      |

| Temporal intelligence layer                |      High |       High | Historical storage, graph          | Tracks first seen, last seen, reposts, actor shifts, infrastructure changes.      |



\---



\# SECTION 10 — Final blunt assessment



\## The 5 biggest architectural mistakes or weaknesses



\### 1. The UI is the orchestrator



\*\*Observed in repo:\*\* `ui.py` drives model selection, query refinement, Tor check, search, scrape, artifact extraction, summarization, saving, and rendering. Evidence: `ui.py:543-743`.



\*\*Why it is a problem:\*\* This prevents durable jobs, retries, queueing, scaling, API integration, and team workflows.



\*\*Recommendation:\*\* Move orchestration into backend services and workers.



\---



\### 2. The platform is search-engine-centric, not intelligence-collection-centric



\*\*Observed in repo:\*\* Sources are URL templates for search engines/directories, and collection is based on querying those sources. Evidence: `sources.yml:2-163`, `sources.py:434-482`.



\*\*Why it is a problem:\*\* Search engines are incomplete, stale, spammy, and not enough for CTI.



\*\*Recommendation:\*\* Build a connector framework for lawful feeds, APIs, monitored sources, trackers, and enrichment providers.



\---



\### 3. JSON files are treated as the system of record



\*\*Observed in repo:\*\* Investigations are timestamped JSON files. Evidence: `investigations.py:27-50`.



\*\*Why it is a problem:\*\* JSON files cannot support normalized entities, claims, evidence chains, multi-user workflows, search, graph relationships, or historical analytics.



\*\*Recommendation:\*\* Add PostgreSQL, object storage, search index, and graph layer.



\---



\### 4. There is no verification model



\*\*Observed in repo:\*\* Current records contain artifacts, source provenance, status, and summaries, but no claim confidence, source reliability, chain-of-custody, corroboration, or contradiction model. Evidence: `investigations.py:31-48`, `query\_expansion.py:456-497`.



\*\*Why it is a problem:\*\* Dark-web intelligence is adversarial. Without verification, the platform risks producing polished but unreliable reports.



\*\*Recommendation:\*\* Build source reliability, per-claim confidence, evidence provenance, conflict handling, stale-data handling, and analyst review.



\---



\### 5. Security and operational hardening are prototype-level



\*\*Observed in repo:\*\* Single container, Tor and app together, root-default Dockerfile, Streamlit on `0.0.0.0`, env secrets, no visible auth/RBAC/audit logs. Evidence: `Dockerfile:1-26`, `docker-compose.yml:1-18`, `entrypoint.sh:3-35`, `config.py:19-26`.



\*\*Why it is a problem:\*\* The system handles sensitive investigations and hostile content. It needs serious isolation and access control.



\*\*Recommendation:\*\* Separate services, add auth/RBAC, audit logs, secret management, crawler sandboxing, and production observability.



\---



\## The 5 highest-value improvements



\### 1. Build durable ingestion: connectors + scheduler + queue + workers



\*\*Impact:\*\* Converts one-off search into continuous intelligence collection.



\*\*Replace:\*\* UI-driven execution in `ui.py`.



\---



\### 2. Add evidence-first storage



\*\*Impact:\*\* Enables traceability, reproducibility, auditability, and defensible reporting.



\*\*Replace:\*\* JSON-only `investigations.py` persistence.



\---



\### 3. Add normalized entities, relationships, and claims



\*\*Impact:\*\* Enables entity resolution, graph analysis, watchlists, alerting, confidence, and case workflows.



\*\*Replace:\*\* Flat artifacts and raw result lists.



\---



\### 4. Add analyst case management and review workflows



\*\*Impact:\*\* Turns the app from a report generator into an investigation platform.



\*\*Replace:\*\* “Run investigation → read summary → download” workflow.



\---



\### 5. Redesign AI around structured, evidence-linked outputs



\*\*Impact:\*\* Makes AI useful without letting it become an unverified narrator.



\*\*Replace:\*\* LLM-only result filtering and freeform narrative summarization.



\---



\## What should be removed or replaced entirely?



| Current component                            | Keep / replace         | Reason                                                                                                                                 |

| -------------------------------------------- | ---------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |

| Streamlit as backend orchestrator            | Replace                | Fine as prototype UI, wrong as platform control plane. Evidence: `ui.py:543-743`.                                                      |

| JSON investigation files as system of record | Replace                | Use DB + object store. Evidence: `investigations.py:27-50`.                                                                            |

| Custom simple YAML parser                    | Replace                | Use real YAML plus schema validation. Evidence: `sources.py:83-120`.                                                                   |

| In-process unhealthy source tracking         | Replace                | Use durable source-health metrics. Evidence: `sources.py:37-39`, `sources.py:508-521`.                                                 |

| LLM result filtering by index selection      | Replace                | Use hybrid deterministic + structured AI ranking. Evidence: `llm.py:93-151`.                                                           |

| Single container with Tor + app              | Replace for production | Separate crawler/Tor workers, API, UI, storage, queues. Evidence: `Dockerfile:1-26`, `entrypoint.sh:3-35`.                             |

| Source registry as only search URL templates | Replace                | Build connector registry with compliance, cadence, parser, policy, and source type. Evidence: `sources.py:46-53`, `sources.yml:2-163`. |

| Flat artifact rows                           | Expand substantially   | Convert into entities/indicators with provenance and confidence. Evidence: `artifacts.py:46-52`.                                       |



\---



\## Can this repo become a serious platform?



\*\*Blunt answer:\*\* Not as-is.



\*\*Observed in repo:\*\* The repo is coherent as a local prototype: Dockerized Streamlit app, Tor-backed source searches, source health checks, bounded scraping, artifact extraction, query expansion, LLM summarization, and JSON saves.



\*\*Inference:\*\* It can become the seed of a serious platform only if treated as a prototype and substantially re-architected. The reusable parts are:



\* Source registry idea.

\* Some search parser tests.

\* Tor bootstrap logic.

\* Scraper safety caps.

\* Artifact regex extraction.

\* Query-expansion policy concepts.

\* Prompt-injection awareness.

\* Investigation metadata concept.

\* Source status UI concept.



\*\*Recommendation:\*\* Mine this repo for parts. Do not build production CTI on the current architecture. The future system needs a new backend, data model, evidence store, connector framework, queue, graph, case workflow, verification framework, and security model.



\[1]: https://ahmia.fi/ "

&#x20;   Ahmia —

&#x20;     Search Tor Hidden Services

&#x20;   

&#x20; "

\[2]: https://www.ransomware.live/api "Ransomware.live "

\[3]: https://www.misp-project.org/feeds/?utm\_source=chatgpt.com "MISP Default Feeds"

\[4]: https://otx.alienvault.com/api?utm\_source=chatgpt.com "OTX DirectConnect API - LevelBlue - Open Threat Exchange"

\[5]: https://abuse.ch/ "abuse.ch | Fighting malware and botnets"

\[6]: https://urlhaus.abuse.ch/api/ "URLhaus | Community API"

\[7]: https://feodotracker.abuse.ch/ "Feodo Tracker"

\[8]: https://www.cisa.gov/known-exploited-vulnerabilities-catalog?utm\_source=chatgpt.com "Known Exploited Vulnerabilities Catalog"

\[9]: https://www.nist.gov/programs-projects/national-vulnerability-database-nvd?utm\_source=chatgpt.com "National Vulnerability Database (NVD)"

\[10]: https://attack.mitre.org/?utm\_source=chatgpt.com "MITRE ATT\&CK®"

\[11]: https://attack.mitre.org/resources/attack-data-and-tools/?utm\_source=chatgpt.com "ATT\&CK Data \& Tools"

\[12]: https://docs.chainabuse.com/docs/welcome-to-chainabuse-api?utm\_source=chatgpt.com "Chainabuse Public API (v1.2)"

\[13]: https://ofac.treasury.gov/?utm\_source=chatgpt.com "Office of Foreign Assets Control: Home"

\[14]: https://docs.etherscan.io/introduction?utm\_source=chatgpt.com "Etherscan API Key"

\[15]: https://www.phishtank.net/?utm\_source=chatgpt.com "PhishTank | Join the fight against phishing"

\[16]: https://www.openphish.com/?utm\_source=chatgpt.com "OpenPhish - Phishing Intelligence"

\[17]: https://www.abuseipdb.com/?utm\_source=chatgpt.com "AbuseIPDB - IP address abuse reports - Making the Internet ..."

\[18]: https://www.spamhaus.org/blocklists/do-not-route-or-peer/?utm\_source=chatgpt.com "Don't Route Or Peer Lists (DROP) | Use with firewalls \& BGP"

\[19]: https://urlscan.io/docs/api/?utm\_source=chatgpt.com "API Documentation"

\[20]: https://docs.securitytrails.com/docs/overview?utm\_source=chatgpt.com "SecurityTrails API - Overview"

\[21]: https://search.censys.io/api?utm\_source=chatgpt.com "Censys Search API"

\[22]: https://developer.shodan.io/?utm\_source=chatgpt.com "Shodan developer API"

\[23]: https://certificate.transparency.dev/?utm\_source=chatgpt.com "Certificate Transparency : Certificate Transparency"

\[24]: https://haveibeenpwned.com/api/v3?utm\_source=chatgpt.com "API Documentation"

\[25]: https://haveibeenpwned.com/?utm\_source=chatgpt.com "Have I Been Pwned: Check if your email address has been ..."

\[26]: https://docs.github.com/en/rest?utm\_source=chatgpt.com "GitHub REST API documentation"



