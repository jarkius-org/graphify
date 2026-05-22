"""Tests for graphify digest CLI."""
from __future__ import annotations

import json

import networkx as nx
from networkx.readwrite import json_graph

import graphify.__main__ as mainmod


def _write_graphify_out(tmp_path):
    out = tmp_path / "graphify-out"
    out.mkdir()
    graph = nx.Graph()
    graph.add_node("build", label="build_from_json()", source_file="graphify/build.py")
    graph.add_node("cluster", label="cluster()", source_file="graphify/cluster.py")
    graph.add_edge("build", "cluster", relation="feeds", confidence="EXTRACTED")
    (out / "graph.json").write_text(json.dumps(json_graph.node_link_data(graph, edges="links")), encoding="utf-8")
    (out / "GRAPH_REPORT.md").write_text(
        "\n".join(
            [
                "# Graph Report",
                "",
                "## God Nodes (most connected - your core abstractions)",
                "1. `build_from_json()` - 42 edges",
                "",
                "## Surprising Connections (you probably didn't know these)",
                "- `build_from_json()` --feeds--> `cluster()` [EXTRACTED]",
                "",
                "## Suggested Questions",
                "- How does build output affect clustering?",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return out


def test_digest_cli_writes_memory_file(monkeypatch, tmp_path, capsys):
    _write_graphify_out(tmp_path)
    memory_dir = tmp_path / "vault" / "psi" / "memory" / "projects" / "graphify"

    monkeypatch.setattr(mainmod, "_check_skill_version", lambda _: None)
    monkeypatch.setattr(
        mainmod.sys,
        "argv",
        ["graphify", "digest", str(tmp_path), "--memory-dir", str(memory_dir), "--project-slug", "graphify"],
    )

    mainmod.main()

    digest_files = list(memory_dir.glob("*_graphify_graph-digest.md"))
    assert len(digest_files) == 1
    content = digest_files[0].read_text(encoding="utf-8")
    assert 'type: "graphify_digest"' in content
    assert "build_from_json()" in content
    assert "Surprising Connections" in content
    assert "How does build output affect clustering?" in content
    assert "Digest written to" in capsys.readouterr().out


def test_digest_cli_can_write_psi_outbox_note(monkeypatch, tmp_path):
    _write_graphify_out(tmp_path)
    memory_dir = tmp_path / "memory"
    outbox = tmp_path / "psi" / "outbox"

    monkeypatch.setattr(mainmod, "_check_skill_version", lambda _: None)
    monkeypatch.setattr(
        mainmod.sys,
        "argv",
        [
            "graphify",
            "digest",
            str(tmp_path),
            "--memory-dir",
            str(memory_dir),
            "--psi-outbox",
            str(outbox),
            "--project-slug",
            "graphify",
        ],
    )

    mainmod.main()

    notes = list(outbox.glob("*_graphify_graph-digest.md"))
    assert len(notes) == 1
    assert "markdown digest remains canonical" in notes[0].read_text(encoding="utf-8")


def test_digest_cli_default_memory_dir_is_project_graphify_out(monkeypatch, tmp_path):
    _write_graphify_out(tmp_path)
    monkeypatch.chdir(tmp_path.parent)
    monkeypatch.setattr(mainmod, "_check_skill_version", lambda _: None)
    monkeypatch.setattr(mainmod.sys, "argv", ["graphify", "digest", str(tmp_path)])

    mainmod.main()

    digest_files = list((tmp_path / "graphify-out" / "memory").glob("*_graph-digest.md"))
    assert len(digest_files) == 1


def test_digest_cli_missing_graph_exits(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(mainmod, "_check_skill_version", lambda _: None)
    monkeypatch.setattr(mainmod.sys, "argv", ["graphify", "digest", str(tmp_path)])

    try:
        mainmod.main()
    except SystemExit as exc:
        assert exc.code == 1
    else:
        raise AssertionError("expected digest to exit for missing graph")

    assert "graph file not found" in capsys.readouterr().err
