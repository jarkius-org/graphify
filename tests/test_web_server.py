import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from graphify.web_server import create_server, make_token, render_markdown


def write_graphify_out(project: Path) -> None:
    out = project / "graphify-out"
    wiki = out / "wiki"
    wiki.mkdir(parents=True)
    (out / "graph.json").write_text(json.dumps({
        "nodes": [{"id": "A", "label": "Alpha", "community": 0}],
        "links": [{"source": "A", "target": "B", "type": "related"}],
    }), encoding="utf-8")
    (out / "GRAPH_REPORT.md").write_text("# Graph Report\n\nUseful [[_COMMUNITY_Community_0|Alpha]] summary", encoding="utf-8")
    (wiki / "index.md").write_text("# Knowledge Graph Index\n\n- [[includes/jpgraph]]\n- [[Alpha]]", encoding="utf-8")
    (wiki / "Alpha.md").write_text("# Alpha\n\nAlpha details", encoding="utf-8")
    (wiki / "includes-jpgraph.md").write_text("# includes/jpgraph\n\nGraph library details", encoding="utf-8")


@pytest.fixture
def running_dashboard(tmp_path):
    write_graphify_out(tmp_path)
    token = make_token()
    server = create_server(tmp_path, host="127.0.0.1", port=0, token=token)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"
    try:
        yield base_url, token
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def test_graph_api_requires_token(running_dashboard):
    base_url, _token = running_dashboard
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(f"{base_url}/api/graph", timeout=5)
    assert exc.value.code == 401


def test_graph_api_accepts_authorization_bearer(running_dashboard):
    base_url, token = running_dashboard
    request = urllib.request.Request(
        f"{base_url}/api/graph",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        data = json.loads(response.read().decode("utf-8"))
    assert data["nodes"][0]["label"] == "Alpha"


def test_graph_api_returns_project_graph_with_token(running_dashboard):
    base_url, token = running_dashboard
    data = get_json(f"{base_url}/api/graph?token={token}")
    assert data["nodes"][0]["label"] == "Alpha"
    assert data["links"][0]["type"] == "related"


def test_health_route_reports_available_outputs(running_dashboard):
    base_url, token = running_dashboard
    data = get_json(f"{base_url}/api/health?token={token}")
    assert data["graph"]["exists"] is True
    assert data["graph"]["nodes"] == 1
    assert data["graph"]["links"] == 1
    assert data["report"]["exists"] is True
    assert data["wiki"]["exists"] is True


def test_report_route_returns_rendered_wiki_link_html(running_dashboard):
    base_url, token = running_dashboard
    data = get_json(f"{base_url}/api/report?token={token}")
    assert data["markdown"].startswith("# Graph Report")
    assert "<h1>Graph Report</h1>" in data["html"]
    assert "Alpha" in data["html"]
    assert 'href="/wiki/_COMMUNITY_Community_0?token=' in data["html"]
    assert "_COMMUNITY_Community_0|Alpha" not in data["html"]


def test_wiki_index_and_page_routes_return_rendered_html(running_dashboard):
    base_url, token = running_dashboard
    index = get_json(f"{base_url}/api/wiki?token={token}")
    assert {page["name"] for page in index["pages"]} >= {"index", "Alpha", "includes-jpgraph"}
    assert [page["name"] for page in index["pages"][:3]] == ["index", "includes-jpgraph", "Alpha"]
    page = get_json(f"{base_url}/api/wiki/Alpha?token={token}")
    assert page["name"] == "Alpha"
    assert "<h1>Alpha</h1>" in page["html"]
    slash_page = get_json(f"{base_url}/api/wiki/includes%2Fjpgraph?token={token}")
    assert slash_page["name"] == "includes/jpgraph"
    assert "<h1>includes/jpgraph</h1>" in slash_page["html"]


def test_wiki_page_rejects_path_traversal(running_dashboard):
    base_url, token = running_dashboard
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(f"{base_url}/api/wiki/../graph?token={token}", timeout=5)
    assert exc.value.code in {400, 404}


def test_markdown_renderer_escapes_html_and_links_wiki_words():
    html = render_markdown("# <script>\n\nSee [[Alpha]] and <b>raw</b>")
    assert "&lt;script&gt;" in html
    assert "&lt;b&gt;raw&lt;/b&gt;" in html
    assert 'href="/wiki/Alpha"' in html


def test_markdown_renderer_can_preserve_token_on_wiki_links():
    html = render_markdown("See [[Alpha Page|Alpha]]", token="dev token")
    assert 'href="/wiki/Alpha_Page?token=dev%20token"' in html


def test_markdown_renderer_links_slash_labels_as_safe_filenames():
    html = render_markdown("See [[_COMMUNITY_Community 3|includes/jpgraph]]", token="dev-token")
    assert 'href="/wiki/_COMMUNITY_Community_3?token=dev-token"' in html
    assert "[[_COMMUNITY_" not in html


def test_markdown_renderer_formats_bold_and_code():
    html = render_markdown("Use **AssetController.php** from `app/Controllers/AssetController.php`")
    assert "<strong>AssetController.php</strong>" in html
    assert "<code>app/Controllers/AssetController.php</code>" in html
