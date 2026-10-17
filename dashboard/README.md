# 🌌 GraphOS Visualization Dashboard

The GraphOS Dashboard is an interactive Streamlit application for visual graph exploration, blast-radius topology inspection, policy evaluation audit, and decision memory history.

---

## 🚀 Running the Dashboard

Launch the dashboard using the local virtual environment:

```bash
# Using Makefile
make dashboard

# Or directly with Python
agent/venv/bin/python -m streamlit run dashboard/app.py
```

The dashboard will open automatically in your browser at `http://localhost:8501`.

---

## 📊 Features

1. **Graph Overview & Topology**:
   - Live entity distribution charts (Services, Repositories, Pull Requests, Tasks, Persons).
   - Relationship type connectivity matrix.
   - Graph density and degree metrics.
2. **Blast Radius Visualizer**:
   - Interactive 2D network graph for upstream and downstream dependency tracing.
   - Simulation of proposed entity failures and architectural changes.
3. **Governance & Policy Audits**:
   - Inspect compliance rules and prerequisite verification status.
4. **Historical Decision Memory**:
   - Audit trail of historical actions, proposed counterfactual plans, and recorded investigation outcomes.
