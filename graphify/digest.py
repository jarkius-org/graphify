"""Export Graphify graph/report summaries into durable markdown memory."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from networkx.readwrite import json_graph


def _slugify(value: str) -> str:
    slug = re.sub(r"[^\w]+", "-", value.lower()).strip("-")
    return slug[:80] or "graphify"


def _section(markdown: str, heading: str, *, max_lines: int = 20) -> list[str]:
    lines = markdown.splitlines()
    start = None
    marker = f"## {heading}"
    for idx, line in enumerate(lines):
        if line.strip() == marker:
            start = idx + 1
            break
    if start is None:
        return []

    out: list[str] = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        if line.strip():
            out.append(line)
        if len(out) >= max_lines:
            break
    return out


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    counter = 2
    while True:
        candidate = path.with_name(f"{path.stem}-{counter}{path.suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def _top_nodes(graph_path: Path, limit: int = 10) -> tuple[int, int, list[str]]:
    raw = json.loads(graph_path.read_text(encoding="utf-8"))
    try:
        graph = json_graph.node_link_graph(raw, edges="links")
    except TypeError:
        graph = json_graph.node_link_graph(raw)

    nodes: list[str] = []
    for node_id, degree in sorted(graph.degree(), key=lambda item: item[1], reverse=True)[:limit]:
        data = graph.nodes[node_id]
        label = data.get("label", node_id)
        source = data.get("source_file", "")
        source_text = f" - `{source}`" if source else ""
        nodes.append(f"- `{label}` ({degree} connections){source_text}")
    return graph.number_of_nodes(), graph.number_of_edges(), nodes


def write_digest(
    *,
    project_path: Path,
    graph_path: Path,
    report_path: Path,
    memory_dir: Path,
    project_slug: str | None = None,
    psi_outbox: Path | None = None,
) -> Path:
    """Write an append-only graph digest and optionally a Psi outbox note."""
    project_path = project_path.resolve()
    graph_path = graph_path.resolve()
    report_path = report_path.resolve()
    memory_dir = memory_dir.expanduser()

    if not graph_path.exists():
        raise FileNotFoundError(f"graph file not found: {graph_path}")
    if not report_path.exists():
        raise FileNotFoundError(f"report file not found: {report_path}")

    memory_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    slug = _slugify(project_slug or project_path.name)
    out_path = _unique_path(memory_dir / f"{now.strftime('%Y-%m-%d')}_{slug}_graph-digest.md")

    report = report_path.read_text(encoding="utf-8", errors="replace")
    node_count, edge_count, top_nodes = _top_nodes(graph_path)
    god_nodes = _section(report, "God Nodes (most connected - your core abstractions)")
    surprises = _section(report, "Surprising Connections (you probably didn't know these)")
    questions = _section(report, "Suggested Questions")

    if not god_nodes:
        god_nodes = top_nodes
    if not surprises:
        surprises = ["- Not present in report."]
    if not questions:
        questions = ["- Not present in report."]

    content = "\n".join(
        [
            "---",
            'type: "graphify_digest"',
            f'date: "{now.isoformat()}"',
            f'project: "{project_path.name}"',
            f'project_path: "{project_path}"',
            f'graph_path: "{graph_path}"',
            f'report_path: "{report_path}"',
            'contributor: "graphify"',
            "---",
            "",
            f"# Graphify Digest: {project_path.name}",
            "",
            "## Summary",
            "",
            f"- Nodes: {node_count}",
            f"- Edges: {edge_count}",
            f"- Source graph: `{graph_path}`",
            f"- Source report: `{report_path}`",
            "",
            "## God Nodes",
            "",
            *god_nodes,
            "",
            "## Surprising Connections",
            "",
            *surprises,
            "",
            "## Suggested Questions",
            "",
            *questions,
            "",
            "## Recent Changes",
            "",
            "- Not computed by this digest command. Use `graphify diff` or a saved graph snapshot for change analysis.",
            "",
            "## Layer Routing",
            "",
            "- `docs/wiki`: curated project truth.",
            "- `graphify-out/wiki`: generated graph navigation.",
            "- `~/.oracle-vault`: durable cross-session memory.",
            "- Arra/Psi: optional retrieval acceleration over this digest.",
            "",
        ]
    )
    out_path.write_text(content, encoding="utf-8")

    if psi_outbox is not None:
        psi_outbox = psi_outbox.expanduser()
        psi_outbox.mkdir(parents=True, exist_ok=True)
        note = _unique_path(psi_outbox / f"{now.strftime('%Y-%m-%d')}_{slug}_graph-digest.md")
        note.write_text(
            "\n".join(
                [
                    f"# Graphify Digest Ready: {project_path.name}",
                    "",
                    f"- Digest: `{out_path}`",
                    f"- Graph: `{graph_path}`",
                    f"- Report: `{report_path}`",
                    "",
                    "Index this digest if Arra/Psi retrieval acceleration is available. The markdown digest remains canonical.",
                    "",
                ]
            ),
            encoding="utf-8",
        )

    return out_path
