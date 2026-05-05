"""Normalize and validate LLM semantic graph fragments before merge."""
from __future__ import annotations

from copy import deepcopy
from typing import Any


ALLOWED_RELATIONS = {
    "calls",
    "implements",
    "references",
    "cites",
    "conceptually_related_to",
    "shares_data_with",
    "semantically_similar_to",
    "rationale_for",
}

RELATION_ALIASES = {
    "call": "calls",
    "invoke": "calls",
    "invokes": "calls",
    "import": "references",
    "imports": "references",
    "use": "references",
    "uses": "references",
    "depends_on": "references",
    "citation": "cites",
    "related": "conceptually_related_to",
    "related_to": "conceptually_related_to",
    "conceptually_related": "conceptually_related_to",
    "similar": "semantically_similar_to",
    "similar_to": "semantically_similar_to",
    "semantic_similarity": "semantically_similar_to",
}

FILE_TYPE_ALIASES = {
    "doc": "document",
    "docs": "document",
    "markdown": "document",
    "md": "document",
    "article": "document",
    "paper_pdf": "paper",
    "pdf": "paper",
    "img": "image",
    "image_file": "image",
}

ALLOWED_CONFIDENCE = {"EXTRACTED", "INFERRED", "AMBIGUOUS"}


def _list_or_empty(value: Any) -> list:
    return value if isinstance(value, list) else []


def _warning(code: str, message: str, **extra: Any) -> dict:
    item = {"code": code, "message": message}
    item.update(extra)
    return item


def _normalize_relation(value: Any) -> str:
    relation = str(value or "").strip().lower()
    return RELATION_ALIASES.get(relation, relation)


def _normalize_file_type(value: Any) -> str:
    file_type = str(value or "").strip().lower()
    return FILE_TYPE_ALIASES.get(file_type, file_type)


def _normalize_confidence(value: Any) -> str:
    confidence = str(value or "INFERRED").strip().upper()
    return confidence if confidence in ALLOWED_CONFIDENCE else "AMBIGUOUS"


def validate_semantic_graph(fragment: dict) -> dict:
    """Return a normalized semantic fragment plus structured warnings."""
    result = {
        key: deepcopy(fragment.get(key))
        for key in fragment
        if key not in {"nodes", "edges", "hyperedges", "warnings"}
    }
    warnings: list[dict] = []

    nodes: list[dict] = []
    node_ids: set[str] = set()
    for raw in _list_or_empty(fragment.get("nodes")):
        if not isinstance(raw, dict):
            warnings.append(_warning("invalid_node", "Dropped non-object node.", node=raw))
            continue
        node = deepcopy(raw)
        node_id = str(node.get("id") or "").strip()
        if not node_id:
            warnings.append(_warning("missing_node_id", "Dropped node without an id.", node=raw))
            continue
        node["id"] = node_id
        if "file_type" in node:
            node["file_type"] = _normalize_file_type(node.get("file_type"))
        nodes.append(node)
        node_ids.add(node_id)

    edges: list[dict] = []
    for raw in _list_or_empty(fragment.get("edges")):
        if not isinstance(raw, dict):
            warnings.append(_warning("invalid_edge", "Dropped non-object edge.", edge=raw))
            continue
        edge = deepcopy(raw)
        source = str(edge.get("source") or "").strip()
        target = str(edge.get("target") or "").strip()
        relation = _normalize_relation(edge.get("relation"))
        if relation not in ALLOWED_RELATIONS:
            warnings.append(_warning(
                "unknown_relation",
                f"Dropped edge {source} -> {target} with unknown relation {relation!r}.",
                edge=raw,
            ))
            continue
        if source not in node_ids or target not in node_ids:
            warnings.append(_warning(
                "dangling_edge",
                f"Dropped edge {source} -> {target} because one or both nodes are missing.",
                edge=raw,
            ))
            continue
        edge["source"] = source
        edge["target"] = target
        edge["relation"] = relation
        if "confidence" in edge:
            edge["confidence"] = _normalize_confidence(edge.get("confidence"))
        edges.append(edge)

    result["nodes"] = nodes
    result["edges"] = edges
    result["hyperedges"] = _list_or_empty(fragment.get("hyperedges"))
    result["warnings"] = warnings
    return result
