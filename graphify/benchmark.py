"""Token-reduction benchmark - measures how much context graphify saves vs naive full-corpus approach."""
from __future__ import annotations
import json
from pathlib import Path
import networkx as nx
from networkx.readwrite import json_graph
from graphify.serve import _score_nodes


_CHARS_PER_TOKEN = 4  # standard approximation


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // _CHARS_PER_TOKEN)


def _query_subgraph_context(G: nx.Graph, question: str, depth: int = 3) -> dict:
    """Run BFS from best-matching nodes and return context metrics."""
    terms = [t.lower() for t in question.split() if len(t) > 2]
    scored = _score_nodes(G, terms)
    start_nodes = [nid for _, nid in scored[:3]]
    if not start_nodes:
        return {"query_tokens": 0, "nodes": set(), "edges": [], "start_nodes": []}

    visited: set[str] = set(start_nodes)
    frontier = set(start_nodes)
    edges_seen: list[tuple] = []
    for _ in range(depth):
        next_frontier: set[str] = set()
        for n in frontier:
            for neighbor in G.neighbors(n):
                if neighbor not in visited:
                    next_frontier.add(neighbor)
                    edges_seen.append((n, neighbor))
        visited.update(next_frontier)
        frontier = next_frontier

    lines = []
    for nid in visited:
        d = G.nodes[nid]
        lines.append(f"NODE {d.get('label', nid)} src={d.get('source_file', '')} loc={d.get('source_location', '')}")
    for u, v in edges_seen:
        if u in visited and v in visited:
            d = G.edges[u, v]
            lines.append(f"EDGE {G.nodes[u].get('label', u)} --{d.get('relation', '')}--> {G.nodes[v].get('label', v)}")

    return {
        "query_tokens": _estimate_tokens("\n".join(lines)),
        "nodes": visited,
        "edges": edges_seen,
        "start_nodes": start_nodes,
    }


def _query_subgraph_tokens(G: nx.Graph, question: str, depth: int = 3) -> int:
    """Run BFS from best-matching nodes and return estimated tokens in the subgraph context."""
    return int(_query_subgraph_context(G, question, depth=depth)["query_tokens"])


def _source_matches_prefix(source_file: str, prefixes: list[str]) -> bool:
    normalized = source_file.replace("\\", "/").lstrip("./")
    return any(normalized.startswith(prefix.replace("\\", "/").lstrip("./")) for prefix in prefixes)


def _quality_metrics(
    G: nx.Graph,
    visited: set[str],
    expected: list[str],
    noisy_source_prefixes: list[str],
) -> dict:
    missed = [nid for nid in expected if nid not in visited]
    found = [nid for nid in expected if nid in visited]
    missed_connected = [
        nid for nid in missed
        if nid in G and any(neighbor in visited for neighbor in G.neighbors(nid))
    ]
    noisy_nodes = [
        nid for nid in visited
        if _source_matches_prefix(str(G.nodes[nid].get("source_file", "")), noisy_source_prefixes)
    ]
    recall = len(found) / len(expected) if expected else None
    noisy_rate = len(noisy_nodes) / len(visited) if visited else 0.0
    return {
        "expected_recall": round(recall, 3) if recall is not None else None,
        "missed_expected_nodes": missed,
        "missed_connected_nodes": missed_connected,
        "noisy_node_rate": round(noisy_rate, 3),
        "noisy_nodes": sorted(noisy_nodes),
    }


_SAMPLE_QUESTIONS = [
    "how does authentication work",
    "what is the main entry point",
    "how are errors handled",
    "what connects the data layer to the api",
    "what are the core abstractions",
]


