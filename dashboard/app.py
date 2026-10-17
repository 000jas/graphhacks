import json
import os
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT_DIR = Path(__file__).resolve().parent.parent
MCP_SERVER_DIR = ROOT_DIR / "mcp_server"

if str(MCP_SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_SERVER_DIR))

from server import (
    analyze_graph_impact,
    check_policy,
    execute_approved_action,
    find_shortest_evidence_path,
    get_entity_profile,
    propose_action,
    record_outcome,
    retrieve_source_documents,
    run_graph_algorithm,
    search_connected_entities,
    simulate_action,
    traverse_relationships,
)
from db import get_graph_stats, execute_ro_query
from config import settings

st.set_page_config(
    page_title="GraphOS — Evidence-Bound Graph Intelligence",
    page_icon="🌌",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.7), rgba(15, 23, 42, 0.8));
        padding: 1.2rem;
        border-radius: 12px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        margin-bottom: 1rem;
    }
    .badge-critical { background-color: #ef4444; color: white; padding: 4px 8px; border-radius: 6px; font-weight: bold; }
    .badge-high { background-color: #f97316; color: white; padding: 4px 8px; border-radius: 6px; font-weight: bold; }
    .badge-medium { background-color: #eab308; color: black; padding: 4px 8px; border-radius: 6px; font-weight: bold; }
    .badge-low { background-color: #22c55e; color: white; padding: 4px 8px; border-radius: 6px; font-weight: bold; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] {
        padding: 8px 16px;
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)


def load_stats():
    try:
        return get_graph_stats()
    except Exception as e:
        return {"error": str(e)}


stats = load_stats()

with st.sidebar:
    st.title("🌌 GraphOS")
    st.caption("Evidence-Bound MCP Server Dashboard")
    st.markdown("---")

    if "error" in stats:
        st.error(f"FalkorDB Connection Error: {stats['error']}")
    else:
        st.success("🟢 FalkorDB Cloud Connected")
        st.write(f"**Host**: `{settings.host[:25]}...`")
        st.write(f"**Port**: `{settings.port}`")
        st.write(f"**Graph**: `{stats['graph_name']}`")
        col_s1, col_s2 = st.columns(2)
        col_s1.metric("Entities", stats["total_entities"])
        col_s2.metric("Relationships", stats["total_relationships"])

    st.markdown("---")
    view = st.radio(
        "Navigation",
        [
            "🔍 Entity Explorer",
            "🔗 Shortest Evidence Path",
            "📊 Graph Algorithms",
            "💥 Blast Radius & Impact",
            "🛡️ Policy & Counterfactual Simulator",
            "🚀 Action Lifecycle & Execution",
            "🧠 Organizational Memory",
            "⚡ Direct MCP Tool Console",
        ],
    )

    st.markdown("---")
    st.caption("FalkorDB Cloud AWS Cluster • MCP v2.3.0")

if view == "🔍 Entity Explorer":
    st.header("🔍 Entity Explorer & Search")
    st.markdown("Query the cloud graph for entities, inspect incoming/outgoing edges, and review source-backed properties.")

    col1, col2 = st.columns([3, 1])
    with col1:
        search_query = st.text_input("Search entity name or ID", value="payments")
    with col2:
        kinds = ["All"] + (stats.get("entity_kinds", []) if "error" not in stats else [])
        selected_kind = st.selectbox("Filter by Kind", kinds)

    kind_param = "" if selected_kind == "All" else selected_kind
    if st.button("Search Entities", type="primary") or search_query:
        raw_res = search_connected_entities(query=search_query, kind=kind_param, limit=15)
        res = json.loads(raw_res)

        st.subheader(f"Results ({res['count']} found)")
        if res["entities"]:
            df = pd.DataFrame(res["entities"])
            st.dataframe(df, use_container_width=True)

            selected_entity_id = st.selectbox("Inspect Full Entity Profile", [e["id"] for e in res["entities"]])
            if selected_entity_id:
                prof_raw = get_entity_profile(selected_entity_id)
                prof = json.loads(prof_raw)

                if prof.get("found"):
                    e = prof["entity"]
                    st.markdown(f"### 🏷️ {e['name']} (`{e['id']}`)")
                    st.write(f"**Kind:** `{e['kind']}` | **Status:** `{e.get('properties', {}).get('status', 'active')}`")

                    col_p1, col_p2 = st.columns(2)
                    with col_p1:
                        st.markdown(f"**Outgoing Relationships ({len(prof['outgoing_relationships'])})**")
                        if prof["outgoing_relationships"]:
                            out_data = [
                                {"Type": r["type"], "Target": r["target"]["name"], "Target Kind": r["target"]["kind"]}
                                for r in prof["outgoing_relationships"]
                            ]
                            st.dataframe(pd.DataFrame(out_data), use_container_width=True)
                        else:
                            st.info("No outgoing relationships.")

                    with col_p2:
                        st.markdown(f"**Incoming Relationships ({len(prof['incoming_relationships'])})**")
                        if prof["incoming_relationships"]:
                            in_data = [
                                {"Type": r["type"], "Source": r["source"]["name"], "Source Kind": r["source"]["kind"]}
                                for r in prof["incoming_relationships"]
                            ]
                            st.dataframe(pd.DataFrame(in_data), use_container_width=True)
                        else:
                            st.info("No incoming relationships.")

                    with st.expander("Raw Entity Properties"):
                        st.json(e["properties"])

elif view == "🔗 Shortest Evidence Path":
    st.header("🔗 Shortest Evidence Path Finder")
    st.markdown("Trace verifiable connection chains across multiple hops between two entities with edge provenance and confidence.")

    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        source_id = st.text_input("Source Entity ID", value="release-payments-2026-10")
    with col2:
        target_id = st.text_input("Target Entity ID", value="event-liam-leave")
    with col3:
        max_hops = st.slider("Max Depth", 1, 8, 6)

    if st.button("Trace Evidence Path", type="primary"):
        with st.spinner("Traversing graph..."):
            raw_path = find_shortest_evidence_path(source_id=source_id, target_id=target_id, max_depth=max_hops)
            res = json.loads(raw_path)

        if not res.get("found"):
            st.warning(f"No path found: {res.get('message')}")
        else:
            st.success(f"✓ Found verifiable path of {res['hop_count']} hops!")

            nodes = res["path_nodes"]
            edges = res["path_edges"]

            steps = []
            for i in range(len(edges)):
                u = nodes[i]
                v = nodes[i + 1]
                e = edges[i]
                steps.append(f"**{u['name']}** *({u['kind']})* &nbsp; `—[{e['type']}]→` &nbsp; **{v['name']}** *({v['kind']})*")

            for idx, step in enumerate(steps, 1):
                st.markdown(f"> **Step {idx}:** {step}")

            with st.expander("Detailed Evidence & Timestamps"):
                st.json(res)

elif view == "📊 Graph Algorithms":
    st.header("📊 Graph Algorithms & Structural Analysis")
    st.markdown("Run topological centrality, deadlock detection, and community algorithms over FalkorDB Cloud.")

    algo = st.selectbox(
        "Select Algorithm",
        ["PageRank", "Degree Centrality", "Cycle Detection", "Connected Components"],
    )

    col1, col2 = st.columns(2)
    with col1:
        top_k = st.slider("Top K Entities", 3, 20, 10)
    with col2:
        max_iter = st.slider("Max Iterations", 5, 50, 25)

    if st.button("Run Algorithm", type="primary"):
        with st.spinner(f"Computing {algo}..."):
            algo_key = algo.lower().replace(" ", "_")
            raw_res = run_graph_algorithm(algorithm=algo_key, top_k=top_k, max_iterations=max_iter)
            res = json.loads(raw_res)

        st.info(f"**Interpretation:** {res.get('interpretation')}")

        if "ranked_entities" in res:
            df = pd.DataFrame(res["ranked_entities"])
            score_col = "score" if "score" in df.columns else "total_degree"

            col_chart, col_tbl = st.columns([3, 2])
            with col_chart:
                fig = px.bar(
                    df,
                    x=score_col,
                    y="name",
                    orientation="h",
                    color="kind",
                    title=f"{algo} Rankings",
                )
                fig.update_layout(yaxis={"autorange": "reversed"})
                st.plotly_chart(fig, use_container_width=True)
            with col_tbl:
                st.dataframe(df, use_container_width=True)

        elif "cycles" in res:
            st.metric("Cycles / Circular Deadlocks Found", res["cycles_found"])
            if res["cycles"]:
                for idx, c in enumerate(res["cycles"], 1):
                    chain = " ➔ ".join([node["name"] for node in c])
                    st.warning(f"Cycle {idx}: {chain}")

        elif "components" in res:
            st.metric("Total Weakly Connected Clusters", res["total_components"])
            for comp in res["components"]:
                st.write(f"**Cluster Root (`{comp['component_root']}`)** — {comp['size']} entities")

elif view == "💥 Blast Radius & Impact":
    st.header("💥 Blast Radius & Impact Analysis")
    st.markdown("Evaluate downstream consequences, affected services, and critical dependency chains for an entity.")

    col1, col2 = st.columns([3, 1])
    with col1:
        impact_root = st.text_input("Root Entity ID", value="task-code-review-482")
    with col2:
        direction = st.selectbox("Direction", ["downstream", "upstream", "both"])

    if st.button("Compute Blast Radius", type="primary") or impact_root:
        raw_imp = analyze_graph_impact(root_entity_id=impact_root, direction=direction, max_depth=4)
        imp = json.loads(raw_imp)

        if not imp.get("found"):
            st.warning(imp.get("message"))
        else:
            br = imp["blast_radius"]
            sev = br["severity"]
            badge_class = f"badge-{sev.lower()}"

            st.markdown(f"### Severity: <span class='{badge_class}'>{sev}</span> (Score: {br['score']})", unsafe_allow_html=True)
            st.markdown(f"*{imp['summary']}*")

            col_m1, col_m2, col_m3 = st.columns(3)
            col_m1.metric("Direct Dependencies", br["direct_dependencies_count"])
            col_m2.metric("Total Transitive Impacted", br["total_transitive_impacted_count"])
            col_m3.metric("Critical Assets Impacted", br["critical_assets_impacted"])

            if imp.get("impact_by_category"):
                cats = {k: len(v) for k, v in imp["impact_by_category"].items()}
                cat_df = pd.DataFrame(list(cats.items()), columns=["Asset Category", "Impacted Count"])
                fig_cat = px.pie(cat_df, names="Asset Category", values="Impacted Count", title="Impact by Entity Kind")
                st.plotly_chart(fig_cat, use_container_width=True)

            with st.expander("Critical Impact Chains"):
                for c in imp.get("critical_impact_chains", []):
                    st.write(f"**{c['target_entity']['name']}** ({c['hops']} hops): {' ➔ '.join(c['chain'])}")

elif view == "🛡️ Policy & Counterfactual Simulator":
    st.header("🛡️ Policy Engine & Counterfactual Planning")
    st.markdown("Dry-run proposed interventions against graph policies without modifying state.")

    action = st.selectbox(
        "Candidate Action",
        ["reassign_review", "bypass_review", "approve_production_release", "deprecate_dependency"],
    )

    target_id = st.text_input("Target Entity ID", value="task-code-review-482")

    params = {}
    if action == "reassign_review":
        assignee_id = st.text_input("Proposed Assignee ID", value="person-ravi-kulkarni")
        params["assignee_id"] = assignee_id

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Check Policy Verdict", type="secondary"):
            pol_raw = check_policy(action=action, target_id=target_id, params=params)
            pol = json.loads(pol_raw)

            verdict = pol["verdict"]
            if pol.get("allowed"):
                st.success(f"✓ Policy Verdict: {verdict}")
            else:
                st.error(f"✗ Policy Verdict: {verdict}")
            st.write(f"**Reason:** {pol.get('reason')}")
            if pol.get("violated_rules"):
                st.markdown("**Violated Rules:**")
                for r in pol["violated_rules"]:
                    st.markdown(f"- ❌ {r}")

    with col2:
        if st.button("Simulate Intervention (Counterfactual)", type="primary"):
            sim_raw = simulate_action(action=action, target_id=target_id, params=params)
            sim = json.loads(sim_raw)

            st.markdown(f"**Counterfactual Verdict:** {sim.get('counterfactual_verdict')}")
            risk = sim["risk_assessment"]["risk_level"]
            st.metric("Projected Risk Level", risk)
            st.write(f"**Reversible:** `{sim['risk_assessment']['is_reversible']}`")

            if sim.get("projected_unblocked_entities"):
                st.markdown("**Entities Unblocked by this Action:**")
                for u in sim["projected_unblocked_entities"]:
                    st.write(f"• **{u['name']}** ({u['kind']}): *{u['projected_effect']}*")

            if sim.get("recommended_mitigations"):
                st.markdown("**Recommended Operational Mitigations:**")
                for m in sim["recommended_mitigations"]:
                    st.markdown(f"- 🛡️ {m}")

elif view == "🚀 Action Lifecycle & Execution":
    st.header("🚀 Action Lifecycle & Controlled Execution")
    st.markdown("Propose an action bound to evidence, verify approval tokens, and execute with immutable audit logs.")

    st.subheader("Step 1: Propose Action")
    prop_action_type = st.selectbox("Action", ["reassign_review", "approve_production_release"])
    prop_target = st.text_input("Target ID", value="task-code-review-482")
    prop_assignee = st.text_input("Assignee ID (if reassign)", value="person-ravi-kulkarni")
    prop_rationale = st.text_area(
        "Evidence Rationale",
        value="Liam Patel is on leave until Oct 20. Reassign to Ravi Kulkarni to unblock PR #482 and payments release.",
    )

    if st.button("Submit Proposal", type="primary"):
        prop_res = propose_action(
            action=prop_action_type,
            target_id=prop_target,
            rationale=prop_rationale,
            params={"assignee_id": prop_assignee},
            evidence_ids=["event-liam-leave"],
        )
        p = json.loads(prop_res)
        st.session_state["last_proposal"] = p
        st.success(f"Proposal Created: `{p['proposal_id']}`")
        st.info(f"Approval Token Issued: `{p['approval_token']}`")

    st.markdown("---")
    st.subheader("Step 2: Execute Approved Action")
    last_prop = st.session_state.get("last_proposal", {})
    exec_prop_id = st.text_input("Proposal ID", value=last_prop.get("proposal_id", ""))
    exec_token = st.text_input("Approval Token", value=last_prop.get("approval_token", ""))

    if st.button("Execute Action with Token", type="primary"):
        if not exec_prop_id or not exec_token:
            st.error("Please supply both Proposal ID and Approval Token.")
        else:
            exec_raw = execute_approved_action(proposal_id=exec_prop_id, approval_token=exec_token)
            ex = json.loads(exec_raw)

            if ex.get("executed"):
                st.success(f"✓ Execution Succeeded! Status: {ex['status']}")
                st.write(f"**Execution ID:** `{ex['execution_id']}`")
                st.write(f"**Audit Trail Node:** `{ex['audit_trail_id']}`")
            else:
                st.error(f"✗ Execution Blocked: {ex.get('message')}")

elif view == "🧠 Organizational Memory":
    st.header("🧠 Durable Organizational Memory")
    st.markdown("Inspect historical findings and record new verified outcomes linked back to graph entities.")

    memory_rows = execute_ro_query(
        """
        MATCH (m:Entity {kind: 'MemoryRecord'})
        RETURN m.id, m.name, m.finding_id, m.summary, m.outcome_status, m.recorded_at
        ORDER BY m.recorded_at DESC
        LIMIT 10
        """
    )

    st.subheader(f"Historical Decision Memory ({len(memory_rows)} records)")
    if memory_rows:
        mem_df = pd.DataFrame(
            memory_rows,
            columns=["Memory ID", "Name", "Finding ID", "Summary", "Outcome Status", "Recorded At"],
        )
        st.dataframe(mem_df, use_container_width=True)
    else:
        st.info("No memory records found.")

    st.markdown("---")
    st.subheader("Record New Memory Entry")
    col1, col2 = st.columns(2)
    with col1:
        f_id = st.text_input("Finding ID", value="INCIDENT-PAYMENTS-RESOLVED")
        f_targets = st.text_input("Target Entity IDs (comma separated)", value="task-code-review-482, pr-482")
    with col2:
        f_status = st.selectbox("Outcome Status", ["RESOLVED", "VERIFIED_IN_PROD", "PARTIALLY_RESOLVED"])

    f_summary = st.text_area("Resolution Summary", value="Urgent bottleneck resolved via staff engineer reassignment.")
    f_variance = st.text_input("Variance from Simulated Plan", value="Zero variance; merged cleanly.")

    if st.button("Record to Memory Graph", type="primary"):
        target_list = [t.strip() for t in f_targets.split(",") if t.strip()]
        rec_raw = record_outcome(
            finding_id=f_id,
            target_entity_ids=target_list,
            summary=f_summary,
            outcome_status=f_status,
            variance_analysis=f_variance,
        )
        rec = json.loads(rec_raw)
        st.success(f"✓ Saved to Memory: `{rec['memory_id']}` (Linked {len(rec['target_entities_linked'])} entities)")

elif view == "⚡ Direct MCP Tool Console":
    st.header("⚡ Direct MCP Tool Console")
    st.markdown("Test raw MCP tool invocations with custom JSON parameters and inspect response payloads.")

    tools = [
        "search_connected_entities",
        "get_entity_profile",
        "traverse_relationships",
        "find_shortest_evidence_path",
        "run_graph_algorithm",
        "analyze_graph_impact",
        "retrieve_source_documents",
        "check_policy",
        "simulate_action",
        "propose_action",
        "execute_approved_action",
        "record_outcome",
    ]

    selected_tool = st.selectbox("Select MCP Tool to Invoke", tools)

    default_payloads = {
        "search_connected_entities": {"query": "payments", "limit": 5, "kind": ""},
        "get_entity_profile": {"entity_id": "release-payments-2026-10"},
        "traverse_relationships": {"entity_id": "release-payments-2026-10", "relationship_types": ["BLOCKED_BY", "DEPLOYS"], "depth": 2, "limit": 10},
        "find_shortest_evidence_path": {"source_id": "release-payments-2026-10", "target_id": "event-liam-leave", "max_depth": 8},
        "run_graph_algorithm": {"algorithm": "pagerank", "top_k": 5},
        "analyze_graph_impact": {"root_entity_id": "task-code-review-482", "direction": "downstream", "max_depth": 3},
        "retrieve_source_documents": {"entity_ids": ["service-payment-api", "policy-third-party-review"]},
        "check_policy": {"action": "reassign_review", "target_id": "task-code-review-482", "assignee_id": "person-ravi-kulkarni"},
        "simulate_action": {"action": "reassign_review", "target_id": "task-code-review-482", "params": {"assignee_id": "person-ravi-kulkarni"}},
        "propose_action": {"action": "reassign_review", "target_id": "task-code-review-482", "rationale": "Direct tool test", "evidence_ids": ["event-liam-leave"]},
        "execute_approved_action": {"proposal_id": "prop-test", "approval_token": "token-test"},
        "record_outcome": {"finding_id": "TEST-CONSOLE", "target_entity_ids": ["service-payment-api"], "summary": "Console test", "outcome_status": "RESOLVED"},
    }

    payload_str = st.text_area("Input Arguments (JSON)", value=json.dumps(default_payloads.get(selected_tool, {}), indent=2), height=180)

    if st.button("Invoke MCP Tool", type="primary"):
        try:
            kwargs = json.loads(payload_str)
            tool_fn = globals()[selected_tool]
            raw_output = tool_fn(**kwargs)
            parsed_output = json.loads(raw_output)

            st.markdown("### Output Response")
            st.json(parsed_output)
        except Exception as e:
            st.error(f"Tool invocation error: {e}")
