"""Architecture layer detection for Graphify nodes."""
from __future__ import annotations

from pathlib import Path

import networkx as nx


LAYER_ORDER = ["API", "Service", "Data", "UI", "Utility", "Tests", "Configuration", "Documentation"]


def _parts(path: str) -> list[str]:
    return [part.lower() for part in Path(path.replace("\\", "/")).parts]


def detect_layer(source_file: str | None) -> str:
    """Return a deterministic architecture layer from a node source path."""
    if not source_file:
        return "Utility"
    path = source_file.replace("\\", "/").lower()
    parts = _parts(path)
    name = parts[-1] if parts else path

    if "tests" in parts or name.startswith("test_") or name.endswith("_test.py"):
        return "Tests"
    if any(part in {"config", "configs", "settings"} for part in parts) or name in {
        "pyproject.toml", "package.json", "tsconfig.json", "dockerfile",
    }:
        return "Configuration"
    if "docs" in parts or name.endswith((".md", ".rst", ".txt")):
        return "Documentation"
    if any(part in {"api", "routes", "controllers", "endpoints"} for part in parts):
        return "API"
    if any(part in {"service", "services", "usecases", "interactors"} for part in parts):
        return "Service"
    if any(part in {"data", "db", "database", "models", "repositories", "repository", "migrations"} for part in parts):
        return "Data"
    if any(part in {"ui", "views", "components", "pages", "frontend"} for part in parts) or name.endswith((".tsx", ".jsx", ".vue", ".svelte")):
        return "UI"
    return "Utility"


def annotate_layers(G: nx.Graph) -> dict[str, str]:
    """Annotate graph nodes with layer while leaving community assignments intact."""
    layers: dict[str, str] = {}
    for nid, data in G.nodes(data=True):
        layer = detect_layer(data.get("source_file"))
        data["layer"] = layer
        layers[nid] = layer
    return layers
