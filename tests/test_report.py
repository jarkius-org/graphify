import json
from pathlib import Path
from graphify.build import build_from_json
from graphify.cluster import cluster, score_all
from graphify.analyze import god_nodes, surprising_connections
from graphify.report import generate

FIXTURES = Path(__file__).parent / "fixtures"

def make_inputs():
    extraction = json.loads((FIXTURES / "extraction.json").read_text())
    G = build_from_json(extraction)
    communities = cluster(G)
    cohesion = score_all(G, communities)
    labels = {cid: f"Community {cid}" for cid in communities}
    gods = god_nodes(G)
    surprises = surprising_connections(G)
    detection = {"total_files": 4, "total_words": 62400, "needs_graph": True, "warning": None}
    tokens = {"input": extraction["input_tokens"], "output": extraction["output_tokens"]}
    return G, communities, cohesion, labels, gods, surprises, detection, tokens

def test_report_contains_header():
    G, communities, cohesion, labels, gods, surprises, detection, tokens = make_inputs()
    report = generate(G, communities, cohesion, labels, gods, surprises, detection, tokens, "./project")
    assert "# Graph Report" in report

def test_report_contains_corpus_check():
    G, communities, cohesion, labels, gods, surprises, detection, tokens = make_inputs()
    report = generate(G, communities, cohesion, labels, gods, surprises, detection, tokens, "./project")
    assert "## Corpus Check" in report

def test_report_contains_god_nodes():
    G, communities, cohesion, labels, gods, surprises, detection, tokens = make_inputs()
    report = generate(G, communities, cohesion, labels, gods, surprises, detection, tokens, "./project")
    assert "## God Nodes" in report

def test_report_contains_surprising_connections():
    G, communities, cohesion, labels, gods, surprises, detection, tokens = make_inputs()
    report = generate(G, communities, cohesion, labels, gods, surprises, detection, tokens, "./project")
    assert "## Surprising Connections" in report

def test_report_contains_communities():
    G, communities, cohesion, labels, gods, surprises, detection, tokens = make_inputs()
    report = generate(G, communities, cohesion, labels, gods, surprises, detection, tokens, "./project")
    assert "## Communities" in report

def test_report_contains_ambiguous_section():
    G, communities, cohesion, labels, gods, surprises, detection, tokens = make_inputs()
    report = generate(G, communities, cohesion, labels, gods, surprises, detection, tokens, "./project")
    assert "## Ambiguous Edges" in report

def test_report_shows_token_cost():
    G, communities, cohesion, labels, gods, surprises, detection, tokens = make_inputs()
    report = generate(G, communities, cohesion, labels, gods, surprises, detection, tokens, "./project")
    assert "Token cost" in report
    assert "1,200" in report


def test_report_shows_indexed_source_roots():
    G, communities, cohesion, labels, gods, surprises, detection, tokens = make_inputs()
    detection = {
        **detection,
        "files": {
            "code": ["graphify/report.py", "graphify/watch.py", "tests/test_report.py"],
            "document": ["README.md"],
        },
    }
    report = generate(G, communities, cohesion, labels, gods, surprises, detection, tokens, "./project")
    assert "Indexed roots: graphify (2), README.md (1), tests (1)" in report

def test_report_shows_raw_cohesion_scores():
    G, communities, cohesion, labels, gods, surprises, detection, tokens = make_inputs()
    report = generate(G, communities, cohesion, labels, gods, surprises, detection, tokens, "./project", min_community_size=1)
    assert "Cohesion:" in report
    assert "✓" not in report
    assert "⚠" not in report


def test_report_caps_community_hubs_and_uses_content_labels():
    import networkx as nx

    G = nx.Graph()
    communities = {}
    labels = {}
    cohesion = {}
    for cid in range(25):
        nodes = []
        for idx in range(3):
            node = f"node_{cid}_{idx}"
            G.add_node(node, label=f"Thing {cid}.{idx}", source_file=f"src/domain_{cid}/module.py")
            nodes.append(node)
        G.add_edge(nodes[0], nodes[1], confidence="EXTRACTED")
        G.add_edge(nodes[1], nodes[2], confidence="EXTRACTED")
        communities[cid] = nodes
        labels[cid] = f"Community {cid}"
        cohesion[cid] = 1.0

    report = generate(
        G,
        communities,
        cohesion,
        labels,
        [],
        [],
        {"total_files": 25, "total_words": 100_000, "needs_graph": True, "warning": None},
        {"input": 0, "output": 0},
        "./project",
        min_community_size=1,
    )

    hub_section = report.split("## God Nodes", 1)[0]
    assert hub_section.count("[[_COMMUNITY_") == 20
    assert "5 smaller communities" in hub_section
    assert "[[_COMMUNITY_Community_0|src/domain_0]]" in hub_section
    assert "`Thing 0.1`" in hub_section


def test_report_summary_distinguishes_concept_communities_from_total_clusters():
    G, communities, cohesion, labels, gods, surprises, detection, tokens = make_inputs()
    report = generate(G, communities, cohesion, labels, gods, surprises, detection, tokens, "./project")
    assert "concept communities" in report
    assert "total clusters" in report
