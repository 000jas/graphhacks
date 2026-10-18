# 🌌 GraphOS — Evidence-Bound Graph AI Agent

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-Model%20Context%20Protocol-green.svg)](https://modelcontextprotocol.io/)
[![FalkorDB](https://img.shields.io/badge/FalkorDB-Cloud%20Graph-red.svg)](https://www.falkordb.com/)
[![Tests](https://img.shields.io/badge/tests-42%20passed-brightgreen.svg)](tests/)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](Dockerfile)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-yellow.svg)](LICENSE)

**GraphOS** is a production-grade, CLI-first autonomous AI agent that investigates complex organizational, infrastructural, and dependency problems using connected graph data. 

Powered by **FalkorDB Cloud** and the **Model Context Protocol (MCP)**, GraphOS navigates relationships between systems, teams, code, events, and policies to uncover root causes and deliver grounded, verifiable conclusions.

```text
  ██████╗ ██████╗  █████╗ ██████╗ ██╗  ██╗ ██████╗ ███████╗
 ██╔════╝ ██╔══██╗██╔══██╗██╔═══██╗██║  ██║██╔═══██╗██╔════╝
 ██║  ███╗██████╔╝███████║██████╔╝ ███████║██║   ██║███████╗
 ██║   ██║██╔══██╗██╔══██║██╔═══╝  ██╔══██║██║   ██║╚════██║
 ╚██████╔╝██║  ██║██║  ██║██║     ██║  ██║╚██████╔╝███████║
  ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝  ╚═╝ ╚═════╝ ╚══════╝

  Connected-data intelligence from the terminal.

  Model       NVIDIA · openai/gpt-oss-20b
  Graph       FalkorDB Cloud (Connected)
  Tools       MCP (32 read-only / 37 available)
  Mode        READ ONLY (Strict Guardrails)

graphos ❯ Why is the payments release delayed?
```

---

## 💡 The Problem & The Mission

### The Problem
Conventional AI agents analyze isolated documents or flat keyword searches. They frequently:
- **Miss critical dependencies** across systems, pull requests, tasks, and personnel.
- **Hallucinate causation** from loose correlation without structural evidence.
- **Lose context between sessions**, repeating the same queries from scratch.
- **Fail to explain *why*** a conclusion was reached with verifiable audit trails.

### The GraphOS Mission
> **GraphOS uses connected data to understand a situation, reason across multi-hop relationships, decide what should happen, and explain why.**

It builds conclusions strictly from evidence and the links between that evidence—never from unsupported assumptions or guesses.

---

## 🏛️ Core Principles

1. **The Graph is Central**: FalkorDB Cloud is the foundation of investigation and reasoning—not a decorative visualizer. Graph traversal directly dictates agent decisions.
2. **Evidence Before Confidence**: Every finding cites verified entity IDs, properties, and relationship chains (`Entity A` ➔ `Blocked By` ➔ `Entity B`). Missing data is reported as uncertainty rather than assumed away.
3. **Genuine MCP Tool Discovery**: Discovers and executes 37 graph analysis tools dynamically via Model Context Protocol (`stdio` or Streamable HTTP).
4. **Zero-Trust Guardrails**: Hardware-enforced read-only mode, parameter boundary checks, loop detection, and untrusted graph content boundary wrapping (`<untrusted_graph_data>`).
5. **Provider-Agnostic LLM Engine**: Native support for **NVIDIA** (`openai/gpt-oss-20b`), **OpenAI** (`gpt-4o`), **Anthropic Claude** (`claude-3-5-sonnet`), local **Ollama**, and an offline **Mock Provider**.
6. **Accountable & Interactive**: Delivers clear root-cause explanations with interactive numbered follow-up actions for terminal operators.

---

## 🚀 Installation & Setup Guide

### 📋 Prerequisites
- **Python 3.10 – 3.13** (`python3 --version`)
- **Git**
- **FalkorDB Instance** (FalkorDB Cloud endpoint or local instance)
- **LLM API Key** (NVIDIA AI Foundation, OpenAI, Anthropic, or local Ollama)

---

### Option A: Standard Local Installation (Recommended)

#### 1. Clone & Setup Environment
```bash
git clone https://github.com/000jas/graphhacks.git
cd graphhacks

# Create and activate dedicated virtual environment
python3 -m venv .venv
source .venv/bin/activate
```

#### 2. Install Dependencies & CLI
```bash
# Upgrade pip and install requirements
pip install --upgrade pip
pip install -r requirements.txt
pip install -e .

# Ensure CLI script is executable
chmod +x graphos
```
*(Alternatively, simply run `make install`)*

#### 3. Configure Credentials
Copy the template configuration file:
```bash
cp .env.example .env
```
Edit `.env` with your FalkorDB Cloud and LLM provider credentials:
```dotenv
# --- FalkorDB Cloud Connection ---
FALKORDB_HOST=your-falkordb-host.cloud
FALKORDB_PORT=6379
FALKORDB_USERNAME=default
FALKORDB_PASSWORD=your_falkordb_password
FALKORDB_SSL=false
GRAPHOS_GRAPH_NAME=graphos_dev

# --- LLM Provider Settings (Default: NVIDIA) ---
LLM_PROVIDER=nvidia
LLM_MODEL=openai/gpt-oss-20b
LLM_API_BASE=https://integrate.api.nvidia.com/v1
NVIDIA_API_KEY=nvapi-your-nvidia-api-key

# --- Safety Guardrails ---
AGENT_READ_ONLY=true
AGENT_MAX_ITERATIONS=10
AGENT_MAX_TOOL_CALLS=20
```

#### 4. Verify Installation
Run the automated system diagnostics check:
```bash
./graphos doctor
# or: make doctor
```
Run the automated test suite (42 tests):
```bash
make test
# or: pytest tests
```

---

### Option B: Docker Container Installation

GraphOS is fully containerized with a production multi-stage `Dockerfile` and `docker-compose.yml`:

```bash
# 1. Configure environment
cp .env.example .env

# 2. Build the Docker container
make docker-build
# or: docker compose build

# 3. Run system diagnostics inside Docker
docker compose run --rm agent doctor

# 4. Launch the interactive terminal agent
make docker-run
# or: docker compose run --rm agent

# 5. Launch the Streamlit Analytics Dashboard (http://localhost:8501)
make docker-dashboard
# or: docker compose up -d dashboard
```

---

## 🕹️ Usage Modes

### Mode 1: Interactive Terminal Agent (REPL)

Launch the interactive prompt session:
```bash
./graphos
```

```text
graphos ❯ Why is the payments release delayed?

  ◈ Investigating objective: Why is the payments release delayed?
  ◈ Reasoning over evidence graph (step 1/10)...
  ◈ Calling MCP tool: search_connected_entities (query='payments', kind='Release')
  ◈ Calling MCP tool: traverse_relationships (entity_id='release-payments-2026-10', depth=2)
  ◈ Calling MCP tool: get_entity_profile (entity_id='task-code-review-482')
  ◈ Calling MCP tool: get_entity_profile (entity_id='person-liam-patel')
  ✓ Investigation completed (28.9s, 7 tool calls)

🎯 Root Cause Summary
The Payments Release is delayed because the code-review task for PR #482 is stalled:
its assigned reviewer, Liam Patel, is on leave. PR #482 cannot merge without review,
keeping the production release blocked.

🔗 Chain of Evidence
 Payments Release October 2026
    └─ BLOCKED_BY ── PR #482: Update payments SDK
           └─ BLOCKED_BY ── Review PR #482 (Task)
                  └─ ASSIGNED_TO ── Liam Patel (Person)
                         └─ availability: on_leave

💡 Key Contributing Facts
 • Liam Patel – assigned reviewer for the code review, status: on_leave.
 • Review PR #482 – status: blocked; cannot complete until reviewer returns.
 • Security review task – open and awaiting completion.

⚡ Suggested Next Actions
[1] Reassign the code-review task to an available reviewer (e.g. Ravi Kulkarni or Maya Chen).
[2] Prioritize the security review task with Priya Shah to avoid subsequent delay.
[3] Assess blast radius on checkout service if PR #482 is fast-tracked.

╭──────────────────────── 🔗 Verified Dependency Chain ────────────────────────╮
│   • release-payments-2026-10 ➔ Payments Release October 2026 ➔ PR #482       │
│   • release-payments-2026-10 ➔ PR #482 ➔ Review PR #482 ➔ Liam Patel (on_leave)│
╰──────────────────────────────────────────────────────────────────────────────╯
  ⚡ Verified in 28.9s · 7 tool calls · 34 entities grounded · nvidia (openai/gpt-oss-20b)

👉 Interactive Next Step: Choose [1-3], ask a follow-up, or press Enter to finish: 
```

### Mode 2: Direct One-Shot Investigation

Execute single queries for scripts, workflows, or terminal automation:
```bash
# Human-readable report
./graphos ask "Why is the payments release delayed?"

# Machine-readable JSON for CI/CD pipelines
./graphos ask "Why is the payments release delayed?" --json
```

### Mode 3: Visual Knowledge Graph Dashboard

Launch the Streamlit analytics interface:
```bash
make dashboard
# or: streamlit run dashboard/app.py
```
Open **http://localhost:8501** to inspect topological metrics, graph algorithms, and entity blast radiuses visually.

---

## 🩺 Diagnostic Subcommands

| Command | Description |
| :--- | :--- |
| `./graphos doctor` | Comprehensive health check (Python, dependencies, FalkorDB, MCP, credentials, guardrails) |
| `./graphos status` | Live status of model, cloud graph, transport, and discovered tools |
| `./graphos config` | Safe runtime configuration report with all secrets and passwords masked |
| `./graphos tools` | Catalog of all 32 discovered read-only MCP tools and parameter schemas |
| `./graphos schema` | Discovered runtime schema, topological counts, and label catalog |
| `./graphos refresh`| Force immediate cache invalidation and re-discovery of FalkorDB graph schema |

---

## 💻 Supported REPL Slash Commands

Within `./graphos`, use slash commands to inspect state dynamically:

| Slash Command | Action |
| :--- | :--- |
| `/help` | Show command reference guide and example queries |
| `/schema` | Inspect discovered node kinds, relationship types, and properties |
| `/status` | View live provider, MCP server, and database connection status |
| `/doctor` | Run deep diagnostic health checks in-session |
| `/config` | Display active runtime configuration with credentials redacted |
| `/tools` | List all exposed MCP tools and schemas |
| `/model [provider] [model]` | Dynamically switch LLM provider and model without restarting |
| `/history` | View turns, durations, and evidence metrics in current session |
| `/new`, `/reset` | Clear conversational context and start a fresh investigation |
| `/clear` | Clear terminal screen and redisplay status banner |
| `/exit`, `/quit` | Cleanly terminate session (or press `Ctrl+D`) |

---

## ⚙️ Provider Configuration Matrix

GraphOS is provider-agnostic. Switch providers via `.env`, the `--provider` flag, or `/model` in the REPL:

```bash
# NVIDIA AI Foundation (Default)
./graphos --provider nvidia --model openai/gpt-oss-20b

# OpenAI
./graphos --provider openai --model gpt-4o

# Anthropic Claude
./graphos --provider anthropic --model claude-3-5-sonnet-20241022

# Local Ollama
./graphos --provider ollama --model qwen2.5:7b

# Offline / Hermetic Demonstration (No API key needed)
./graphos --provider mock
```

---

## 🛡️ Zero-Trust Guardrail Architecture

GraphOS strictly enforces safety and security at the application boundary:

1. **Read-Only Allowlist**: Strips all mutating tools (`propose_action`, `execute_approved_action`, `record_outcome`) from the model's catalog before prompt construction and blocks them at execution time.
2. **Tool Name Sanitization**: Cleans chat template tokens (e.g. `<|channel|>commentary`) to ensure strict allowlist matching.
3. **Parameter Boundary Validation**: Enforces safety limits on traversal depth (`1 <= depth <= 6`), entity limits (`1 <= limit <= 50`), and query character lengths.
4. **Anti-Repetition Circuit Breaker**: Halts recurring tool loops with identical parameters.
5. **Prompt Injection Isolation**: Wraps retrieved graph data in `<untrusted_graph_data>` tags to prevent external content from overriding instructions.
6. **Secret Scrubbing**: API keys, passwords, and tokens are automatically masked in logs, diagnostics, and session storage.

---

## 📦 Discovered MCP Toolset (37 Tools)

GraphOS connects to FalkorDB via MCP and discovers 37 composable graph tools:

| Category | Tools Included |
| :--- | :--- |
| **Core Traversal & Search** | `search_connected_entities`, `get_entity_profile`, `traverse_relationships`, `find_shortest_evidence_path`, `retrieve_source_documents`, `check_policy`, `simulate_action` |
| **Topological Intelligence** | `discover_relationship_patterns`, `find_common_neighbors`, `find_alternative_paths`, `detect_critical_dependencies`, `detect_communities`, `detect_graph_anomalies`, `analyze_reachability`, `compare_connectivity` |
| **Investigation & Clustering**| `search_entities_advanced`, `compare_entities`, `investigate_entity_cluster`, `extract_investigation_subgraph`, `compare_evidence_paths`, `batch_get_entities`, `generate_investigation_summary` |
| **Centrality & Algorithms** | `run_graph_algorithm` (PageRank, Betweenness, Closeness, Degree, Connected Components, Cycle Detection) |
| **Risk & Counterfactuals** | `analyze_graph_impact`, `assess_change_risk_and_impact`, `evaluate_candidate_actions` |
| **Evidence & Temporal Graph** | `evaluate_evidence_quality`, `detect_conflicting_evidence`, `inspect_temporal_graph` |
| **Schema & Memory** | `discover_graph_schema`, `query_decision_memory`, `run_read_only_cypher_query` |

---

## 🏗️ Architecture

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        Terminal CLI Entry Points                       │
│  - Interactive REPL: `graphos`                                         │
│  - One-shot command: `graphos ask "..."`                               │
│  - Diagnostics: `graphos doctor`, `status`, `config`, `tools`          │
│  - Scripting options: `--json`, `--quiet`, `--verbose`, `--no-color`   │
└────────────────────────────────────┬───────────────────────────────────┘
                                     │
                                     ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        Session Manager (`agent/session.py`)            │
│  - Multi-turn conversation state & context management                  │
│  - Sanitized local session persistence (`~/.graphos/sessions`)         │
│  - Turn-level metrics & evidence accumulation                          │
└────────────────────────────────────┬───────────────────────────────────┘
                                     │
                                     ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        Agent Engine (`agent/engine.py`)                │
│  - Provider-agnostic investigation loop & plan synthesis               │
│  - Dynamic runtime graph schema discovery & prompt injection           │
│  - Zero-Trust Guardrails & Read-Only allowlist enforcement             │
│  - Anti-loop circuit breaker & untrusted data wrapping                 │
└───────────────────┬────────────────────────────────┬───────────────────┘
                    │                                │
                    ▼                                ▼
┌──────────────────────────────────────┐  ┌──────────────────────────────┐
│  LLM Provider Adapters               │  │  MCP Client (`mcp_client.py`)│
│  - NVIDIA (openai/gpt-oss-20b)       │  │  - stdio or streamable_http  │
│  - OpenAI (gpt-4o)                   │  │  - Dynamic tool discovery    │
│  - Anthropic (claude-3-5-sonnet)     │  │  - Robust timeout handling   │
│  - Ollama (local inference)          │  └──────────────┬───────────────┘
│  - Mock (deterministic offline test) │                 │
└──────────────────────────────────────┘                 ▼
                                          ┌──────────────────────────────┐
                                          │  GraphOS MCP Server          │
                                          │  (`mcp_server/server.py`)    │
                                          │  (37 composable graph tools) │
                                          └──────────────┬───────────────┘
                                                         │
                                                         ▼
                                          ┌──────────────────────────────┐
                                          │  FalkorDB Cloud Graph Engine │
                                          │  (Live Knowledge Graph)      │
                                          └──────────────────────────────┘
```

---

## 🛠️ Developer Reference (`Makefile`)

| Command | Action |
| :--- | :--- |
| `make install` | Install project dependencies and editable package |
| `make test` | Run complete automated unit and integration test suite (42 tests) |
| `make doctor` | Execute full system health audit and diagnostic report |
| `make status` | Display live connection status of provider, graph, and MCP |
| `make run` | Launch interactive terminal REPL (`./graphos`) |
| `make ask Q="..."` | Run one-shot investigation query |
| `make dashboard` | Launch Streamlit Analytics Dashboard on `http://localhost:8501` |
| `make docker-build` | Build `graphos:latest` Docker image |
| `make docker-run` | Run interactive terminal agent inside Docker |
| `make docker-dashboard` | Run Streamlit dashboard container |
| `make docker-down` | Stop running Docker containers |
| `make clean` | Clean up `__pycache__`, pytest caches, and temporary files |

---

## 📄 License

Licensed under the **Apache License 2.0**. See [LICENSE](LICENSE) for details.
