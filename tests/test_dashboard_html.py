import json

from graphify.dashboard_html import DASHBOARD_HTML, remove_dashboard_html, write_dashboard_html


def test_write_dashboard_html_embeds_graph_report_and_wiki(tmp_path):
    out = tmp_path / "graphify-out"
    wiki = out / "wiki"
    wiki.mkdir(parents=True)
    (out / "graph.json").write_text(
        json.dumps({
            "nodes": [{"id": "A", "label": "Alpha", "community": 1}],
            "links": [{"source": "A", "target": "B"}],
        }),
        encoding="utf-8",
    )
    (out / "GRAPH_REPORT.md").write_text("# Graph Report\n\nUseful [[_COMMUNITY_Community_0|Alpha]] summary", encoding="utf-8")
    (wiki / "index.md").write_text("# Index\n\n- [[Alpha]]", encoding="utf-8")

    target = write_dashboard_html(out)

    assert target == out / DASHBOARD_HTML
    html = target.read_text(encoding="utf-8")
    assert "Graphify Dashboard" in html
    assert '"label":"Alpha"' in html
    assert "[[_COMMUNITY_Community_0|Alpha]]" in html
    assert '"title":"Index"' in html
    assert "renderMarkdown(data.report" in html
    assert "splitWikiLink" in html
    assert "openWikiPage" in html
    assert 'id="report-text" class="panel markdown"' in html


def test_write_dashboard_html_escapes_script_breakouts(tmp_path):
    out = tmp_path / "graphify-out"
    out.mkdir()
    (out / "graph.json").write_text(
        json.dumps({"nodes": [{"id": "bad", "label": "</script><script>alert(1)</script>"}], "links": []}),
        encoding="utf-8",
    )

    html = write_dashboard_html(out).read_text(encoding="utf-8")

    assert "</script><script>alert(1)</script>" not in html
    assert "\\u003c/script\\u003e" in html


def test_remove_dashboard_html_is_idempotent(tmp_path):
    out = tmp_path / "graphify-out"
    out.mkdir()
    target = write_dashboard_html(out)
    assert target.exists()

    remove_dashboard_html(out)
    remove_dashboard_html(out)

    assert not target.exists()
