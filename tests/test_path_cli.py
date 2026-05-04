"""Tests for path-first CLI compatibility."""
from __future__ import annotations

import json

import networkx as nx
from networkx.readwrite import json_graph

import graphify.__main__ as mainmod


def test_path_first_invocation_rebuilds_code(monkeypatch, tmp_path, capsys):
    calls = []

    def fake_rebuild(path, *, force=False, no_viz=False):
        calls.append((path, force, no_viz))
        return True

    monkeypatch.setattr(mainmod, "_check_skill_version", lambda _: None)
    monkeypatch.setattr("graphify.watch._rebuild_code", fake_rebuild)
    monkeypatch.setattr(mainmod.sys, "argv", ["graphify", str(tmp_path)])

    mainmod.main()

    assert calls == [(tmp_path, False, False)]
    assert "Code graph updated" in capsys.readouterr().out


def test_path_first_invocation_accepts_update_force_and_no_viz(monkeypatch, tmp_path):
    calls = []

    def fake_rebuild(path, *, force=False, no_viz=False):
        calls.append((path, force, no_viz))
        return True

    monkeypatch.setattr(mainmod, "_check_skill_version", lambda _: None)
    monkeypatch.setattr("graphify.watch._rebuild_code", fake_rebuild)
    monkeypatch.setattr(
        mainmod.sys,
        "argv",
        ["graphify", str(tmp_path), "--update", "--force", "--no-viz"],
    )

    mainmod.main()

    assert calls == [(tmp_path, True, True)]


def test_path_first_cluster_only_routes_existing_graph(monkeypatch, tmp_path):
    calls = []

    def fake_cluster(path, *, no_viz=False, min_community_size=3):
        calls.append((path, no_viz, min_community_size))

    monkeypatch.setattr(mainmod, "_check_skill_version", lambda _: None)
    monkeypatch.setattr(mainmod, "_run_cluster_only", fake_cluster)
    monkeypatch.setattr(
        mainmod.sys,
        "argv",
        ["graphify", str(tmp_path), "--cluster-only", "--no-viz"],
    )

    mainmod.main()

    assert calls == [(tmp_path, True, 3)]


def test_path_first_wiki_generates_markdown_wiki(monkeypatch, tmp_path):
    out = tmp_path / "graphify-out"
    out.mkdir()

    G = nx.Graph()
    G.add_node("a", label="A", file_type="code", source_file="a.py")
    G.add_node("b", label="B", file_type="code", source_file="b.py")
    G.add_edge("a", "b", relation="calls", confidence="EXTRACTED")
    (out / "graph.json").write_text(json.dumps(json_graph.node_link_data(G, edges="links")))

    monkeypatch.setattr(mainmod, "_check_skill_version", lambda _: None)
    monkeypatch.setattr("graphify.watch._rebuild_code", lambda path, *, force=False, no_viz=False: True)
    monkeypatch.setattr(mainmod.sys, "argv", ["graphify", str(tmp_path), "--wiki"])

    mainmod.main()

    assert (out / "wiki" / "index.md").exists()
