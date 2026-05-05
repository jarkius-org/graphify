from __future__ import annotations

import json

import networkx as nx
from networkx.readwrite import json_graph

import graphify.__main__ as mainmod
from graphify.impact import analyze_impact


def _impact_graph() -> nx.Graph:
    G = nx.Graph()
    G.add_node("api_file", label="routes.py", source_file="app/api/routes.py", type="file", community=1)
    G.add_node("handler", label="handle_login", source_file="app/api/routes.py", type="function", community=1)
    G.add_node("service", label="AuthService", source_file="src/services/auth.py", type="class", community=2)
    G.add_node("data", label="UserRepository", source_file="src/models/user.py", type="class", community=3)
    G.add_edge("api_file", "handler", relation="contains")
    G.add_edge("handler", "service", relation="calls")
    G.add_edge("service", "data", relation="uses")
    return G


def test_analyze_impact_maps_changed_files_to_nodes_and_neighbors():
    result = analyze_impact(_impact_graph(), ["app/api/routes.py"])

    assert result["changed_nodes"] == ["api_file", "handler"]
    assert result["affected_nodes"] == ["service"]
    assert result["affected_edges"] == [
        {"source": "handler", "target": "service", "relation": "calls"}
    ]
    assert result["communities"] == [1, 2]
    assert result["layers"] == ["API", "Service"]


def test_analyze_impact_reports_unmapped_files_and_empty_diff():
    result = analyze_impact(_impact_graph(), ["missing.py"])

    assert result["changed_nodes"] == []
    assert result["affected_nodes"] == []
    assert result["unmapped_files"] == ["missing.py"]
    assert "graphify update ." in result["recommendation"]


def test_diff_cli_files_prints_impact(monkeypatch, tmp_path, capsys):
    graph_path = tmp_path / "graph.json"
    graph_path.write_text(json.dumps(json_graph.node_link_data(_impact_graph(), edges="links")), encoding="utf-8")

    monkeypatch.setattr(mainmod, "_check_skill_version", lambda _: None)
    monkeypatch.setattr(
        mainmod.sys,
        "argv",
        ["graphify", "diff", "--graph", str(graph_path), "--files", "app/api/routes.py"],
    )

    mainmod.main()

    out = capsys.readouterr().out
    assert "Changed nodes: 2" in out
    assert "Affected nodes: 1" in out
    assert "AuthService" in out
