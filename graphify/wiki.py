# Wiki export - Wikipedia-style markdown articles from the knowledge graph
# Generates an agent-crawlable wiki: index.md + one article per community + god node articles
from __future__ import annotations
from collections import Counter
from pathlib import Path
from typing import Any
import networkx as nx

from graphify.report import display_community_labels


def _safe_filename(name: str) -> str:
    """Make a label safe for use as a filename across platforms.

    Substitutes characters that Windows reserves in filenames
    (< > : " / \\ | ? *) and strips trailing dots/spaces, also reserved.
    Falls back to 'unnamed' for empty results and caps length at 200
    chars to stay well under common filesystem limits.
    """
    import re
    s = name.replace("/", "-").replace(" ", "_").replace(":", "-")
    s = re.sub(r'[<>:"/\\|?*]', '_', s)
    s = s.strip('. ')
    return s[:200] if s else 'unnamed'


def _community_target(cid: Any) -> str:
    return _safe_filename(f"_COMMUNITY_Community {cid}")


def _wiki_link(target: str, label: str) -> str:
    return f"[[{target}|{label}]]" if target != label else f"[[{target}]]"


def _cross_community_links(G: nx.Graph, nodes: list[str], own_cid: int) -> list[tuple[Any, int]]:
    """Return (community_id, edge_count) pairs for cross-community connections, sorted descending."""
    counts: dict[Any, int] = Counter()
    for nid in nodes:
        for neighbor in G.neighbors(nid):
            nd = G.nodes[neighbor]
            ncid = nd.get("community")
            if ncid is not None and ncid != own_cid:
                counts[ncid] += 1
    return sorted(counts.items(), key=lambda x: -x[1])


def _community_article(
    G: nx.Graph,
    cid: int,
    nodes: list[str],
    label: str,
    labels: dict[int, str],
    community_targets: dict[Any, str],
    cohesion: float | None,
) -> str:
    top_nodes = sorted(nodes, key=lambda n: G.degree(n), reverse=True)[:25]
    cross = _cross_community_links(G, nodes, cid)

    # Edge confidence breakdown
    conf_counts: Counter = Counter()
    for nid in nodes:
        for neighbor in G.neighbors(nid):
            ed = G.edges[nid, neighbor]
            conf_counts[ed.get("confidence", "EXTRACTED")] += 1
    total_edges = sum(conf_counts.values()) or 1

    sources = sorted({G.nodes[n].get("source_file", "") for n in nodes} - {""})

    lines: list[str] = []
    lines += [f"# {label}", ""]

    meta_parts = [f"{len(nodes)} nodes"]
    if cohesion is not None:
        meta_parts.append(f"cohesion {cohesion:.2f}")
    lines += [f"> {' · '.join(meta_parts)}", ""]

    lines += ["## Key Concepts", ""]
    for nid in top_nodes:
        d = G.nodes[nid]
        node_label = d.get("label", nid)
        src = d.get("source_file", "")
        degree = G.degree(nid)
        src_str = f" — `{src}`" if src else ""
        lines.append(f"- **{node_label}** ({degree} connections){src_str}")
    remaining = len(nodes) - len(top_nodes)
    if remaining > 0:
        lines.append(f"- *... and {remaining} more nodes in this community*")
    lines.append("")

    lines += ["## Relationships", ""]
    if cross:
        for other_cid, count in cross[:12]:
            other_label = labels.get(other_cid, f"Community {other_cid}")
            target = community_targets.get(other_cid, _community_target(other_cid))
            lines.append(f"- {_wiki_link(target, other_label)} ({count} shared connections)")
    else:
        lines.append("- No strong cross-community connections detected")
    lines.append("")

    if sources:
        lines += ["## Source Files", ""]
        for src in sources[:20]:
            lines.append(f"- `{src}`")
        lines.append("")

    lines += ["## Audit Trail", ""]
    for conf in ("EXTRACTED", "INFERRED", "AMBIGUOUS"):
        n = conf_counts.get(conf, 0)
        pct = round(n / total_edges * 100)
        lines.append(f"- {conf}: {n} ({pct}%)")
    lines.append("")

    lines += ["---", "", "*Part of the graphify knowledge wiki. See [[index]] to navigate.*"]
    return "\n".join(lines)


