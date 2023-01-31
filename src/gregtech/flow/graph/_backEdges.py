import collections

# Modified from https://stackoverflow.com/a/53995651/7247528


class BasicGraph():
    def __init__(self, edges):
        self.edges = edges
        self.adj = BasicGraph._build_adjacency_list(edges)
        self.back_edges = []

    @staticmethod
    def _build_adjacency_list(edges):
        adj = collections.defaultdict(list)
        for edge in edges:
            adj[edge[0]].append(edge[1])
        return adj


def dfs(g):
    discovered = set()
    finished = set()

    for u in list(g.adj):
        if u not in discovered and u not in finished:
            dfs_visit(g, u, discovered, finished)


def dfs_visit(g, u, discovered, finished):
    discovered.add(u)

    for v in g.adj[u]:
        # Detect cycles
        if v in discovered:
            g.back_edges.append((u, v))
            # print(f"Cycle detected: found a back edge from {u} to {v}.")
            continue

        # Recurse into DFS tree
        if v not in finished:
            dfs_visit(g, v, discovered, finished)

    discovered.remove(u)
    finished.add(u)


if __name__ == "__main__":
    G = BasicGraph(
        [
            ('u', 'v'),
            ('u', 'x'),
            ('v', 'y'),
            ('w', 'y'),
            ('w', 'z'),
            ('x', 'v'),
            ('y', 'x'),
            ('z', 'z'),
        ]
    )

    dfs(G)
