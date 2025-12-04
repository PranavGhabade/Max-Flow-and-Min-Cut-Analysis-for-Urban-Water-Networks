# network_flow.py
import networkx as nx
from collections import deque


# Helper: ensure reverse edges exist

def prepare_graph(G):
    for u, v in list(G.edges()):
        G[u][v].setdefault('flow', 0)
        if not G.has_edge(v, u):
            G.add_edge(v, u, capacity=0, flow=0)
        else:
            G[v][u].setdefault('flow', 0)


# Edmonds–Karp

def bfs(G, s, t, parent):
    visited = {s}
    q = deque([s])
    while q:
        u = q.popleft()
        for v in G[u]:
            cap = G[u][v]['capacity']
            flow = G[u][v]['flow']
            if v not in visited and cap - flow > 0:
                visited.add(v)
                parent[v] = u
                if v == t:
                    return True
                q.append(v)
    return False


def edmonds_karp_steps(G, s, t):
    prepare_graph(G)
    for u, v in G.edges():
        G[u][v]['flow'] = 0

    parent = {}
    max_flow = 0
    steps = []

    while bfs(G, s, t, parent):
        path_flow = float('inf')
        v = t
        path = []
        while v != s:
            u = parent[v]
            path_flow = min(path_flow, G[u][v]['capacity'] - G[u][v]['flow'])
            path.insert(0, (u, v))
            v = u

        for u, v in path:
            G[u][v]['flow'] += path_flow
            G[v][u]['flow'] -= path_flow

        max_flow += path_flow
        steps.append((path, path_flow, max_flow))
        parent = {}

    return steps, max_flow



# Dinic

def dinic_apply(G, s, t):
    prepare_graph(G)

    def bfs_level():
        level = {n: -1 for n in G.nodes()}
        q = deque([s])
        level[s] = 0
        while q:
            u = q.popleft()
            for v in G[u]:
                if level[v] < 0 and G[u][v]['capacity'] - G[u][v]['flow'] > 0:
                    level[v] = level[u] + 1
                    q.append(v)
        return level

    def dfs(u, pushed, t, level, it):
        if u == t:
            return pushed

        while it[u] < len(G[u]):
            v = list(G[u])[it[u]]
            it[u] += 1

            if level[v] == level[u] + 1 and G[u][v]['capacity'] - G[u][v]['flow'] > 0:
                flow = dfs(v, min(pushed, G[u][v]['capacity'] - G[u][v]['flow']), t, level, it)
                if flow > 0:
                    G[u][v]['flow'] += flow
                    G[v][u]['flow'] -= flow
                    return flow
        return 0

    max_flow = 0
    while True:
        level = bfs_level()
        if level[t] < 0:
            break
        it = {n: 0 for n in G.nodes()}
        while True:
            pushed = dfs(s, float('inf'), t, level, it)
            if pushed <= 0:
                break
            max_flow += pushed

    return max_flow



# PUSH–RELABEL 
def push_relabel_apply(G, s, t):
    prepare_graph(G)

    n = len(G.nodes())
    height = {u: 0 for u in G.nodes()}
    excess = {u: 0 for u in G.nodes()}

    height[s] = n


    # Saturate outgoing edges from source

    for v in G[s]:
        cap = G[s][v]['capacity']
        G[s][v]['flow'] = cap
        G[v][s]['flow'] -= cap
        excess[v] += cap

    # Active nodes (except s and t)
    active = [u for u in G.nodes() if u not in (s, t) and excess[u] > 0]

    def push(u, v):
        send = min(excess[u], G[u][v]['capacity'] - G[u][v]['flow'])
        if send <= 0:
            return False
        G[u][v]['flow'] += send
        G[v][u]['flow'] -= send
        excess[u] -= send
        excess[v] += send
        return True

    def relabel(u):
        min_h = float('inf')
        for v in G[u]:
            if G[u][v]['capacity'] - G[u][v]['flow'] > 0:
                min_h = min(min_h, height[v])
        if min_h < float('inf'):
            height[u] = min_h + 1

    i = 0
    while i < len(active):
        u = active[i]
        old_h = height[u]

        pushed_something = False
        for v in G[u]:
            if push(u, v):
                pushed_something = True
                if v not in (s, t) and excess[v] > 0 and v not in active:
                    active.append(v)
                if excess[u] == 0:
                    break

        if excess[u] > 0:
            relabel(u)

        if height[u] > old_h:
            active.insert(0, active.pop(i))
            i = 0
        else:
            i += 1


    # Final max flow = net inflow into T
   
    flow_into_t = 0
    for u in G.predecessors(t):
        f = G[u][t]['flow']
        if f > 0:
            flow_into_t += f

    return flow_into_t


# Min-cut

def min_cut_report(G, s):
    visited = set()
    stack = [s]
    while stack:
        u = stack.pop()
        if u not in visited:
            visited.add(u)
            for v in G[u]:
                if G[u][v]['capacity'] - G[u][v]['flow'] > 0:
                    stack.append(v)

    cut = []
    for u in visited:
        for v in G[u]:
            if v not in visited and G[u][v]['capacity'] > 0:
                cut.append((u, v, G[u][v]['capacity']))

    return cut

# Extract flow paths (positive flow only)
def extract_flow_paths(G, s, t):
    prepare_graph(G)
    paths = []

    def dfs(u, path, f):
        if u == t:
            paths.append((path, f))
            return
        for v in list(G[u]):
            flow = G[u][v]['flow']
            if flow > 0:
                G[u][v]['flow'] -= flow
                dfs(v, path + [v], min(f, flow))

    for v in list(G[s]):
        flow = G[s][v]['flow']
        if flow > 0:
            G[s][v]['flow'] -= flow
            dfs(v, [s, v], flow)

    return paths
