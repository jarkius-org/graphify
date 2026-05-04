"""Evaluation-style tests for Graphify's assistant-facing usefulness."""
from __future__ import annotations

import json

import networkx as nx
from networkx.readwrite import json_graph

from graphify.benchmark import _estimate_tokens, run_benchmark
from graphify.serve import _query_graph_text


def _write_graph(tmp_path, G: nx.Graph):
    graph_path = tmp_path / "graph.json"
    graph_path.write_text(json.dumps(json_graph.node_link_data(G, edges="links")))
    return graph_path


def _naive_search_context_tokens(files: dict[str, str], query: str) -> tuple[int, str]:
    terms = [term.lower() for term in query.split() if len(term) > 2]
    matched = [
        f"FILE {path}\n{content}"
        for path, content in files.items()
        if any(term in content.lower() for term in terms)
    ]
    context = "\n".join(matched)
    return _estimate_tokens(context), context


def _assistant_eval_graph() -> nx.Graph:
    G = nx.Graph()
    G.add_node("cli", label="main()", source_file="graphify/__main__.py", source_location="L1184", community=0)
    G.add_node("run_update", label="_run_update()", source_file="graphify/__main__.py", source_location="L1089", community=0)
    G.add_node("rebuild", label="_rebuild_code()", source_file="graphify/watch.py", source_location="L39", community=1)
    G.add_node("detect", label="detect()", source_file="graphify/detect.py", source_location="L621", community=1)
    G.add_node("extract", label="extract()", source_file="graphify/extract.py", source_location="L4141", community=1)
    G.add_node("report", label="generate()", source_file="graphify/report.py", source_location="L15", community=1)
    G.add_node("json", label="to_json()", source_file="graphify/export.py", source_location="L343", community=1)
    G.add_node("html", label="to_html()", source_file="graphify/export.py", source_location="L433", community=1)
    G.add_node(
        "watch_test",
        label="test_rebuild_code_preserves_non_code_source_nodes()",
        source_file="tests/test_watch.py",
        source_location="L125",
        community=1,
    )
    G.add_node("php", label="extract_php()", source_file="graphify/extract.py", source_location="L3250", community=2)
    G.add_node("swift", label="extract_swift()", source_file="graphify/extract.py", source_location="L1391", community=2)
    G.add_node("lang_tests", label="test_php_finds_imports()", source_file="tests/test_languages.py", source_location="L330", community=2)
    G.add_node("generic_main", label="main()", source_file="tests/fixtures/sample.zig", source_location="L34", community=3)

    G.add_edge("cli", "run_update", relation="calls", confidence="EXTRACTED", context="call")
    G.add_edge("run_update", "rebuild", relation="calls", confidence="EXTRACTED", context="call")
    G.add_edge("rebuild", "detect", relation="calls", confidence="EXTRACTED", context="call")
    G.add_edge("rebuild", "extract", relation="calls", confidence="EXTRACTED", context="call")
    G.add_edge("rebuild", "json", relation="calls", confidence="EXTRACTED", context="call")
    G.add_edge("rebuild", "html", relation="calls", confidence="EXTRACTED", context="call")
    G.add_edge("rebuild", "report", relation="calls", confidence="EXTRACTED", context="call")
    G.add_edge("watch_test", "rebuild", relation="tests", confidence="EXTRACTED")
    G.add_edge("extract", "php", relation="dispatches", confidence="EXTRACTED")
    G.add_edge("extract", "swift", relation="dispatches", confidence="EXTRACTED")
    G.add_edge("lang_tests", "php", relation="tests", confidence="EXTRACTED")
    G.add_edge("generic_main", "php", relation="fixture_uses", confidence="EXTRACTED")
    return G


def test_assistant_eval_benchmark_shows_token_reduction(tmp_path):
    graph_path = _write_graph(tmp_path, _assistant_eval_graph())

    result = run_benchmark(
        str(graph_path),
        corpus_words=50_000,
        questions=[
            "what is the main entry point",
            "how does graphify update code files",
            "how is extract_php tested",
        ],
    )

    assert result["reduction_ratio"] >= 50
    assert len(result["per_question"]) == 3
    assert all(case["query_tokens"] < result["corpus_tokens"] for case in result["per_question"])


def test_assistant_eval_query_keeps_implementation_and_tests_together():
    G = _assistant_eval_graph()

    text = _query_graph_text(G, "how does graphify update code files", depth=2, token_budget=1200)

    assert "_rebuild_code()" in text
    assert "detect()" in text
    assert "extract()" in text
    assert "test_rebuild_code_preserves_non_code_source_nodes()" in text


def test_assistant_eval_exact_symbol_ranking_resists_fixture_noise():
    G = _assistant_eval_graph()

    text = _query_graph_text(G, "extract_php", depth=1, token_budget=900)
    first_node_line = next(line for line in text.splitlines() if line.startswith("NODE "))

    assert "extract_php()" in first_node_line
    assert "tests/fixtures/sample.zig" not in first_node_line


def test_assistant_eval_graph_context_is_smaller_than_naive_search():
    G = _assistant_eval_graph()
    files = {
        "docs/update.md": "graphify update code files\n" + ("workflow notes " * 2_000),
        "graphify/watch.py": "def _rebuild_code():\n    pass\n" + ("implementation detail " * 1_500),
        "tests/test_watch.py": "def test_rebuild_code_preserves_non_code_source_nodes():\n    pass\n",
    }

    graph_text = _query_graph_text(G, "how does graphify update code files", depth=2, token_budget=1200)
    graph_tokens = _estimate_tokens(graph_text)
    search_tokens, search_context = _naive_search_context_tokens(files, "graphify update code files")

    assert graph_tokens * 10 < search_tokens
    assert "_rebuild_code()" in graph_text
    assert "test_rebuild_code_preserves_non_code_source_nodes()" in graph_text
    assert len(search_context) > len(graph_text)


def test_assistant_eval_graph_finds_connected_nodes_search_misses():
    G = _assistant_eval_graph()
    files = {
        "docs/update.md": "graphify update code files by rebuilding the code graph",
        "graphify/watch.py": "def _rebuild_code():\n    detect()\n    extract()\n",
    }

    graph_text = _query_graph_text(G, "how does graphify update code files", depth=2, token_budget=1200)
    _, search_context = _naive_search_context_tokens(files, "graphify update code files")

    assert "to_html()" in graph_text
    assert "to_json()" in graph_text
    assert "to_html()" not in search_context
    assert "to_json()" not in search_context
