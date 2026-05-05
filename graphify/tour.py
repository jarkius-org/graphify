"""Generate a deterministic newcomer tour from a Graphify graph."""
from __future__ import annotations

import networkx as nx

from graphify.layers import LAYER_ORDER, annotate_layers


def _layer_rank(layer: str) -> int:
    try:
        return LAYER_ORDER.index(layer)
    except ValueError:
        return len(LAYER_ORDER)


def _tour_order(G: nx.Graph) -> list[str]:
    if isinstance(G, nx.DiGraph) and nx.is_directed_acyclic_graph(G):
        return list(nx.topological_sort(G))
    if isinstance(G, nx.DiGraph):
        return sorted(G.nodes())
    return sorted(G.nodes(), key=lambda nid: (_layer_rank(G.nodes[nid].get("layer", "")), -G.degree(nid), str(nid)))


def generate_tour(G: nx.Graph, limit: int | None = None) -> list[dict]:
    """Return ordered nodes that form a compact "start here" tour."""
    annotate_layers(G)
    ordered = _tour_order(G)
    if limit is not None:
        ordered = ordered[:limit]
    return [
        {
            "id": nid,
            "label": G.nodes[nid].get("label", nid),
            "layer": G.nodes[nid].get("layer", "Utility"),
            "source_file": G.nodes[nid].get("source_file", ""),
            "community": G.nodes[nid].get("community"),
        }
        for nid in ordered
    ]
