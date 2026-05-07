"""Tests for graphify.wiki — Wikipedia-style article generation."""
import pytest
from pathlib import Path
import networkx as nx
from graphify.wiki import to_wiki, _index_md, _community_article, _god_node_article


def _make_graph():
    G = nx.Graph()
    G.add_node("n1", label="parse", file_type="code", source_file="parser.py", community=0)
    G.add_node("n2", label="validate", file_type="code", source_file="parser.py", community=0)
    G.add_node("n3", label="render", file_type="code", source_file="renderer.py", community=1)
    G.add_node("n4", label="stream", file_type="code", source_file="renderer.py", community=1)
    G.add_edge("n1", "n2", relation="calls", confidence="EXTRACTED", weight=1.0)
    G.add_edge("n1", "n3", relation="references", confidence="INFERRED", weight=1.0)
    G.add_edge("n3", "n4", relation="calls", confidence="EXTRACTED", weight=1.0)
    return G


COMMUNITIES = {0: ["n1", "n2"], 1: ["n3", "n4"]}
LABELS = {0: "Parsing Layer", 1: "Rendering Layer"}
COHESION = {0: 0.85, 1: 0.72}
GOD_NODES = [{"id": "n1", "label": "parse", "degree": 2}]


def test_to_wiki_writes_index(tmp_path):
    G = _make_graph()
    n = to_wiki(G, COMMUNITIES, tmp_path, community_labels=LABELS, cohesion=COHESION, god_nodes_data=GOD_NODES)
    assert (tmp_path / "index.md").exists()


def test_to_wiki_uses_content_labels_for_generic_communities(tmp_path):
    G = nx.Graph()
    G.add_node("a", label="Alpha", source_file="src/core/a.py", community=0)
    G.add_node("b", label="Beta", source_file="src/core/b.py", community=0)
    G.add_edge("a", "b", confidence="EXTRACTED")

    to_wiki(G, {0: ["a", "b"]}, tmp_path, community_labels={0: "Community 0"})

    index = (tmp_path / "index.md").read_text(encoding="utf-8")
    assert "[[_COMMUNITY_Community_0|src/core]]" in index
    assert (tmp_path / "_COMMUNITY_Community_0.md").exists()


def test_to_wiki_returns_article_count(tmp_path):
    G = _make_graph()
    # 2 communities + 1 god node = 3
    n = to_wiki(G, COMMUNITIES, tmp_path, community_labels=LABELS, cohesion=COHESION, god_nodes_data=GOD_NODES)
    assert n == 3


def test_to_wiki_community_articles_created(tmp_path):
    G = _make_graph()
    to_wiki(G, COMMUNITIES, tmp_path, community_labels=LABELS)
    assert (tmp_path / "_COMMUNITY_Community_0.md").exists()
    assert (tmp_path / "_COMMUNITY_Community_1.md").exists()


def test_to_wiki_god_node_article_created(tmp_path):
    G = _make_graph()
    to_wiki(G, COMMUNITIES, tmp_path, community_labels=LABELS, god_nodes_data=GOD_NODES)
    assert (tmp_path / "_GOD_parse.md").exists()


def test_index_links_all_communities(tmp_path):
    G = _make_graph()
    to_wiki(G, COMMUNITIES, tmp_path, community_labels=LABELS)
    index = (tmp_path / "index.md").read_text()
    assert "[[_COMMUNITY_Community_0|Parsing Layer]]" in index
    assert "[[_COMMUNITY_Community_1|Rendering Layer]]" in index


def test_index_lists_god_nodes(tmp_path):
    G = _make_graph()
    to_wiki(G, COMMUNITIES, tmp_path, community_labels=LABELS, god_nodes_data=GOD_NODES)
    index = (tmp_path / "index.md").read_text()
    assert "[[_GOD_parse|parse]]" in index
    assert "2 connections" in index


def test_community_article_has_cross_links(tmp_path):
    G = _make_graph()
    to_wiki(G, COMMUNITIES, tmp_path, community_labels=LABELS)
    parsing = (tmp_path / "_COMMUNITY_Community_0.md").read_text()
    # n1 (parsing) references n3 (rendering) → cross-community link
    assert "[[_COMMUNITY_Community_1|Rendering Layer]]" in parsing


