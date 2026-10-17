# 🚀 GraphOS Deployment Guide

This guide covers production deployment for the **GraphOS Universal Graph Intelligence Platform**, featuring a Next.js frontend, FastAPI agent backend, MCP server, and FalkorDB knowledge graph.

---

## 🏗️ Architecture Overview

```text
┌───────────────────────────────┐
│       Next.js Frontend        │  <-- Hosted on Vercel / Cloudflare Pages
│  (Landing + React Explorer)   │
└───────────────┬───────────────┘
                │ HTTP / SSE (/api/investigate/stream)
                ▼
┌───────────────────────────────┐
│     FastAPI Agent Backend     │  <-- Hosted on Render / Fly.io / Container
│   (GraphOSInvestigator + SSE) │
└───────────────┬───────────────┘
                │ MCP Client (stdio or SSE)
                ▼
┌───────────────────────────────┐
│     GraphOS MCP Server        │  <-- Read-only Graph Exploration Engine
└───────────────┬───────────────┘
                │ Cypher Queries (Read-only)
                ▼
┌───────────────────────────────┐
│       FalkorDB Cloud          │  <-- Managed Knowledge Graph Instance
└───────────────────────────────┘
```

---

## 🔐 Environment Variables

### 1. Frontend (`frontend/.env`)
| Variable | Description | Example / Default |
| :--- | :--- | :--- |
| `NEXT_PUBLIC_API_URL` | Public URL of the FastAPI backend service | `http://localhost:8000` or `https://api.graphos.app` |

### 2. Backend (`.env`)
| Variable | Required | Description | Example |
| :--- | :--- | :--- | :--- |
| `NVIDIA_API_KEY` | Optional* | NVIDIA NIM API key for GPT-OSS 20B inference | `nvapi-xxxxxxxxxxxx` |
| `LLM_PROVIDER` | No | Provider: `nvidia`, `openai`, `anthropic`, `mock` | `nvidia` |
| `LLM_MODEL` | No | Model identifier | `openai/gpt-oss-20b` |
| `FALKORDB_HOST` | Yes | FalkorDB database host | `xxxxxx.falkordb.cloud` |
| `FALKORDB_PORT` | Yes | FalkorDB database port | `12345` |
| `FALKORDB_USERNAME` | No | FalkorDB username | `default` |
| `FALKORDB_PASSWORD` | Yes | FalkorDB database password | `secret_password` |
| `FALKORDB_GRAPH` | No | Active tenant graph name | `graphos_live` |
| `PORT` | No | Port for FastAPI server | `8000` |

*\* Note: If `NVIDIA_API_KEY` is not provided, the system supports `LLM_PROVIDER=mock` or rich offline demo scenarios.*

---

## 📦 Local Development

### 1. Start the FastAPI Backend
```bash
# From workspace root
python -m uvicorn agent.api:app --host 0.0.0.0 --port 8000 --reload
```
Verify health:
```bash
curl http://localhost:8000/api/health
```

### 2. Start the Next.js Frontend
```bash
cd frontend
npm install
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## 🌐 Production Deployment

### Option A: Frontend on Vercel
1. Push this repository to GitHub.
2. In the Vercel Dashboard, import the repository and select `frontend` as the **Root Directory**.
3. Set the Environment Variable:
   - `NEXT_PUBLIC_API_URL`: Your deployed backend URL (e.g. `https://graphos-api.onrender.com`).
4. Click **Deploy**.

### Option B: Backend on Render / Fly.io / Docker
Deploy using the included root `Dockerfile`:
```bash
# Build Docker container
docker build -t graphos-backend .

# Run with environment variables
docker run -p 8000:8000 --env-file .env graphos-backend python -m uvicorn agent.api:app --host 0.0.0.0 --port 8000
```

---

## 🛡️ Security & Read-Only Guardrails

- All database access is strictly mediated by the GraphOS MCP server.
- The web frontend **never** connects directly to FalkorDB; credentials stay entirely server-side.
- Application guardrails enforce read-only Cypher operations, rejecting any mutation (`CREATE`, `MERGE`, `DELETE`, `DROP`).
