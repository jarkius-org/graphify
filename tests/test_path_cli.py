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
    G.add_node("a", label="A", file_type="code", source_file="a.py", community=7)
    G.add_node("b", label="B", file_type="code", source_file="b.py", community=9)
    G.add_edge("a", "b", relation="calls", confidence="EXTRACTED")
    (out / "graph.json").write_text(json.dumps(json_graph.node_link_data(G, edges="links")))

    monkeypatch.setattr(mainmod, "_check_skill_version", lambda _: None)
    monkeypatch.setattr("graphify.watch._rebuild_code", lambda path, *, force=False, no_viz=False: True)
    monkeypatch.setattr(mainmod.sys, "argv", ["graphify", str(tmp_path), "--wiki"])

    mainmod.main()

    assert (out / "wiki" / "index.md").exists()
    assert (out / "wiki" / "_COMMUNITY_Community_7.md").exists()
    assert (out / "wiki" / "_COMMUNITY_Community_9.md").exists()


def test_path_first_backend_code_only_skips_llm_without_api_key(monkeypatch, tmp_path):
    (tmp_path / "app.py").write_text("def run():\n    return 1\n", encoding="utf-8")

    def fail_if_called(*args, **kwargs):
        raise AssertionError("semantic backend should not run for code-only corpus")

    monkeypatch.delenv("MOONSHOT_API_KEY", raising=False)
    monkeypatch.setattr(mainmod, "_check_skill_version", lambda _: None)
    monkeypatch.setattr("graphify.llm.extract_corpus_parallel", fail_if_called)
    monkeypatch.setattr(mainmod.sys, "argv", ["graphify", str(tmp_path), "--backend", "kimi", "--no-viz"])

    mainmod.main()

    assert (tmp_path / "graphify-out" / "graph.json").exists()


def test_path_first_backend_mixed_corpus_merges_semantic_nodes(monkeypatch, tmp_path):
    (tmp_path / "app.py").write_text("def run():\n    return 1\n", encoding="utf-8")
    (tmp_path / "guide.md").write_text("# Guide\n\nThe runbook explains retries.", encoding="utf-8")
    calls = []

    def fake_semantic(files, *, backend, api_key=None, model=None, root, **kwargs):
        calls.append((files, backend, root))
        return {
            "nodes": [
                {"id": "guide_runbook", "label": "Runbook", "file_type": "doc", "source_file": "guide.md"}
            ],
            "edges": [],
            "hyperedges": [],
            "input_tokens": 10,
            "output_tokens": 5,
        }

    monkeypatch.setenv("MOONSHOT_API_KEY", "test-key")
    monkeypatch.setattr(mainmod, "_check_skill_version", lambda _: None)
    monkeypatch.setattr("graphify.llm.extract_corpus_parallel", fake_semantic)
    monkeypatch.setattr(mainmod.sys, "argv", ["graphify", str(tmp_path), "--backend=kimi", "--no-viz"])

    mainmod.main()

    assert calls
    assert calls[0][1] == "kimi"
    assert [p.name for p in calls[0][0]] == ["guide.md"]
    data = json.loads((tmp_path / "graphify-out" / "graph.json").read_text(encoding="utf-8"))
    semantic = next(node for node in data["nodes"] if node["id"] == "guide_runbook")
    assert semantic["file_type"] == "document"
    assert not (tmp_path / "graphify-out" / "graph.html").exists()


def test_path_first_backend_requires_api_key_for_non_code(monkeypatch, tmp_path, capsys):
    (tmp_path / "guide.md").write_text("# Guide\n\nSemantic content.", encoding="utf-8")

    monkeypatch.delenv("MOONSHOT_API_KEY", raising=False)
    monkeypatch.setattr(mainmod, "_check_skill_version", lambda _: None)
    monkeypatch.setattr(mainmod.sys, "argv", ["graphify", str(tmp_path), "--backend", "kimi", "--no-viz"])

    try:
        mainmod.main()
    except SystemExit as exc:
        assert exc.code == 1
    else:
        raise AssertionError("expected missing API key to exit")

    assert "MOONSHOT_API_KEY" in capsys.readouterr().err


def test_update_command_backend_routes_to_semantic_build(monkeypatch, tmp_path):
    calls = []

    def fake_backend_build(path, *, backend, no_viz=False, wiki=False, force=False):
        calls.append((path, backend, no_viz, wiki, force))

    monkeypatch.setattr(mainmod, "_check_skill_version", lambda _: None)
    monkeypatch.setattr(mainmod, "_run_backend_build", fake_backend_build)
    monkeypatch.setattr(
        mainmod.sys,
        "argv",
        ["graphify", "update", str(tmp_path), "--backend", "claude", "--no-viz", "--wiki", "--force"],
    )

    mainmod.main()

    assert calls == [(tmp_path, "claude", True, True, True)]


def test_dashboard_command_routes_to_web_server(monkeypatch, tmp_path):
    calls = []

    def fake_serve(path, *, host="127.0.0.1", port=8765, graph_dir=None, token=None):
        calls.append((path, host, port, graph_dir, token))

    monkeypatch.setattr(mainmod, "_check_skill_version", lambda _: None)
    monkeypatch.setattr("graphify.web_server.serve_dashboard", fake_serve)
    monkeypatch.setattr(
        mainmod.sys,
        "argv",
        ["graphify", "dashboard", str(tmp_path), "--host", "0.0.0.0", "--port", "9000", "--graph-dir", str(tmp_path / "out")],
    )

    mainmod.main()

    assert calls == [(tmp_path, "0.0.0.0", 9000, str(tmp_path / "out"), None)]


def test_dashboard_command_accepts_fixed_token(monkeypatch, tmp_path):
    calls = []

    def fake_serve(path, *, host="127.0.0.1", port=8765, graph_dir=None, token=None):
        calls.append((path, token))

    monkeypatch.setattr(mainmod, "_check_skill_version", lambda _: None)
    monkeypatch.setattr("graphify.web_server.serve_dashboard", fake_serve)
    monkeypatch.setattr(mainmod.sys, "argv", ["graphify", "web", str(tmp_path), "--token", "dev-token"])

    mainmod.main()

    assert calls == [(tmp_path, "dev-token")]


def test_path_first_backend_uses_semantic_cache_without_api_key(monkeypatch, tmp_path):
    (tmp_path / "guide.md").write_text("# Guide\n\nCached semantic content.", encoding="utf-8")

    def fake_cache(files, root):
        return (
            [{"id": "guide_cached", "label": "Cached Guide", "file_type": "doc", "source_file": "guide.md"}],
            [],
            [],
            [],
        )

    def fail_if_called(*args, **kwargs):
        raise AssertionError("semantic backend should not run when all files are cached")

    monkeypatch.delenv("MOONSHOT_API_KEY", raising=False)
    monkeypatch.setattr(mainmod, "_check_skill_version", lambda _: None)
    monkeypatch.setattr("graphify.cache.check_semantic_cache", fake_cache)
    monkeypatch.setattr("graphify.llm.extract_corpus_parallel", fail_if_called)
    monkeypatch.setattr(mainmod.sys, "argv", ["graphify", str(tmp_path), "--backend", "kimi", "--no-viz"])

    mainmod.main()

    data = json.loads((tmp_path / "graphify-out" / "graph.json").read_text(encoding="utf-8"))
    node = next(n for n in data["nodes"] if n["id"] == "guide_cached")
    assert node["file_type"] == "document"
