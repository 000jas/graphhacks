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

### 1. Backend Deployment on Render (Root Directory)

You can deploy the backend directly to **Render** as a Python Web Service or via the included [render.yaml](file:///Users/ojasdhapse/Ojas/projects2/graphs/render.yaml) Blueprint:

#### Render Dashboard Settings
- **Root Directory:** `.` (leave empty or set to root)
- **Environment:** `Python 3`
- **Build Command:**
  ```bash
  pip install -r requirements.txt
  ```
- **Start Command:**
  ```bash
  uvicorn agent.api:app --host 0.0.0.0 --port $PORT
  ```
- **Health Check Path:** `/api/health`

#### Required Environment Variables on Render
Set these in your Render Web Service **Environment** tab:
| Variable | Value | Notes |
| :--- | :--- | :--- |
| `FALKORDB_HOST` | `xxxx.falkordb.cloud` | Your FalkorDB Cloud endpoint |
| `FALKORDB_PORT` | `xxxx` | Port (e.g. 12345) |
| `FALKORDB_PASSWORD` | `your_falkordb_password` | FalkorDB database password |
| `FALKORDB_GRAPH` | `ALL_GRAPHS` | Default graph name |
| `NVIDIA_API_KEY` | `nvapi-xxxx` | NVIDIA NIM API key for LLM |
| `LLM_PROVIDER` | `nvidia` | Or `mock` for offline testing |
| `GRAPHOS_SECURE_COOKIE` | `true` | Enables secure cross-site cookies |
| `FRONTEND_URL` | `https://your-app.vercel.app` | Your Vercel frontend URL for CORS |

Once deployed, Render gives you a live URL, e.g.: `https://graphos-backend.onrender.com`.

---

### 2. Frontend Deployment on Vercel (`frontend` Directory)

#### Vercel CLI (Fastest)
From your terminal:
```bash
cd frontend
npx vercel
```
Or for production:
```bash
cd frontend
npx vercel --prod
```

#### Vercel Web Dashboard
1. Go to [vercel.com](https://vercel.com) and click **Add New Project**.
2. Select your GitHub repository (`graphhacks`).
3. In **Project Configuration**:
   - **Root Directory:** Click Edit and select `frontend`
   - **Framework Preset:** `Next.js` (detected automatically)
   - **Build Command:** `npm run build`
   - **Output Directory:** `.next`
4. In **Environment Variables**:
   - Add: `NEXT_PUBLIC_API_URL`
   - Value: Your Render backend URL (e.g. `https://graphos-backend.onrender.com`)
5. Click **Deploy**.

---

## 🛡️ Security & Read-Only Guardrails

- All database access is strictly mediated by the GraphOS MCP server.
- The web frontend **never** connects directly to FalkorDB; credentials stay entirely server-side.
- Application guardrails enforce read-only Cypher operations, rejecting any mutation (`CREATE`, `MERGE`, `DELETE`, `DROP`).
- Cross-origin authentication supports both secure `SameSite=None; Secure` cookies and `Authorization: Bearer <token>` headers for Safari and third-party cookie compatibility.

