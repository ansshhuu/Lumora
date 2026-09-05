<div align="center">

# 🔍 Lumora

### Ask questions about any codebase. Get clear, accurate answers.

**Lumora** is a developer tool that lets you explore and understand GitHub repositories using plain English questions. Instead of manually reading through files, you describe what you want to know and Lumora finds the answer directly from the code.

[![CI](https://github.com/ansshhuu/Lumora/actions/workflows/ci.yml/badge.svg)](https://github.com/ansshhuu/Lumora/actions/workflows/ci.yml)
![Coverage](https://img.shields.io/badge/coverage-92%25-brightgreen?style=flat-square)
![Tests](https://img.shields.io/badge/tests-274%20passing-brightgreen?style=flat-square)
![Status](https://img.shields.io/badge/status-in%20development-yellow?style=flat-square)
![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue?style=flat-square&logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green?style=flat-square&logo=fastapi)
![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)

</div>

---

## 📌 The Problem: Why Does This Project Exist?

Understanding an unfamiliar codebase takes time, often days.

You clone the repository, open dozens of files, search through folders, and still struggle to answer basic questions: Where is the login system? What does this module depend on? Why was this designed this way?

Lumora solves this by letting you ask those questions directly, and answering them using the actual code.

---

## ✨ What Lumora Does

| You Ask | Lumora Does |
|---------|------------|
| *"Where is user login handled?"* | Finds the exact files and functions responsible, and explains how they work |
| *"What does the payment module depend on?"* | Maps out all the components and files that the module relies on |
| *"Give me an overview of how this project is structured"* | Reads the entire repository and produces a plain-English summary |
| *"List all the API endpoints and what they do"* | Locates every endpoint and explains its purpose |

---

## 🏗️ How It Works

Lumora processes your question through three stages:

```
┌─────────────────────────────────────────────────────────┐
│                    YOUR QUESTION                         │
│           "Where is login handled?"                      │
└─────────────────────┬───────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│                   Web API  (lumora/api/)                 │
│         Receives your question and routes it             │
└─────────────────────┬───────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│              AI Reasoning Agent  (lumora/agent/)         │
│                                                          │
│   The agent thinks through your question step by step,  │
│   uses tools to search the codebase, reviews what it    │
│   finds, and repeats until it has a confident answer.   │
│                                                          │
│   Available tools:                                       │
│   ├── Code search       (finds similar code by meaning) │
│   ├── Structure lookup  (finds functions and classes)   │
│   ├── File tree         (understands folder layout)     │
│   └── Dependency map    (traces what depends on what)   │
└──────────┬──────────────────────────┬───────────────────┘
           │                          │
           ▼                          ▼
┌─────────────────────┐   ┌──────────────────────────────┐
│   Code Search       │   │  Indexing Pipeline            │
│  (lumora/embeddings)│   │  (lumora/ingestion/)          │
│                     │   │                               │
│  Searches by        │   │  Downloads repo → Reads code  │
│  meaning, keywords, │   │  structure → Converts to      │
│  and code structure │   │  searchable format → Stores   │
└────────┬────────────┘   └──────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│                    Data Storage                          │
│                                                          │
│   Qdrant ────── Stores code in a searchable format       │
│   PostgreSQL ── Stores repository information            │
│   Redis ─────── Saves recent results for faster replies  │
└─────────────────────────────────────────────────────────┘
```

---

## 🛠️ Technologies Used

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Web API** | FastAPI | Handles incoming requests and sends back responses |
| **AI Agent** | LangGraph | Runs a step-by-step reasoning loop to answer questions accurately |
| **AI Framework** | LangChain | Connects the language model with search tools and memory |
| **Code Reader** | tree-sitter | Parses code files to understand their structure — functions, classes, imports |
| **Search Database** | Qdrant | Stores and searches code by meaning, not just keywords |
| **Main Database** | PostgreSQL  | Stores repository metadata and tracks database changes over time |
| **Cache** | Redis | Stores recent results to avoid repeated processing |
| **Background Jobs** | Celery | Handles repository indexing in the background without blocking the API |
| **Containers** | Docker + Docker Compose | Packages each service so it runs consistently on any machine |
| **Automation** | GitHub Actions | Runs code quality checks and tests automatically on every update |

---

## 📁 Project Structure

```
lumora/
├── .github/
│   └── workflows/
│       ├── ci.yml              # Lint and tests on every push and pull request
│       ├── docker.yml          # Placeholder — not yet implemented
│       └── release.yml         # Placeholder — not yet implemented
│
├── lumora/
│   ├── api/                    # FastAPI app — routes, auth, rate limiting
│   │   └── routes/             # /health, /index, /query
│   ├── agent/                  # LangGraph ReAct agent, tools and prompts
│   ├── ingestion/              # Repo cloning and file walking
│   ├── parsing/                # tree-sitter Python parser
│   ├── embeddings/             # Cohere embedding, Qdrant store and search
│   └── core/                   # Shared configuration
│
├── tests/
│   ├── unit/                   # Parser, walker, clone, embedder, tools,
│   │                           #   pipeline, search, Qdrant store, agent graph
│   ├── integration/
│   │   ├── test_ingestion_flow.py   # Walk + parse the fixture repo end to end
│   │   └── test_api_endpoints.py    # API routing, validation and auth
│   └── fixtures/
│       └── sample_repo/        # Small committed repo used by integration tests
│
├── docker/
│   ├── Dockerfile.api          # Container for the web API (multi-stage build)
│   ├── Dockerfile.worker       # Placeholder — indexing runs in the API for now
│   └── Dockerfile.sandbox      # Placeholder — not yet implemented
│
├── docker-compose.yml          # Runs the API and Qdrant together
├── docker-compose.dev.yml      # Placeholder — not yet implemented
├── pyproject.toml              # Dependencies and tool configuration
├── .env.example                # Template for required environment variables
├── CONTRIBUTING.md             # Guide for contributors
└── LICENSE                     # MIT License
```

---

## 🗺️ Roadmap

> **Current Phase: Production Ready** — testing and CI/CD complete; database, observability and a web UI still ahead.
>
> **Overall progress: ~80% complete.**

### Phase 1 — Foundation
- [x] Project structure and dependency management with Poetry
- [x] Docker container for the API, with Qdrant wired up via Compose *(worker and sandbox images are still empty placeholders)*
- [x] Automated checks via GitHub Actions — lint and tests *(release and Docker-build workflows are still empty placeholders)*
- [x] Test structure for unit and integration tests
- [x] Contribution guide and MIT License
- [x] Basic API with a working health check endpoint
- [x] Connect to Qdrant and run a simple code search
- [x] Read and understand Python file structure using tree-sitter
- [x] Index a repository end-to-end for the first time

### Phase 2 — AI Agent
- [x] Set up the reasoning agent using LangGraph
- [x] Build tools: code search, structure lookup, file tree *(dependency map not built — `fetch_file` + reasoning covers "what does X depend on" questions today, but there's no dedicated import-graph tool)*
- [ ] Add conversation memory so follow-up questions work
- [x] Answer a real question about a real repository end-to-end

### Phase 3 — Better Search
- [x] API key authentication on every endpoint (`X-API-Key` header)
- [x] Per-IP rate limiting on `/index` and `/query`
- [x] Health check endpoint reporting Qdrant connectivity
- [ ] Combine meaning-based, keyword, and structure-based search
- [ ] Support additional languages — JavaScript, Go, Java
- [ ] Add caching to speed up repeated queries
- [ ] Process repository indexing in the background without delays

### Phase 4 — Production Ready *(Current)*
- [x] Test suite — 274 tests across unit and integration, 92% coverage
- [x] CI/CD pipeline — lint and tests run automatically on every push and PR
- [ ] Full database integration with migration support
- [ ] Monitoring and observability with LangSmith
- [ ] Simple web interface for non-technical users
- [ ] Performance testing and optimization
- [ ] Public demo

---

## ⚡ Getting Started

> ⚠️ **Note:** Lumora is in early development. These instructions will be updated as the project progresses.

### Requirements

- Python 3.11 or higher
- Docker and Docker Compose
- Poetry

### Installation

```bash
# Download the project
git clone https://github.com/ansshhuu/Lumora.git
cd Lumora

# Set up your environment variables
cp .env.example .env

# Fill in COHERE_API_KEY, GROQ_API_KEY and API_KEY in .env, then start everything
docker compose up --build
```

Once running, open `http://localhost:8000/docs` in your browser to see the API.

If port 8000 or 6333 is already taken on your machine, set `API_PORT` or
`QDRANT_HTTP_PORT` in `.env` — no other change is needed.

Common tasks are wrapped in the Makefile: `make up`, `make down`, `make build`,
`make test`, `make lint`, and `make clean` (which also deletes indexed data).

### Development Mode

`docker-compose.dev.yml` is still an empty placeholder. For an auto-reloading
API, run it outside Docker against the Compose-managed Qdrant:

```bash
docker compose up -d qdrant
poetry run uvicorn lumora.api.main:app --reload
```

### Running Tests

```bash
poetry run pytest tests/

# With a coverage report
poetry run pytest tests/ --cov=lumora --cov-report=term-missing

# Lint
poetry run ruff check .
```

The suite needs no running services. Cohere, Groq and Qdrant are all mocked, so
it runs offline with no API keys and no Qdrant instance — which is exactly how
CI runs it.

---

## 🧪 Testing

274 tests, **92% line coverage** (537 statements, 43 uncovered) as reported by
`pytest-cov`.

| Suite | Tests | What it covers |
|---|---|---|
| `tests/unit/` | 217 | Parser, walker, clone, embedder, agent tools, pipeline, search, Qdrant store |
| `tests/integration/` | 55 | Full walk-and-parse over a committed fixture repo; API routing, validation and auth via `TestClient` |
| `tests/test_week4_manual.py` | 2 (+8 skipped) | Security and robustness checks; the 8 live tests skip unless a server is running at `LUMORA_TEST_BASE_URL` |

Coverage by area:

| Module | Coverage |
|---|---|
| `api/` (routes, security, models, limiter) | 89% |
| `embeddings/` (embedder, pipeline, search, store) | 99% |
| `parsing/` + `ingestion/` | 89% |
| `agent/` (tools, graph) | 94% |

The uncovered lines are almost entirely the real network calls the suite
deliberately mocks — `git clone`, Cohere embedding requests and Qdrant upserts.

Integration tests run against `tests/fixtures/sample_repo/`, a small package
committed to the repository rather than cloned at test time, so the expected
function and class counts are fixed and the tests need no network.

---

## 🔌 API Endpoints

Full interactive reference (request/response schemas, try-it-out) is auto-generated at
`http://localhost:8000/docs` once the server is running. Summary:

`/index` and `/query` require an `X-API-Key` header matching the `API_KEY` (or
`SECRET_KEY`) env var — a missing or wrong key returns `401`. Both are also rate limited
per-IP to `RATE_LIMIT_PER_MINUTE` (default 20/minute); exceeding it returns `429`.

`/health` is deliberately unauthenticated so load balancers and uptime monitors can probe
it. It reports only Qdrant reachability and exposes no repository data.

| Method & Path | Description | Notable responses |
|---|---|---|
| `GET /health` | Checks connectivity to Qdrant. No API key required. | `200` ok · `503` Qdrant unreachable |
| `POST /index` | Clones a public GitHub repo, parses it, and embeds it into a Qdrant collection. Body: `{"repo_url": "https://github.com/<owner>/<repo>"}`. | `400` invalid URL or repo exceeds `MAX_REPO_SIZE_MB` · `500` indexing failed |
| `POST /query` | Asks the reasoning agent a question against an indexed collection. Body: `{"question": "...", "collection": "<name>"}`. | `404` collection not found · `504` agent exceeded `QUERY_TIMEOUT_SECONDS` · `500` agent failed |

All error responses are generic JSON (`{"detail": "..."}` or `{"error": "..."}`) — unhandled
exceptions are logged server-side with a full traceback and never echoed back to the client.

---

## 💡 Design Decisions

<details>
<summary><b>Why does the agent think step by step instead of answering immediately?</b></summary>

A single-shot answer from an AI model is often incomplete — it might miss context or misunderstand the question. Lumora uses a reasoning loop where the agent searches the code, reviews what it finds, and searches again if needed before giving a final answer. This produces more accurate and reliable results, especially for complex questions.

</details>

<details>
<summary><b>Why does Lumora parse code structure instead of just reading the text?</b></summary>

If you split a file into chunks by character count, you might cut a function in half — making it impossible to understand. Lumora uses a tool called tree-sitter to read code the way a compiler does: it understands where each function begins and ends, what it imports, and what it calls. This means search results always contain complete, meaningful pieces of code.

</details>

<details>
<summary><b>Why is there only one application container?</b></summary>

Today the stack runs two services: the API and Qdrant. Indexing happens inside the API process, which offloads the slow clone-parse-embed work to a background thread so requests are not blocked. Separate worker and sandbox images are planned — `docker/Dockerfile.worker` and `docker/Dockerfile.sandbox` are placeholders — and splitting them out only pays off once indexing needs to outlive a request, which needs a queue in front of it. Building those containers before anything dispatches to them would add moving parts with nothing to run.

</details>

---
