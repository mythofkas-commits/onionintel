# OnionIntel

OnionIntel is a Dockerized dark web OSINT investigation app for Tor-backed onion search, AI-assisted query expansion, source health monitoring, artifact extraction, and auditable investigation reports.

It is designed for lawful cybersecurity research, cyber threat intelligence, brand protection, personal exposure review, and investigative OSINT workflows where source provenance and repeatable evidence matter.

> Legal and safety notice: use OnionIntel only for lawful research and defensive investigations. Do not use it to access, acquire, distribute, or act on illegal material. Dark web sources are unstable and may expose offensive, fraudulent, or harmful content.

## What It Does

OnionIntel runs a local Streamlit web app backed by Tor. It searches configurable onion and clearnet dark web search sources, records source health, deduplicates and annotates results, extracts investigation artifacts, optionally uses an LLM for query planning and report writing, and saves a JSON audit trail for each investigation.

## Key Features

- Docker-first dark web OSINT workflow with Tor included in the container.
- Streamlit web UI for single-user investigations at `http://localhost:8501`.
- Configurable dark web search source registry in `sources.yml`.
- Source health reporting for success, timeout, HTTP error, Tor/DNS failure, parse failure, zero results, latency, and result count.
- AI Query Expansion with Conservative, Exploratory, and Off modes.
- Intent-aware search planning for handles, person names, emails/domains, organizations, brands, technical IOCs, and freeform threat searches.
- Query audit trail showing generated queries, query reason, source, phase, intent, and result count.
- Deterministic artifact extraction for onion URLs, clearnet URLs, emails, domains, IPs, CVEs, hashes, cryptocurrency addresses, and handles.
- Safer scraping with URL validation, redirect limits, content caps, duplicate handling, unsupported content-type handling, and prompt hardening.
- Metadata-rich investigation persistence with source provenance, source health snapshot, extracted artifacts, scraped URLs, query plan, query runs, and final summary.
- Multi-provider LLM support for OpenAI, Anthropic, Google Gemini, OpenRouter, Ollama, and llama.cpp-compatible local endpoints.
- Optional model routing for cheaper query expansion and triage models plus stronger final report models.

## Why OnionIntel

Dark web search tools often fail in quiet ways: stale onion sources go offline, search engines return generic marketplace pages, result counts vary by Tor circuit, and final reports can overstate weak evidence. OnionIntel emphasizes reliability and auditability:

- failed sources are visible;
- dead sources are skipped during the current run after failure;
- raw results and qualified results are tracked separately;
- generic infrastructure links are labeled instead of treated as target evidence;
- LLM-generated query variants are bounded and saved;
- scraped page text is treated as untrusted input.

## Quick Start

### 1. Clone and configure

```bash
git clone https://github.com/mythofkas-commits/onionintel.git
cd onionintel
cp .env.example .env
```

Edit `.env` and configure at least one hosted or local model provider.

OpenAI example:

```env
OPENAI_API_KEY=your_openai_api_key
```

Ollama from Docker on Windows or macOS:

```env
OLLAMA_BASE_URL=http://host.docker.internal:11434
```

### 2. Run with Docker Compose

```bash
docker compose up --build
```

The Compose setup builds the improved Robin/OnionIntel image as
`robin:reliable-v1` and bind-mounts this checkout into `/app`, so local repo
changes are reflected in the running `robin` container after Streamlit reloads.
Rebuild only when dependencies or the Dockerfile change:

```bash
docker compose up -d --build --force-recreate
```

Open:

```text
http://localhost:8501
```

### 3. Run with Docker directly

```bash
docker build -t onionintel .
docker run --rm \
  --env-file .env \
  -p 8501:8501 \
  -v "$(pwd)/investigations:/app/investigations" \
  onionintel
```

PowerShell:

```powershell
docker build -t onionintel .
docker run --rm `
  --env-file .env `
  -p 8501:8501 `
  -v "${PWD}\investigations:/app/investigations" `
  onionintel
```

## Docker Runtime

The container starts Tor, waits for the SOCKS listener, then waits for a usable Tor circuit before starting Streamlit. This avoids starting searches while Tor is still bootstrapping.

Important paths:

- `.env`: local provider keys and model endpoints. Do not commit real secrets.
- `investigations/`: saved investigation JSON files.
- `sources.yml`: dark web source registry.

## Source Registry

Search sources are configured in `sources.yml`:

```yaml
sources:
  - name: TorDex
    url_template: "http://example.onion/search?query={query}"
    enabled: true
    parser: generic
    timeout: 25
    notes: "Example Tor-native onion search source."
```

Supported fields:

- `name`
- `url_template`
- `enabled`
- `parser`
- `timeout`
- `notes`

Sources are not permanently disabled by runtime failures. A failed source is skipped for later query variants in the current process, while permanent source changes remain explicit in `sources.yml`.

## AI Query Expansion

OnionIntel can generate bounded search plans from the base query plus optional investigator context.

Modes:

- `Off`: single refined query.
- `Conservative`: bounded query variants with low-risk probes.
- `Exploratory`: larger query budget with optional artifact pivots.

Search intents:

- `person_name`
- `handle`
- `email_or_domain`
- `org_or_brand`
- `technical_ioc`
- `freeform_threat`

The Search Intent controls search strategy. The Prompt Setting controls the report style.

## Artifact Extraction

Before the final report, OnionIntel extracts:

- onion URLs
- clearnet URLs
- email addresses
- domains
- IP addresses
- CVEs
- hashes
- cryptocurrency addresses
- handles

Artifacts are saved with the investigation and can be used for follow-up pivots.

## Development

Install dependencies:

```bash
pip install -r requirements.txt
```

Run locally:

```bash
streamlit run ui.py
```

Run tests:

```bash
python -m unittest discover -s tests -v
```

Build Docker image:

```bash
docker build -t onionintel .
```

## SEO Keywords

Dark web OSINT, onion search engine, Tor search, Tor OSINT, dark web monitoring, cyber threat intelligence, Docker OSINT tool, Streamlit OSINT app, AI OSINT assistant, LLM investigation assistant, onion directory search, breach intelligence, source provenance, investigation audit trail, artifact extraction, threat intelligence workflow.

## Attribution And License

OnionIntel is based on the Robin dark web OSINT application by Apurv Singh Gautam and includes additional Docker, source reliability, audit trail, AI query expansion, intent-aware search, and safer scraping work.

The inherited project is licensed under the MIT License:

> Copyright (c) 2025 Apurv Singh Gautam

The original MIT license notice is retained in [LICENSE](LICENSE), as required by the license.
