# generate GRAPH_REPORT.md - the human-readable audit trail
from __future__ import annotations
import re
from collections import Counter
from datetime import date
import networkx as nx

_MAX_COMMUNITY_HUBS = 20


def _safe_community_name(label: str) -> str:
    """Mirrors export.safe_name so community hub filenames and report wikilinks always agree."""
    cleaned = re.sub(r'[\\/*?:"<>|#^[\]]', "", label.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")).strip()
    cleaned = re.sub(r"\.(md|mdx|markdown)$", "", cleaned, flags=re.IGNORECASE)
    return cleaned or "unnamed"


def _community_target(cid: int) -> str:
    return f"_COMMUNITY_Community_{cid}"


def _is_generic_community_label(label: str, cid: int) -> bool:
    return label.strip().lower() == f"community {cid}".lower()


def _display_community_label(G: nx.Graph, nodes: list[str], cid: int, fallback: str) -> str:
    """Return a deterministic useful label when no semantic community name exists."""
    if fallback and not _is_generic_community_label(fallback, cid):
        return fallback

    real_nodes = [n for n in nodes if n in G and not _is_report_file_node(G, n)]
    source_counts: dict[str, int] = {}
    for node in real_nodes:
        source_file = str(G.nodes[node].get("source_file") or "")
        if not source_file:
            continue
        parts = source_file.split("/")
        source = "/".join(parts[:2]) if len(parts) > 1 else parts[0]
        if source:
            source_counts[source] = source_counts.get(source, 0) + 1

    top_sources = [name for name, _ in sorted(source_counts.items(), key=lambda item: (-item[1], item[0]))[:2]]
    if top_sources:
        return " / ".join(top_sources)

    top_nodes = sorted(
        real_nodes,
        key=lambda node: (-G.degree(node), str(G.nodes[node].get("label", node)).lower()),
    )[:2]
    if top_nodes:
        return " + ".join(str(G.nodes[node].get("label", node)) for node in top_nodes)

    return fallback or f"Community {cid}"


def _community_hint(G: nx.Graph, nodes: list[str], label: str, limit: int = 2) -> str:
    real_nodes = [n for n in nodes if n in G and not _is_report_file_node(G, n)]
    hints: list[str] = []
    for node in sorted(
        real_nodes,
        key=lambda node_id: (-G.degree(node_id), str(G.nodes[node_id].get("label", node_id)).lower()),
    ):
        node_label = str(G.nodes[node].get("label", node))
        if not node_label or node_label == label or node_label in hints:
            continue
        hints.append(node_label)
        if len(hints) >= limit:
            break
    return ", ".join(hints)


def display_community_labels(
    G: nx.Graph,
    communities: dict[int, list[str]],
    community_labels: dict[int, str],
) -> dict[int, str]:
    labels = {
        cid: _display_community_label(G, nodes, cid, community_labels.get(cid, f"Community {cid}"))
        for cid, nodes in communities.items()
    }
    counts = Counter(labels.values())
    candidates: dict[int, str] = {}
    for cid, nodes in communities.items():
        label = labels[cid]
        if counts[label] > 1:
            hint = _community_hint(G, nodes, label)
            if hint:
                label = f"{label} - {hint}"
            else:
                label = f"{label} #{cid}"
        candidates[cid] = label

    candidate_counts = Counter(candidates.values())
    result: dict[int, str] = {}
    for cid, label in candidates.items():
        if candidate_counts[label] > 1:
            label = f"{label} #{cid}"
        result[cid] = label
    return result


def _is_report_file_node(G: nx.Graph, node: str) -> bool:
    from .analyze import _is_file_node
    return _is_file_node(G, node)


def _community_sample(G: nx.Graph, nodes: list[str], limit: int = 4) -> str:
    real_nodes = [n for n in nodes if n in G and not _is_report_file_node(G, n)]
    ranked = sorted(
        real_nodes,
        key=lambda node: (-G.degree(node), str(G.nodes[node].get("label", node)).lower()),
    )[:limit]
    return ", ".join(f"`{G.nodes[node].get('label', node)}`" for node in ranked)


def _source_root_summary(detection_result: dict, limit: int = 8) -> list[str]:
    files = detection_result.get("files") or {}
    counts: dict[str, int] = {}
    for paths in files.values():
        for value in paths:
            path = str(value)
            root = path.split("/", 1)[0] if "/" in path else path
            if root:
                counts[root] = counts.get(root, 0) + 1
    if not counts:
        return []
    parts = [
        f"{root} ({count})"
        for root, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]
    ]
    if len(counts) > limit:
        parts.append(f"+{len(counts) - limit} more")
    return parts