def _god_node_article(
    G: nx.Graph,
    nid: str,
    labels: dict[int, str],
    community_targets: dict[Any, str],
    god_targets: dict[str, str],
) -> str:
    d = G.nodes[nid]
    node_label = d.get("label", nid)
    src = d.get("source_file", "")
    cid = d.get("community")
    community_name = labels.get(cid, f"Community {cid}") if cid is not None else None

    lines: list[str] = []
    lines += [f"# {node_label}", ""]
    lines += [f"> God node · {G.degree(nid)} connections · `{src}`", ""]

    if community_name:
        target = community_targets.get(cid, _community_target(cid))
        lines += [f"**Community:** {_wiki_link(target, community_name)}", ""]

    # Group neighbors by relation type
    by_relation: dict[str, list[str]] = {}
    for neighbor in sorted(G.neighbors(nid), key=lambda n: G.degree(n), reverse=True):
        nd = G.nodes[neighbor]
        ed = G.edges[nid, neighbor]
        rel = ed.get("relation", "related")
        neighbor_label = nd.get("label", neighbor)
        conf = ed.get("confidence", "")
        conf_str = f" `{conf}`" if conf else ""
        if neighbor in god_targets:
            target = god_targets[neighbor]
            by_relation.setdefault(rel, []).append(f"{_wiki_link(target, neighbor_label)}{conf_str}")
        else:
            by_relation.setdefault(rel, []).append(f"`{neighbor_label}`{conf_str}")

    lines += ["## Connections by Relation", ""]
    for rel, targets in sorted(by_relation.items()):
        lines.append(f"### {rel}")
        for t in targets[:20]:
            lines.append(f"- {t}")
        lines.append("")

    lines += ["---", "", "*Part of the graphify knowledge wiki. See [[index]] to navigate.*"]
    return "\n".join(lines)


def _index_md(
    communities: dict[int, list[str]],
    labels: dict[int, str],
    community_targets: dict[Any, str],
    god_nodes_data: list[dict],
    god_targets: dict[str, str],
    total_nodes: int,
    total_edges: int,
) -> str:
    lines: list[str] = [
        "# Knowledge Graph Index",
        "",
        "> Auto-generated by graphify. Start here — read community articles for context, then drill into god nodes for detail.",
        "",
        f"**{total_nodes} nodes · {total_edges} edges · {len(communities)} communities**",
        "",
        "---",
        "",
        "## Communities",
        "(sorted by size, largest first)",
        "",
    ]

    for cid, nodes in sorted(communities.items(), key=lambda x: -len(x[1])):
        label = labels.get(cid, f"Community {cid}")
        target = community_targets.get(cid, _community_target(cid))
        lines.append(f"- {_wiki_link(target, label)} — {len(nodes)} nodes")
    lines.append("")

    if god_nodes_data:
        lines += ["## God Nodes", "(most connected concepts — the load-bearing abstractions)", ""]
        for node in god_nodes_data:
            target = god_targets.get(node.get("id"))
            if target:
                lines.append(f"- {_wiki_link(target, node['label'])} — {node['degree']} connections")
        lines.append("")

    lines += [
        "---",
        "",
        "*Generated by [graphify](https://github.com/safishamsi/graphify)*",
    ]
    return "\n".join(lines)


def to_wiki(
    G: nx.Graph,
    communities: dict[int, list[str]],
    output_dir: str | Path,
    community_labels: dict[int, str] | None = None,
    cohesion: dict[int, float] | None = None,
    god_nodes_data: list[dict] | None = None,
) -> int:
    """Generate a Wikipedia-style wiki from the graph.

    Writes:
      - index.md            — agent entry point, catalog of all articles
      - _COMMUNITY_Community_<id>.md  — one article per community
      - _GOD_<GodNodeLabel>.md        — one article per god node

    Returns the number of articles written (excluding index.md).
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # Clear stale .md files from previous runs to prevent orphan accumulation.
    # Community labels are LLM-generated (per skill.md Step 5) and non-deterministic
    # across runs — the same conceptual community may be named differently each time
    # (e.g. "AutoAgent Skills" → "AutoAgent Methodology"), leaving the previous file
    # as an orphan. Since to_wiki() owns wiki/ entirely (always writes the full set),
    # it can safely clear .md files at the start of each call.
    for old_article in out.glob("*.md"):
        old_article.unlink()

    raw_labels = community_labels or {cid: f"Community {cid}" for cid in communities}
    labels = display_community_labels(G, communities, raw_labels)
    cohesion = cohesion or {}
    god_nodes_data = god_nodes_data or []

    count = 0
    used_slugs: set[str] = {"index"}

    def _unique_slug(base: str) -> str:
        slug = base
        n = 2
        while slug in used_slugs:
            slug = f"{base}_{n}"
            n += 1
        used_slugs.add(slug)
        return slug

    community_targets = {cid: _unique_slug(_community_target(cid)) for cid in communities}
    valid_god_nodes = [node_data for node_data in god_nodes_data if node_data.get("id") in G]
    god_targets = {
        node_data["id"]: _unique_slug(_safe_filename(f"_GOD_{node_data['label']}"))
        for node_data in valid_god_nodes
    }

    # Community articles
    for cid, nodes in communities.items():
        label = labels.get(cid, f"Community {cid}")
        article = _community_article(G, cid, nodes, label, labels, community_targets, cohesion.get(cid))
        slug = community_targets[cid]
        (out / f"{slug}.md").write_text(article, encoding="utf-8")
        count += 1

    # God node articles
    for node_data in valid_god_nodes:
        nid = node_data["id"]
        article = _god_node_article(G, nid, labels, community_targets, god_targets)
        slug = god_targets[nid]
        (out / f"{slug}.md").write_text(article, encoding="utf-8")
        count += 1

    # Index
    (out / "index.md").write_text(
        _index_md(
            communities,
            labels,
            community_targets,
            valid_god_nodes,
            god_targets,
            G.number_of_nodes(),
            G.number_of_edges(),
        ),
        encoding="utf-8",
    )

    return count
