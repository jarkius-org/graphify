from __future__ import annotations

import json

import networkx as nx
from networkx.readwrite import json_graph

import graphify.__main__ as mainmod
from graphify.layers import annotate_layers, detect_layer
from graphify.tour import generate_tour


def test_detect_layer_uses_path_rules():
    assert detect_layer("app/api/routes.py") == "API"
    assert detect_layer("src/services/auth.py") == "Service"
    assert detect_layer("graphify/models/user.py") == "Data"
    assert detect_layer("ui/components/Button.tsx") == "UI"
    assert detect_layer("tests/test_auth.py") == "Tests"
    assert detect_layer("config/settings.py") == "Configuration"
    assert detect_layer("docs/how-it-works.md") == "Documentation"
    assert detect_layer("src/helpers.py") == "Utility"


def test_annotate_layers_keeps_communities_separate():
    G = nx.Graph()
    G.add_node("api", label="API", source_file="app/api/routes.py", community=7)

    layers = annotate_layers(G)

    assert layers == {"api": "API"}
    assert G.nodes["api"]["community"] == 7
    assert G.nodes["api"]["layer"] == "API"


def test_generate_tour_orders_dependency_flow_for_dag():
    G = nx.DiGraph()
    G.add_node("api", label="Routes", source_file="app/api/routes.py")
    G.add_node("service", label="AuthService", source_file="src/services/auth.py")
    G.add_node("data", label="UserRepository", source_file="src/models/user.py")
    G.add_edge("api", "service", relation="calls")
    G.add_edge("service", "data", relation="uses")

    tour = generate_tour(G)

    assert [item["id"] for item in tour] == ["api", "service", "data"]
    assert [item["layer"] for item in tour] == ["API", "Service", "Data"]


def test_generate_tour_handles_cycles_with_stable_fallback():
    G = nx.DiGraph()
    G.add_node("b", label="B", source_file="src/services/b.py")
    G.add_node("a", label="A", source_file="src/services/a.py")
    G.add_edge("a", "b")
    G.add_edge("b", "a")

    tour = generate_tour(G)

    assert [item["id"] for item in tour] == ["a", "b"]


def test_tour_cli_prints_start_here(monkeypatch, tmp_path, capsys):
    G = nx.DiGraph()
    G.add_node("api", label="Routes", source_file="app/api/routes.py")
    G.add_node("service", label="AuthService", source_file="src/services/auth.py")
    G.add_edge("api", "service", relation="calls")
    graph_path = tmp_path / "graph.json"
    graph_path.write_text(json.dumps(json_graph.node_link_data(G, edges="links")), encoding="utf-8")

    monkeypatch.setattr(mainmod, "_check_skill_version", lambda _: None)
    monkeypatch.setattr(mainmod.sys, "argv", ["graphify", "tour", "--graph", str(graph_path)])

    mainmod.main()

    out = capsys.readouterr().out
    assert "Start here" in out
    assert "Routes" in out
    assert "AuthService" in out
