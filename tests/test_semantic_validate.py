from __future__ import annotations

from graphify.llm import _merge_into
from graphify.semantic_validate import validate_semantic_graph


def test_validate_semantic_graph_normalizes_aliases_and_empty_collections():
    fragment = {
        "nodes": [
            {"id": "auth_login", "label": "Login", "file_type": "doc", "source_file": "docs/auth.md"},
            {"id": "auth_session", "label": "Session", "file_type": "concept", "source_file": "docs/auth.md"},
        ],
        "edges": [
            {
                "source": "auth_login",
                "target": "auth_session",
                "relation": "invoke",
                "confidence": "inferred",
                "confidence_score": 0.72,
            }
        ],
        "hyperedges": None,
    }

    result = validate_semantic_graph(fragment)

    assert result["nodes"][0]["file_type"] == "document"
    assert result["edges"][0]["relation"] == "calls"
    assert result["edges"][0]["confidence"] == "INFERRED"
    assert result["edges"][0]["confidence_score"] == 0.72
    assert result["hyperedges"] == []


def test_validate_semantic_graph_drops_dangling_edges_with_warning():
    fragment = {
        "nodes": [{"id": "known", "label": "Known", "file_type": "code"}],
        "edges": [
            {"source": "known", "target": "missing", "relation": "references", "confidence": "EXTRACTED"},
            {"source": "known", "target": "known", "relation": "related_to", "confidence": "INFERRED"},
        ],
    }

    result = validate_semantic_graph(fragment)

    assert len(result["edges"]) == 1
    assert result["edges"][0]["relation"] == "conceptually_related_to"
    assert result["warnings"] == [
        {
            "code": "dangling_edge",
            "message": "Dropped edge known -> missing because one or both nodes are missing.",
            "edge": {"source": "known", "target": "missing", "relation": "references", "confidence": "EXTRACTED"},
        }
    ]


def test_validate_semantic_graph_drops_unknown_relations():
    fragment = {
        "nodes": [
            {"id": "a", "label": "A", "file_type": "code"},
            {"id": "b", "label": "B", "file_type": "code"},
        ],
        "edges": [{"source": "a", "target": "b", "relation": "magically_knows", "confidence": "INFERRED"}],
    }

    result = validate_semantic_graph(fragment)

    assert result["edges"] == []
    assert result["warnings"][0]["code"] == "unknown_relation"


def test_validate_semantic_graph_is_idempotent_for_valid_input():
    fragment = {
        "nodes": [{"id": "a", "label": "A", "file_type": "rationale", "source_file": "docs/a.md"}],
        "edges": [{"source": "a", "target": "a", "relation": "rationale_for", "confidence": "AMBIGUOUS"}],
        "hyperedges": [],
        "input_tokens": 10,
        "output_tokens": 5,
    }

    result = validate_semantic_graph(fragment)

    assert result == {**fragment, "warnings": []}


def test_llm_merge_validates_chunk_results_before_accumulating():
    merged = {"nodes": [], "edges": [], "hyperedges": [], "input_tokens": 0, "output_tokens": 0}
    chunk = {
        "nodes": [{"id": "a", "label": "A", "file_type": "doc"}],
        "edges": [{"source": "a", "target": "missing", "relation": "references", "confidence": "EXTRACTED"}],
        "input_tokens": 10,
        "output_tokens": 3,
    }

    _merge_into(merged, chunk)

    assert merged["nodes"][0]["file_type"] == "document"
    assert merged["edges"] == []
    assert merged["warnings"][0]["code"] == "dangling_edge"
    assert merged["input_tokens"] == 10
    assert merged["output_tokens"] == 3
