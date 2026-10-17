# GraphOS — Provider-Agnostic, MCP-Powered AI Investigator

GraphOS is an evidence-bound graph intelligence agent architecture connecting autonomous LLMs to organizational knowledge graphs hosted in **FalkorDB Cloud** via the **Model Context Protocol (MCP)**.

---

## 🏛️ Architecture Overview

The system is engineered with strict separation of concerns across five core layers:

```
┌────────────────────────────────────────────────────────┐
│                   CLI / User Objective                 │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│                 Agent Engine (engine.py)               │
│  • Bounded Iterative Loop (Max Iterations, Budgets)    │
│  • Provider & Tool Call Normalization                  │
│  • Early Exit on Terminal Reasoning                    │
└────────────┬─────────────────────────────┬─────────────┘
             │                             │
             ▼                             ▼
┌───────────────────────────┐  ┌─────────────────────────┐
│ LLM Provider Layer        │  │ Guardrail Layer         │
│ (providers/)              │  │ (guardrails.py)         │
│ • NVIDIA (Default)        │  │ • Read-Only Enforcement │
│ • OpenAI                  │  │ • Mutating Blocklist    │
│ • Anthropic Claude        │  │ • Parameter Bounds      │
│ • Ollama                  │  │ • Anti-Loop Detection   │
│ • Mock (Autonomous/Canned)│  │ • Untrusted Data Encaps │
└───────────────────────────┘  └───────────┬─────────────┘
                                           │
                                           ▼
                               ┌─────────────────────────┐
                               │ MCP Client Layer        │
                               │ (mcp_client.py)         │
                               │ • Dynamic Tool Discovery│
                               │ • stdio & HTTP Transport│
                               └───────────┬─────────────┘
                                           │
                                           ▼
                               ┌─────────────────────────┐
                               │ Evidence Layer          │
                               │ (evidence.py)           │
                               │ • Fact vs Inference     │
                               │ • Provenance Citations  │
                               │ • Multi-Hop Path Chains │
                               │ • Gaps & Uncertainty    │
                               └───────────┬─────────────┘
                                           │
                                           ▼
                              [FalkorDB Cloud Knowledge Graph]
```

---

## 🚀 Quickstart & Setup

### 1. Prerequisites & Virtual Environment
Use the dedicated project virtual environment (`agent/venv`):

```bash
# Verify venv Python version
agent/venv/bin/python --version
# Output: Python 3.13.9
```

### 2. Environment Configuration
Copy `agent/.env.example` to `agent/.env` (or review existing configuration):

```bash
cp agent/.env.example agent/.env
```

Configuration variables in `agent/.env`:
```dotenv
# Active LLM Provider: 'nvidia', 'openai', 'anthropic', 'ollama', or 'mock'
LLM_PROVIDER=nvidia

# NVIDIA Configuration (Initial Default)
LLM_MODEL=openai/gpt-oss-20b
LLM_API_BASE=https://integrate.api.nvidia.com/v1
NVIDIA_API_KEY=nvapi-...

# OpenAI Configuration
OPENAI_API_KEY=sk-...

# Anthropic Claude Configuration
ANTHROPIC_API_KEY=sk-ant-...

# Ollama Local Configuration
OLLAMA_BASE_URL=http://localhost:11434

# MCP Client Transport
MCP_TRANSPORT=stdio
MCP_SERVER_COMMAND=python mcp_server/server.py

# Guardrails & Budgets
GRAPHOS_READ_ONLY=true
GRAPHOS_MAX_ITERATIONS=10
GRAPHOS_MAX_TOOL_CALLS=20
```

---

## 🔄 Provider Switching (Configuration-Driven)

The agent switches between model providers purely through configuration flags without code changes:

### NVIDIA (Default)
```bash
agent/venv/bin/python -m agent --provider nvidia
```

### OpenAI
```bash
agent/venv/bin/python -m agent --provider openai --model gpt-4o
```

### Anthropic Claude
```bash
agent/venv/bin/python -m agent --provider anthropic --model claude-3-5-sonnet-20241022
```

### Ollama (Local Inference)
```bash
agent/venv/bin/python -m agent --provider ollama --model llama3.1
```

### Mock (Offline / Autonomous Testing)
```bash
agent/venv/bin/python -m agent --provider mock
```

---

## 🛡️ Guardrails & Read-Only Enforcement

The GraphOS Investigator operates strictly in **READ-ONLY** mode:
1. **Dynamic Tool Filtering**: When the MCP server advertises tools, all mutating functions (`propose_action`, `execute_approved_action`, `record_outcome`, `record_investigation_finding`, `supersede_finding`) are stripped before schemas are exposed to the model.
2. **Pre-Execution Interception**: Any unauthorized tool call attempted by the model is intercepted and rejected with a `PERMISSION DENIED` guardrail response.
3. **Anti-Repetition Detection**: Prevents infinite loops by terminating or blocking identical sequential calls.
4. **Prompt Injection Containment**: All raw graph outputs and document contents are wrapped in `<untrusted_graph_data source='falkordb_mcp'>` tags before ingestion into conversational context.

---

## 🧪 Automated Testing

Run the comprehensive test suite (41 tests across 11 test modules) using the local venv:

```bash
agent/venv/bin/pytest agent/tests
```

### Test Suite Breakdown:
- `test_config.py`: Environment variable loading, validation, and API key masking.
- `test_providers.py`: Provider initialization, schema conversion (OpenAI & Anthropic formats), and factory routing.
- `test_guardrails.py`: Read-only blocking, parameter limits, loop detection, and untrusted wrapping.
- `test_mcp_client.py`: Dynamic tool discovery and execution over MCP stdio client.
- `test_evidence.py`: Grounded fact extraction, provenance metadata, path chains, and policy results.
- `test_agent_engine.py`: Iteration budget limits, immediate answer termination, and streaming callbacks.
- `test_investigations.py`: Live end-to-end multi-step investigations over cloud FalkorDB.
- `test_cli_agent.py`: CLI one-shot execution, JSON output mode, and multi-turn REPL follow-ups.
- `test_session.py`: Persistent session state serialization, turn history, and replay.
- `test_universal_graph.py`: Schema-adaptive graph profiling and universal domain support.

---

## 🔎 Demonstration Investigations

### 1. Root Cause Analysis: Payments Release Delay
```bash
agent/venv/bin/python -m agent --provider mock -q "Why is the payments release delayed? Investigate the connected data and explain the root cause with supporting evidence."
```
**Outcome**: Discovers `release-payments-2026-10` -> `service-payment-api` -> `pr-482` -> `task-code-review-482` -> `person-liam-patel` (on leave via `event-liam-leave`) and identifies concurrent uncompleted security review `task-security-review-482`.

### 2. Unknown Entity / Evidence Gap Handling
```bash
agent/venv/bin/python -m agent --provider mock -q "Investigate the status of QuantumTeleportationService and explain why its release is blocked."
```
**Outcome**: Discovers 0 matching nodes, prevents hallucinated edges, and honestly reports insufficient graph evidence.
