from __future__ import annotations

import collections
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

# Modified from https://stackoverflow.com/a/53995651/7247528


class BasicGraph():
    """Basic graph abstraction used to remove back edges (loops)."""

    def __init__(self, edges: Sequence[tuple[str, str]]) -> None:
        """Initializes a basic graph object.

        Args:
            edges (Sequence[tuple]): Sequence of basic edges
        """
        self.edges = edges
        self.adj = BasicGraph._build_adjacency_list(edges)
        self.back_edges: Sequence[tuple[str, str]] = []

    @staticmethod
    def _build_adjacency_list(edges: Sequence[tuple[str, str]]
                              ) -> collections.defaultdict[str, list]:
        """Builds an adjacency from a list of basic edges.

        Args:
            edges (Sequence[tuple[str, str]]): Sequence of basic edges

        Returns:
            collections.defaultdict[str, list]: Adjacency list
        """
        adj = collections.defaultdict(list)
        for edge in edges:
            adj[edge[0]].append(edge[1])
        return adj


def dfs(g: BasicGraph) -> None:
    """Performs a depth-first search of a BasicGraph object to remove back edges.

    According to Lemma 22.11 of Cormen et al., Introduction to Algorithms (CLRS):

    "A directed graph G is acyclic if and only if a depth-first search of G yields no back edges."

    Args:
        g (BasicGraph): BasicGraph object
    """
    discovered: set[str] = set()
    finished: set[str] = set()

    for u in list(g.adj):
        if u not in discovered and u not in finished:
            dfs_visit(g, u, discovered, finished)


def dfs_visit(g: BasicGraph, u: str, discovered: set, finished: set) -> None:
    """Depth-first search visit edge.

    Args:
        g (BasicGraph): BasicGraph object
        u (str): Node of an edge
        discovered (set): Set
        finished (set): Set
    """
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