def run_benchmark(
    graph_path: str = "graphify-out/graph.json",
    corpus_words: int | None = None,
    questions: list[str] | None = None,
    expected_nodes: dict[str, list[str]] | None = None,
    noisy_source_prefixes: list[str] | None = None,
    depth: int = 3,
) -> dict:
    """Measure token reduction: corpus tokens vs graphify query tokens.

    Args:
        graph_path: path to the built graph
        corpus_words: total word count from detect() output; if None, estimated from graph
        questions: list of questions to benchmark; defaults to _SAMPLE_QUESTIONS
        expected_nodes: optional question -> expected node IDs for recall tracking
        noisy_source_prefixes: source path prefixes counted as noisy context
        depth: graph traversal depth for query context

    Returns dict with: corpus_tokens, avg_query_tokens, reduction_ratio, per_question
    """
    data = json.loads(Path(graph_path).read_text(encoding="utf-8"))
    try:
        G = json_graph.node_link_graph(data, edges="links")
    except TypeError:
        G = json_graph.node_link_graph(data)

    if corpus_words is None:
        # Rough estimate: each node label is ~3 words, plus source context
        corpus_words = G.number_of_nodes() * 50

    corpus_tokens = corpus_words * 100 // 75  # words → tokens (100 words ≈ 133 tokens)

    qs = questions or _SAMPLE_QUESTIONS
    expected_nodes = expected_nodes or {}
    noisy_source_prefixes = noisy_source_prefixes or []
    per_question = []
    for q in qs:
        context = _query_subgraph_context(G, q, depth=depth)
        qt = int(context["query_tokens"])
        if qt > 0:
            expected = expected_nodes.get(q, [])
            metrics = _quality_metrics(G, set(context["nodes"]), expected, noisy_source_prefixes)
            per_question.append({
                "question": q,
                "query_tokens": qt,
                "reduction": round(corpus_tokens / qt, 1),
                "matched_nodes": sorted(context["nodes"]),
                **metrics,
            })

    if not per_question:
        return {"error": "No matching nodes found for sample questions. Build the graph first."}

    avg_query_tokens = sum(p["query_tokens"] for p in per_question) // len(per_question)
    reduction_ratio = round(corpus_tokens / avg_query_tokens, 1) if avg_query_tokens > 0 else 0
    recall_values = [p["expected_recall"] for p in per_question if p["expected_recall"] is not None]
    avg_expected_recall = round(sum(recall_values) / len(recall_values), 3) if recall_values else None
    avg_noisy_node_rate = round(sum(p["noisy_node_rate"] for p in per_question) / len(per_question), 3)

    return {
        "corpus_tokens": corpus_tokens,
        "corpus_words": corpus_words,
        "nodes": G.number_of_nodes(),
        "edges": G.number_of_edges(),
        "avg_query_tokens": avg_query_tokens,
        "reduction_ratio": reduction_ratio,
        "avg_expected_recall": avg_expected_recall,
        "avg_noisy_node_rate": avg_noisy_node_rate,
        "per_question": per_question,
    }


def print_benchmark(result: dict) -> None:
    """Print a human-readable benchmark report."""
    if "error" in result:
        print(f"Benchmark error: {result['error']}")
        return

    print(f"\ngraphify token reduction benchmark")
    print(f"{'─' * 50}")
    print(f"  Corpus:          {result['corpus_words']:,} words → ~{result['corpus_tokens']:,} tokens (naive)")
    print(f"  Graph:           {result['nodes']:,} nodes, {result['edges']:,} edges")
    print(f"  Avg query cost:  ~{result['avg_query_tokens']:,} tokens")
    print(f"  Reduction:       {result['reduction_ratio']}x fewer tokens per query")
    if result.get("avg_expected_recall") is not None:
        print(f"  Recall:          {result['avg_expected_recall']:.3f} expected-node recall")
    print(f"  Noise:           {result.get('avg_noisy_node_rate', 0):.3f} noisy-node rate")
    print(f"\n  Per question:")
    for p in result["per_question"]:
        quality = ""
        if p.get("expected_recall") is not None:
            quality = f" recall={p['expected_recall']:.3f} noise={p['noisy_node_rate']:.3f}"
        print(f"    [{p['reduction']}x]{quality} {p['question'][:55]}")
    print()
