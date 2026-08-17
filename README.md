<div align="center">

# 🔍 Lumora

### Ask questions about any codebase. Get clear, accurate answers.

**Lumora** is a developer tool that lets you explore and understand GitHub repositories using plain English questions. Instead of manually reading through files, you describe what you want to know and Lumora finds the answer directly from the code.

![Status](https://img.shields.io/badge/status-in%20development-yellow?style=flat-square)
![Python](https://img.shields.io/badge/python-3.12+-blue?style=flat-square&logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green?style=flat-square&logo=fastapi)
![Docker](https://img.shields.io/badge/Docker-ready-blue?style=flat-square&logo=docker)
![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)
![CI](https://img.shields.io/badge/CI-GitHub%20Actions-black?style=flat-square&logo=githubactions)

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
│                   Web API  (src/api/)                    │
│         Receives your question and routes it             │
└─────────────────────┬───────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│              AI Reasoning Agent  (src/agent/)            │
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
│   (src/retrieval/)  │   │  (src/ingestion/)             │
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
│       ├── ci.yml              # Runs code checks and tests on every push
│       ├── docker.yml          # Verifies that Docker builds succeed
│       └── release.yml         # Handles automatic version releases
│
├── src/
│   └── lumora/
│       ├── api/                # Web API — handles requests and responses
│       ├── agent/              # AI agent — reasoning and tool use logic
│       ├── ingestion/          # Indexing pipeline — downloads and processes repositories
│       ├── retrieval/          # Search logic — finds relevant code for a query
│       └── core/               # Shared configuration, models, and utilities
│
├── tests/
│   ├── unit/
│   │   ├── test_chunker.py     # Tests for how code is split into searchable pieces
│   │   ├── test_retrieval.py   # Tests for the search system
│   │   └── test_agent.py       # Tests for the AI agent tools
│   └── integration/
│       └── test_index_flow.py  # End-to-end test for the full indexing process
│
├── docker/
│   ├── Dockerfile.api          # Container for the web API
│   ├── Dockerfile.worker       # Container for background indexing jobs
│   └── Dockerfile.sandbox      # Isolated container for safe code processing
│
├── migrations/                 # Database schema change history
├── docs/                       # Additional documentation
├── docker-compose.yml          # Runs all services together for production
├── docker-compose.dev.yml      # Development configuration with auto-reload
├── pyproject.toml              # Project dependencies and tool configuration
├── Makefile                    # Shortcuts for common development commands
├── .env.example                # Template for required environment variables
├── CONTRIBUTING.md             # Guide for contributors
└── LICENSE                     # MIT License
```

---

## 🗺️ Roadmap

> **Current Phase: Foundation** — Project setup and core infrastructure

### Phase 1 — Foundation *(Current)*
- [x] Project structure and dependency management with Poetry
- [x] Docker containers for API, background worker, and sandbox
- [x] Automated checks via GitHub Actions — code quality, tests, and releases
- [x] Test structure for unit and integration tests
- [x] Contribution guide and MIT License
- [x] Basic API with a working health check endpoint
- [ ] Connect to Qdrant and run a simple code search
- [ ] Read and understand Python file structure using tree-sitter
- [ ] Index a repository end-to-end for the first time

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

### Phase 4 — Production Ready
- [ ] Full database integration with migration support
- [ ] Monitoring and observability with LangSmith
- [ ] Simple web interface for non-technical users
- [ ] Performance testing and optimization
- [ ] Public demo

---

## ⚡ Getting Started

> ⚠️ **Note:** Lumora is in early development. These instructions will be updated as the project progresses.

### Requirements

- Python 3.12 or higher
- Docker and Docker Compose
- Poetry

### Installation

```bash
# Download the project
git clone https://github.com/yourusername/lumora.git
cd lumora

# Set up your environment variables
cp .env.example .env

# Start all services
docker-compose up --build
```

Once running, open `http://localhost:8000/docs` in your browser to see the API.

### Development Mode

For local development with automatic reload on file changes:

```bash
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up
```

### Running Tests

```bash
# Using the shortcut
make test

# Or directly
poetry run pytest tests/
```

### Available Commands

```bash
make lint       # Check code quality
make test       # Run all tests
make build      # Build Docker images
make up         # Start all services
make down       # Stop all services
```

---

## 🔌 API Endpoints

Full interactive reference (request/response schemas, try-it-out) is auto-generated at
`http://localhost:8000/docs` once the server is running. Summary:

Every endpoint below requires an `X-API-Key` header matching the `API_KEY` (or `SECRET_KEY`)
env var — missing or wrong key returns `401`. `/index` and `/query` are additionally rate
limited per-IP to `RATE_LIMIT_PER_MINUTE` (default 20/minute) — exceeding it returns `429`.

| Method & Path | Description | Notable responses |
|---|---|---|
| `GET /health` | Checks connectivity to Qdrant. | `200` ok · `503` Qdrant unreachable |
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
<summary><b>Why are there three separate Docker containers?</b></summary>

Each container has a specific job. The API container handles user requests. The worker container handles the slower task of downloading and indexing repositories in the background, so the API stays fast. The sandbox container processes code in an isolated environment for safety. Keeping them separate also makes it easier to scale or update each one independently.

</details>

---