def generate(
    G: nx.Graph,
    communities: dict[int, list[str]],
    cohesion_scores: dict[int, float],
    community_labels: dict[int, str],
    god_node_list: list[dict],
    surprise_list: list[dict],
    detection_result: dict,
    token_cost: dict,
    root: str,
    suggested_questions: list[dict] | None = None,
    min_community_size: int = 3,
) -> str:
    today = date.today().isoformat()

    confidences = [d.get("confidence", "EXTRACTED") for _, _, d in G.edges(data=True)]
    total = len(confidences) or 1
    ext_pct = round(confidences.count("EXTRACTED") / total * 100)
    inf_pct = round(confidences.count("INFERRED") / total * 100)
    amb_pct = round(confidences.count("AMBIGUOUS") / total * 100)

    inf_edges = [(u, v, d) for u, v, d in G.edges(data=True) if d.get("confidence") == "INFERRED"]
    inf_scores = [d.get("confidence_score", 0.5) for _, _, d in inf_edges]
    inf_avg = round(sum(inf_scores) / len(inf_scores), 2) if inf_scores else None

    lines = [
        f"# Graph Report - {root}  ({today})",
        "",
        "## Corpus Check",
    ]
    if detection_result.get("warning"):
        lines.append(f"- {detection_result['warning']}")
    else:
        lines += [
            f"- {detection_result['total_files']} files · ~{detection_result['total_words']:,} words",
            "- Verdict: corpus is large enough that graph structure adds value.",
        ]
    source_roots = _source_root_summary(detection_result)
    if source_roots:
        lines.append(f"- Indexed roots: {', '.join(source_roots)}")

    from .analyze import _is_file_node as _ifn
    non_empty = {cid: nodes for cid, nodes in communities.items()
                 if any(not _ifn(G, n) for n in nodes)}
    display_labels = display_community_labels(G, communities, community_labels)

    lines += [
        "",
        "## Summary",
        f"- {G.number_of_nodes()} nodes · {G.number_of_edges()} edges · "
        f"{len(non_empty)} concept communities · {len(communities)} total clusters",
        f"- Extraction: {ext_pct}% EXTRACTED · {inf_pct}% INFERRED · {amb_pct}% AMBIGUOUS"
        + (f" · INFERRED: {len(inf_edges)} edges (avg confidence: {inf_avg})" if inf_avg is not None else ""),
        f"- Token cost: {token_cost.get('input', 0):,} input · {token_cost.get('output', 0):,} output",
    ]

    # Community hub navigation - links to _COMMUNITY_*.md files in the Obsidian vault.
    # Without these, GRAPH_REPORT.md is a dead-end and the vault splits into disconnected components.
    if non_empty:
        ranked_hubs = sorted(
            non_empty.items(),
            key=lambda item: (
                -sum(1 for n in item[1] if not _ifn(G, n)),
                str(display_labels.get(item[0], f"Community {item[0]}")).lower(),
            ),
        )
        lines += ["", "## Community Hubs (Navigation)"]
        if len(ranked_hubs) > _MAX_COMMUNITY_HUBS:
            lines.append(
                f"_Showing the {_MAX_COMMUNITY_HUBS} largest communities; "
                f"{len(ranked_hubs) - _MAX_COMMUNITY_HUBS} smaller communities are listed below._"
            )
        for cid, nodes in ranked_hubs[:_MAX_COMMUNITY_HUBS]:
            label = display_labels.get(cid, f"Community {cid}")
            target = _community_target(cid)
            sample = _community_sample(G, nodes)
            suffix = f" - {sample}" if sample else ""
            lines.append(f"- [[{target}|{label}]] ({len(nodes)} nodes){suffix}")

    lines += [
        "",
        "## God Nodes (most connected - your core abstractions)",
    ]
    for i, node in enumerate(god_node_list, 1):
        lines.append(f"{i}. `{node['label']}` - {node['degree']} edges")

    lines += ["", "## Surprising Connections (you probably didn't know these)"]
    if surprise_list:
        for s in surprise_list:
            relation = s.get("relation", "related_to")
            note = s.get("note", "")
            files = s.get("source_files", ["", ""])
            conf = s.get("confidence", "EXTRACTED")
            cscore = s.get("confidence_score")
            if conf == "INFERRED" and cscore is not None:
                conf_tag = f"INFERRED {cscore:.2f}"
            else:
                conf_tag = conf
            sem_tag = " [semantically similar]" if relation == "semantically_similar_to" else ""
            lines += [
                f"- `{s['source']}` --{relation}--> `{s['target']}`  [{conf_tag}]{sem_tag}",
                f"  {files[0]} → {files[1]}" + (f"  _{note}_" if note else ""),
            ]
    else:
        lines.append("- None detected - all connections are within the same source files.")

    hyperedges = G.graph.get("hyperedges", [])
    if hyperedges:
        lines += ["", "## Hyperedges (group relationships)"]
        for h in hyperedges:
            node_labels = ", ".join(h.get("nodes", []))
            conf = h.get("confidence", "INFERRED")
            cscore = h.get("confidence_score")
            conf_tag = f"{conf} {cscore:.2f}" if cscore is not None else conf
            lines.append(f"- **{h.get('label', h.get('id', ''))}** — {node_labels} [{conf_tag}]")

    thin_count = sum(
        1 for nodes in communities.values()
        if 0 < sum(1 for n in nodes if not _ifn(G, n)) < min_community_size
    )
    lines += ["", f"## Communities ({len(communities)} total, {thin_count} thin omitted)"]
    for cid, nodes in communities.items():
        label = display_labels.get(cid, f"Community {cid}")
        score = cohesion_scores.get(cid, 0.0)
        # Filter method/function stubs from display - they're structural noise
        real_nodes = [n for n in nodes if not _ifn(G, n)]
        if not real_nodes:
            continue
        if len(real_nodes) < min_community_size:
            continue
        display = [G.nodes[n].get("label", n) for n in real_nodes[:8]]
        suffix = f" (+{len(real_nodes)-8} more)" if len(real_nodes) > 8 else ""
        lines += [
            "",
            f"### Community {cid} - \"{label}\"",
            f"Cohesion: {score}",
            f"Nodes ({len(real_nodes)}): {', '.join(display)}{suffix}",
        ]

    ambiguous = [(u, v, d) for u, v, d in G.edges(data=True) if d.get("confidence") == "AMBIGUOUS"]
    if ambiguous:
        lines += ["", "## Ambiguous Edges - Review These"]
        for u, v, d in ambiguous:
            ul = G.nodes[u].get("label", u)
            vl = G.nodes[v].get("label", v)
            lines += [
                f"- `{ul}` → `{vl}`  [AMBIGUOUS]",
                f"  {d.get('source_file', '')} · relation: {d.get('relation', 'unknown')}",
            ]

    # --- Gaps section ---
    from .analyze import _is_file_node, _is_concept_node

    isolated = [
        n for n in G.nodes()
        if G.degree(n) <= 1 and not _is_file_node(G, n) and not _is_concept_node(G, n)
    ]
    thin_communities = {
        cid: nodes for cid, nodes in communities.items()
        if 0 < sum(1 for n in nodes if not _is_file_node(G, n)) < 3
    }
    gap_count = len(isolated) + len(thin_communities)

    if gap_count > 0 or amb_pct > 20:
        lines += ["", "## Knowledge Gaps"]
        if isolated:
            isolated_labels = [G.nodes[n].get("label", n) for n in isolated[:5]]
            suffix = f" (+{len(isolated)-5} more)" if len(isolated) > 5 else ""
            lines.append(f"- **{len(isolated)} isolated node(s):** {', '.join(f'`{l}`' for l in isolated_labels)}{suffix}")
            lines.append("  These have ≤1 connection - possible missing edges or undocumented components.")
        if thin_communities:
            lines.append(f"- **{len(thin_communities)} thin communities (<{min_community_size} nodes) omitted from report** — run `graphify query` to explore isolated nodes.")
        if amb_pct > 20:
            lines.append(f"- **High ambiguity: {amb_pct}% of edges are AMBIGUOUS.** Review the Ambiguous Edges section above.")

    if suggested_questions:
        lines += ["", "## Suggested Questions"]
        no_signal = len(suggested_questions) == 1 and suggested_questions[0].get("type") == "no_signal"
        if no_signal:
            lines.append(f"_{suggested_questions[0]['why']}_")
        else:
            lines.append("_Questions this graph is uniquely positioned to answer:_")
            lines.append("")
            for q in suggested_questions:
                if q.get("question"):
                    lines.append(f"- **{q['question']}**")
                    lines.append(f"  _{q['why']}_")

    return "\n".join(lines)
