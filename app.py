# app.py
import streamlit as st
import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt

from network_flow import (
    edmonds_karp_steps,
    dinic_apply,
    push_relabel_apply,
    extract_flow_paths,
    min_cut_report,
)

st.set_page_config(page_title="Pune Water Network", layout="wide")

st.title("💧 Pune Water Network – Max Flow Simulator")

# Sidebar
st.sidebar.header("Simulation Settings")

scenario = st.sidebar.selectbox("Select Scenario", ["Normal Operation", "Pipe Failure"])
failure_pipe = st.sidebar.text_input("Pipe Failure (format: u,v)")

leakage = st.sidebar.slider("Leakage (%)", 0, 30, 10)

algo_choice = st.sidebar.selectbox(
    "Select Algorithm",
    ["Edmonds-Karp", "Dinic", "Push-Relabel"]
)

debug_mode = st.sidebar.checkbox("Debug output", value=True)

run = st.sidebar.button("Run Simulation")

# Load Graph from CSV
edges_df = pd.read_csv("data/edges.csv")

G = nx.DiGraph()

for _, row in edges_df.iterrows():
    # supports both comma or tab separated pasted files, but CSV reading already handled
    u, v, cap = row["u"], row["v"], row["capacity_mld"]

    # apply leakage
    cap = cap * (1 - leakage / 100)

    # pipe failure
    if scenario == "Pipe Failure" and f"{u},{v}" == failure_pipe:
        cap = 0

    # store capacity and initialize flow attribute
    G.add_edge(u, v, capacity=cap, flow=0)

# Run Simulation
if run:

    st.subheader("Results")

    # work on a fresh copy each run
    Gcopy = G.copy()
    S, T = "S", "T"

    # algorithm selection
    if algo_choice == "Edmonds-Karp":
        steps, max_flow = edmonds_karp_steps(Gcopy, S, T)
        st.success(f"Max Flow = {max_flow:.2f} MLD (Edmonds-Karp)")

    elif algo_choice == "Dinic":
        max_flow = dinic_apply(Gcopy, S, T)
        st.success(f"Max Flow = {max_flow:.2f} MLD (Dinic)")

    elif algo_choice == "Push-Relabel":
        max_flow = push_relabel_apply(Gcopy, S, T)
        st.success(f"Max Flow = {max_flow:.2f} MLD (Push-Relabel)")

    # debug outputs to help trace why no paths are found
    if debug_mode:
        st.markdown("### Debug info")
        # net positive inflow into T
        try:
            preds_T = list(Gcopy.predecessors(T))
        except Exception:
            preds_T = []
        inflow_T = 0.0
        for u in preds_T:
            f = Gcopy[u][T].get("flow", 0)
            if f > 0:
                inflow_T += f
        # net positive outflow from S
        succs_S = list(Gcopy.successors(S))
        outflow_S = 0.0
        for v in succs_S:
            f = Gcopy[S][v].get("flow", 0)
            if f > 0:
                outflow_S += f

        st.write("Number of predecessors of T:", len(preds_T))
        st.write("Net positive inflow into T (sum of positive flows on incoming edges):", f"{inflow_T:.2f}")
        st.write("Net positive outflow from S (sum of positive flows on outgoing edges):", f"{outflow_S:.2f}")

        # show first 30 edges with signed flow and capacity
        st.markdown("First 30 edges, showing signed flow and capacity")
        rows = []
        i = 0
        for u, v, data in Gcopy.edges(data=True):
            if i >= 30:
                break
            rows.append([u, v, data.get("flow", 0), data.get("capacity", 0)])
            i += 1
        df_edges = pd.DataFrame(rows, columns=["u", "v", "flow (signed)", "capacity"])
        st.dataframe(df_edges, use_container_width=True)

        # list nodes with positive excess like intermediate accumulation,
        # we approximate by nodes with positive sum(outgoing positive flow) - sum(incoming positive flow)
        st.markdown("Nodes with positive forward-outflow but no path to T may indicate stuck flow")
        node_rows = []
        for n in Gcopy.nodes():
            pos_out = sum(max(0, Gcopy[n][w].get("flow", 0)) for w in Gcopy.successors(n))
            pos_in = sum(max(0, Gcopy[p][n].get("flow", 0)) for p in Gcopy.predecessors(n))
            net_pos = pos_out - pos_in
            if abs(net_pos) > 1e-6:
                node_rows.append([n, round(pos_in, 3), round(pos_out, 3), round(net_pos, 3)])
        node_df = pd.DataFrame(node_rows, columns=["node", "pos_in", "pos_out", "pos_out - pos_in"])
        # show top 20 imbalanced nodes
        if not node_df.empty:
            node_df = node_df.sort_values(by="pos_out - pos_in", ascending=False).head(20)
            st.dataframe(node_df, use_container_width=True)
        else:
            st.write("No nodes with significant forward flow imbalance found")

    # Flow Visualization
    st.subheader("Flow Distribution")

    pos = nx.kamada_kawai_layout(Gcopy)
    fig, ax = plt.subplots(figsize=(10, 7))

    widths = []
    colors = []

    # Visualize using positive forward flow only
    for u, v, data in Gcopy.edges(data=True):
        flow = max(0, data.get("flow", 0))
        cap = data.get("capacity", 0)
        ratio = flow / cap if cap > 0 else 0
        widths.append(1 + 6 * ratio)
        if ratio == 0:
            colors.append("gray")
        elif ratio < 0.5:
            colors.append("skyblue")
        else:
            colors.append("blue")

    nx.draw(
        Gcopy,
        pos,
        with_labels=True,
        node_size=850,
        node_color="lightblue",
        width=widths,
        edge_color=colors,
        arrows=True,
        ax=ax
    )

    ax.set_title("Final Flow Distribution (Edge thickness = Flow)")
    ax.axis("off")
    st.pyplot(fig)

    # Flow Paths
    st.subheader("Flow Paths (S → T)")

    paths = extract_flow_paths(Gcopy.copy(), S, T)

    if paths:
        df_paths = pd.DataFrame([
            (" → ".join(p), f) for p, f in paths
        ], columns=["Path", "Flow (MLD)"])
        st.dataframe(df_paths, use_container_width=True)
    else:
        # when no path found, provide hint using debug numbers
        if debug_mode:
            st.info("No flow paths found, debug shows either zero inflow to T, or forward flows are stuck upstream.")
            st.info("Check the 'Net positive inflow into T' and the 'First 30 edges' table above to find where flow accumulates.")
        else:
            st.info("No flow paths found.")

    # Min-Cut Report
    st.subheader("Min-Cut Report")

    cut_edges = min_cut_report(Gcopy, S)

    if cut_edges:
        df_cut = pd.DataFrame(cut_edges, columns=["From", "To", "Capacity"])
        st.dataframe(df_cut, use_container_width=True)
    else:
        st.success("No bottlenecks detected.")

else:
    st.info("Adjust settings and click Run Simulation.")
