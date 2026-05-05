"""Changed-file impact analysis over a Graphify graph."""
from __future__ import annotations

from pathlib import Path

import networkx as nx

from graphify.layers import annotate_layers


def _norm_path(value: str | None) -> str:
    return str(value or "").replace("\\", "/").lstrip("./")


def analyze_impact(G: nx.Graph, changed_files: list[str]) -> dict:
    """Map changed files to graph nodes and one-hop affected neighbors."""
    annotate_layers(G)
    changed_set = {_norm_path(path) for path in changed_files}
    changed_nodes = [
        nid for nid, data in G.nodes(data=True)
        if _norm_path(data.get("source_file")) in changed_set
    ]
    changed_node_set = set(changed_nodes)
    affected: list[str] = []
    edge_rows: list[dict] = []
    seen_edges: set[tuple[str, str]] = set()

    for node in changed_nodes:
        for neighbor in G.neighbors(node):
            if neighbor in changed_node_set:
                continue
            if neighbor not in affected:
                affected.append(neighbor)
            key = tuple(sorted((node, neighbor)))
            if key in seen_edges:
                continue
            seen_edges.add(key)
            raw = G[node][neighbor]
            data = next(iter(raw.values()), {}) if isinstance(G, (nx.MultiGraph, nx.MultiDiGraph)) else raw
            edge_rows.append({
                "source": node,
                "target": neighbor,
                "relation": data.get("relation", ""),
            })

    known_sources = {
        _norm_path(data.get("source_file"))
        for _, data in G.nodes(data=True)
        if data.get("source_file")
    }
    unmapped = [path for path in changed_files if _norm_path(path) not in known_sources]
    involved = changed_nodes + affected
    communities = sorted({
        G.nodes[nid].get("community")
        for nid in involved
        if G.nodes[nid].get("community") is not None
    })
    layers = []
    for nid in involved:
        layer = G.nodes[nid].get("layer")
        if layer and layer not in layers:
            layers.append(layer)

    result = {
        "changed_files": changed_files,
        "changed_nodes": changed_nodes,
        "affected_nodes": affected,
        "affected_edges": edge_rows,
        "communities": communities,
        "layers": layers,
        "unmapped_files": unmapped,
    }
    if unmapped:
        result["recommendation"] = "Run graphify update . if the graph is stale or the file was newly added."
    return result


def format_impact_markdown(G: nx.Graph, impact: dict) -> str:
    """Render a compact markdown impact report."""
    lines = [
        "# Graphify Diff Impact",
        "",
        f"Changed nodes: {len(impact['changed_nodes'])}",
        f"Affected nodes: {len(impact['affected_nodes'])}",
    ]
    if impact.get("layers"):
        lines.append(f"Layers: {', '.join(impact['layers'])}")
    if impact.get("communities"):
        lines.append(f"Communities: {', '.join(str(c) for c in impact['communities'])}")
    lines.append("")
    for nid in impact["changed_nodes"]:
        lines.append(f"- Changed: {G.nodes[nid].get('label', nid)} ({G.nodes[nid].get('source_file', '')})")
    for nid in impact["affected_nodes"]:
        lines.append(f"- Affected: {G.nodes[nid].get('label', nid)} ({G.nodes[nid].get('source_file', '')})")
    if impact.get("unmapped_files"):
        lines.append("")
        for path in impact["unmapped_files"]:
            lines.append(f"- Unmapped: {path}")
        lines.append(impact.get("recommendation", ""))
    return "\n".join(lines)