def test_community_article_shows_cohesion(tmp_path):
    G = _make_graph()
    to_wiki(G, COMMUNITIES, tmp_path, community_labels=LABELS, cohesion=COHESION)
    parsing = (tmp_path / "_COMMUNITY_Community_0.md").read_text()
    assert "cohesion 0.85" in parsing


def test_community_article_has_audit_trail(tmp_path):
    G = _make_graph()
    to_wiki(G, COMMUNITIES, tmp_path, community_labels=LABELS)
    parsing = (tmp_path / "_COMMUNITY_Community_0.md").read_text()
    assert "EXTRACTED" in parsing
    assert "INFERRED" in parsing


def test_god_node_article_has_connections(tmp_path):
    G = _make_graph()
    to_wiki(G, COMMUNITIES, tmp_path, community_labels=LABELS, god_nodes_data=GOD_NODES)
    article = (tmp_path / "_GOD_parse.md").read_text()
    assert "`validate`" in article or "`render`" in article


def test_god_node_article_links_community(tmp_path):
    G = _make_graph()
    to_wiki(G, COMMUNITIES, tmp_path, community_labels=LABELS, god_nodes_data=GOD_NODES)
    article = (tmp_path / "_GOD_parse.md").read_text()
    assert "[[_COMMUNITY_Community_0|Parsing Layer]]" in article


def test_to_wiki_skips_missing_god_node_ids(tmp_path):
    """God node with bad ID should not crash."""
    G = _make_graph()
    bad_gods = [{"id": "nonexistent", "label": "ghost", "degree": 99}]
    n = to_wiki(G, COMMUNITIES, tmp_path, community_labels=LABELS, god_nodes_data=bad_gods)
    # 2 communities + 0 god nodes (nonexistent skipped) = 2
    assert n == 2


def test_to_wiki_no_labels_uses_fallback(tmp_path):
    G = _make_graph()
    to_wiki(G, COMMUNITIES, tmp_path)  # no labels
    assert (tmp_path / "_COMMUNITY_Community_0.md").exists()
    assert (tmp_path / "_COMMUNITY_Community_1.md").exists()


def test_article_navigation_footer(tmp_path):
    G = _make_graph()
    to_wiki(G, COMMUNITIES, tmp_path, community_labels=LABELS)
    article = (tmp_path / "_COMMUNITY_Community_0.md").read_text()
    assert "[[index]]" in article


def test_community_article_truncation_notice(tmp_path):
    """Communities with more than 25 nodes show a truncation notice."""
    G = nx.Graph()
    nodes = [f"n{i}" for i in range(30)]
    for nid in nodes:
        G.add_node(nid, label=f"concept_{nid}", file_type="code", source_file="a.py", community=0)
    for i in range(len(nodes) - 1):
        G.add_edge(nodes[i], nodes[i + 1], relation="calls", confidence="EXTRACTED", weight=1.0)
    communities = {0: nodes}
    to_wiki(G, communities, tmp_path, community_labels={0: "Big Community"})
    article = (tmp_path / "_COMMUNITY_Community_0.md").read_text()
    assert "and 5 more nodes" in article


def test_duplicate_community_labels_get_stable_distinct_targets(tmp_path):
    G = nx.Graph()
    G.add_node("a", label="Alpha", source_file="a.py", community=0)
    G.add_node("b", label="Beta", source_file="b.py", community=1)
    G.add_edge("a", "b", relation="references", confidence="EXTRACTED")

    to_wiki(G, {0: ["a"], 1: ["b"]}, tmp_path, community_labels={0: "Same", 1: "Same"})

    index = (tmp_path / "index.md").read_text(encoding="utf-8")
    assert "[[_COMMUNITY_Community_0|Same - Alpha]]" in index
    assert "[[_COMMUNITY_Community_1|Same - Beta]]" in index
    assert (tmp_path / "_COMMUNITY_Community_0.md").exists()
    assert (tmp_path / "_COMMUNITY_Community_1.md").exists()
