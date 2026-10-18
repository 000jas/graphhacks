# 🚀 GraphOS Quick Start & Execution Guide (`start.md`)

This guide explains how to run each component of **GraphOS** — including the full web application, multi-language code parser, interactive terminal agent, analytics dashboard, and Docker containers.

---

## ⚡ 1-Command All-In-One Runner (Fastest)

Launch both the **FastAPI Backend** and the **Next.js Frontend** simultaneously with automatic health checks and clean shutdown:

```bash
./start.sh
```

- **Frontend:** [http://localhost:3000](http://localhost:3000)
- **Backend API:** [http://localhost:8000](http://localhost:8000)
- **API Docs (Swagger):** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Shutdown:** Press `Ctrl+C` in the terminal to terminate all services cleanly.

---

## 📋 Initial Setup (First Time Only)

### 1. Python Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

### 2. Frontend Dependencies
```bash
cd frontend
npm install
cd ..
```

### 3. Environment Variables (`.env`)
Make sure `.env` is configured with your FalkorDB Cloud credentials:
```dotenv
# FalkorDB Cloud Connection
FALKORDB_HOST=r-6jissuruar.instance-27k50cn68.hc-7up0crkyn.ap-south-1.aws.f2e0a955bb84.cloud
FALKORDB_PORT=54637
FALKORDB_USERNAME=falkordb
FALKORDB_PASSWORD=your_falkordb_password
FALKORDB_SSL=false
GRAPHOS_GRAPH_NAME=graphos_dev

# LLM Provider (NVIDIA, OpenAI, Anthropic, Ollama, or Mock)
LLM_PROVIDER=nvidia
LLM_MODEL=openai/gpt-oss-20b
LLM_API_BASE=https://integrate.api.nvidia.com/v1
NVIDIA_API_KEY=nvapi-your-nvidia-api-key
```

---

## 🌐 Running the Web Application Manually

If you prefer running the backend and frontend in separate terminals:

### Terminal 1: FastAPI Backend
```bash
source .venv/bin/activate
uvicorn agent.api:app --host 0.0.0.0 --port 8000 --reload
```
*Verify health:*
```bash
curl http://localhost:8000/api/health
```

### Terminal 2: Next.js Frontend
```bash
cd frontend
npm run dev
```
*Open [http://localhost:3000](http://localhost:3000) in your browser.*

---

## 🔍 Running the Multi-Language Code Parser & Ingestion

GraphOS includes a **Tree-sitter AST Code Parser** (`graphagent`) supporting 8 languages: **Python, JavaScript, TypeScript/TSX, Java, Go, C/C++, Rust, and PHP**.

### Method 1: Terminal CLI (2-Step Workflow)

From the project root directory:

#### **Step 1 — Parse Repository to AST Graph JSON**
```bash
# Parse current repository
python3 run.py .

# Parse any external codebase
python3 run.py /path/to/any/repo

# Test against the included 8-language sample repository
python3 run.py agent/codeparser/tests/sample_repo
```
*Output: Generates `output.json` with extracted nodes (`File`, `Class`, `Function`, `Method`, `Interface`, `Struct`) and relationships (`CONTAINS`, `CALLS`, `IMPORTS`, `INHERITS`, `IMPLEMENTS`).*

#### **Step 2 — Push into FalkorDB Cloud**
```bash
# Push into default graph
python3 run.py save-db

# Push into a specific graph tenant (e.g., graphos_dev)
python3 run.py save-db output.json --graph graphos_dev

# Or use the standalone script
python3 save_to_db.py output.json --graph graphos_dev
```

---

### Method 2: Web UI Drag & Drop Ingestion

1. Open **[http://localhost:3000](http://localhost:3000)**.
2. Click **Import Dataset** in the top navigation bar.
3. In the **Code AST JSON** tab:
   - Drag & drop your generated `output.json` file.
   - Enter your target graph name (e.g. `graphos_dev`).
4. Click **Ingest Code Graph**.
5. The nodes and relationships are ingested into FalkorDB and immediately visualized in the interactive graph explorer!

---

## 💻 Running the Terminal CLI Agent (`graphos`)

GraphOS provides a colorized, interactive terminal agent with live MCP tool execution:

```bash
# Make executable (first time only)
chmod +x graphos

# 1. Interactive REPL Mode
./graphos
# or: make run

# 2. One-Shot Query (Human-readable report)
./graphos ask "Why is the payments release delayed?"

# 3. One-Shot Query (JSON output for CI/CD automation)
./graphos ask "Why is the payments release delayed?" --json

# 4. System Diagnostics & Health Check
./graphos doctor

# 5. Live Status Report
./graphos status

# 6. List Discovered MCP Tools
./graphos tools
```

---

## 📊 Running the Streamlit Graph Analytics Dashboard

To inspect topological graph metrics, degree centrality, PageRank, and community clusters:

```bash
make dashboard
# or: streamlit run dashboard/app.py
```
*Open [http://localhost:8501](http://localhost:8501) in your browser.*

---

## 🐳 Running with Docker

GraphOS is fully containerized with `Dockerfile` and `docker-compose.yml`:

```bash
# Build Docker image
make docker-build

# Run interactive terminal agent inside Docker
make docker-run

# Run one-shot query inside Docker
make docker-ask Q="Why is the payments release delayed?"

# Run Streamlit dashboard in Docker (http://localhost:8501)
make docker-dashboard

# Stop and clean up containers
make docker-down
```

---

## 🧪 Running Automated Tests

```bash
# Run core GraphOS agent & MCP test suite (42 tests)
make test
# or: pytest tests

# Run multi-language Tree-sitter code parser test suite (19 tests)
pytest agent/codeparser/tests

# Validate Next.js frontend production build
cd frontend && npm run build
```

---

## 🛠️ Summary Cheat Sheet

| Task | Command |
| :--- | :--- |
| **Start Web App (Frontend + Backend)** | `./start.sh` |
| **Start Backend only** | `uvicorn agent.api:app --host 0.0.0.0 --port 8000 --reload` |
| **Start Frontend only** | `cd frontend && npm run dev` |
| **Parse Code Repository** | `python3 run.py <path_to_repo>` |
| **Save Code AST to FalkorDB** | `python3 run.py save-db output.json --graph graphos_dev` |
| **Launch Terminal Agent** | `./graphos` or `make run` |
| **One-Shot Agent Query** | `./graphos ask "<question>"` |
| **System Diagnostics** | `./graphos doctor` |
| **Launch Streamlit Dashboard** | `make dashboard` |
| **Run Core Tests** | `make test` |
| **Run Parser Tests** | `pytest agent/codeparser/tests` |
