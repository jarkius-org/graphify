from __future__ import annotations

import html
import json
import re
import socket
import secrets
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

from graphify.wiki import _safe_filename

DEFAULT_PORT = 8765


class DashboardServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, server_address, handler_class, *, project_path: Path, graph_dir: Path, token: str):
        super().__init__(server_address, handler_class)
        self.project_path = project_path
        self.graph_dir = graph_dir
        self.token = token


def make_token() -> str:
    return secrets.token_urlsafe(24)


def create_server(project_path: str | Path, *, host: str = "127.0.0.1", port: int = DEFAULT_PORT, token: str | None = None, graph_dir: str | Path | None = None) -> DashboardServer:
    project = Path(project_path).resolve()
    out_dir = Path(graph_dir).resolve() if graph_dir else project / "graphify-out"
    return DashboardServer((host, port), DashboardHandler, project_path=project, graph_dir=out_dir, token=token or make_token())


def serve_dashboard(project_path: str | Path, *, host: str = "127.0.0.1", port: int = DEFAULT_PORT, graph_dir: str | Path | None = None, token: str | None = None) -> None:
    server = create_server(project_path, host=host, port=port, graph_dir=graph_dir, token=token)
    url = f"http://{host}:{server.server_port}/?token={server.token}"
    print(f"Dashboard: {url}", flush=True)
    print(f"Viewing: {server.graph_dir / 'graph.json'}", flush=True)
    wiki_index = server.graph_dir / "wiki" / "index.md"
    if wiki_index.exists():
        print(f"Wiki: {wiki_index}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard stopped.", file=sys.stderr)
    finally:
        server.server_close()


def render_markdown(markdown: str, *, token: str | None = None) -> str:
    blocks: list[str] = []
    in_list = False
    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        if not line:
            if in_list:
                blocks.append("</ul>")
                in_list = False
            continue
        if line.startswith("#"):
            if in_list:
                blocks.append("</ul>")
                in_list = False
            level = min(len(line) - len(line.lstrip("#")), 6)
            text = line[level:].strip()
            blocks.append(f"<h{level}>{_render_inline(text, token=token)}</h{level}>")
        elif line.startswith("- "):
            if not in_list:
                blocks.append("<ul>")
                in_list = True
            blocks.append(f"<li>{_render_inline(line[2:].strip(), token=token)}</li>")
        else:
            if in_list:
                blocks.append("</ul>")
                in_list = False
            blocks.append(f"<p>{_render_inline(line, token=token)}</p>")
    if in_list:
        blocks.append("</ul>")
    return "\n".join(blocks)


def _render_inline(text: str, *, token: str | None = None) -> str:
    escaped = html.escape(text)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    return _link_wiki_words(escaped, token=token)


def _link_wiki_words(text: str, *, token: str | None = None) -> str:
    out = []
    rest = text
    while "[[" in rest and "]]" in rest:
        before, tail = rest.split("[[", 1)
        target, after = tail.split("]]", 1)
        raw_target = html.unescape(target)
        page_target, display = _split_wiki_target(raw_target)
        safe = _safe_page_name(page_target)
        out.append(before)
        if safe:
            href = f"/wiki/{quote(_safe_filename(safe))}"
            if token:
                href = f"{href}?token={quote(token)}"
            out.append(f'<a href="{html.escape(href)}">{html.escape(display)}</a>')
        else:
            out.append(f"[[{target}]]")
        rest = after
    out.append(rest)
    return "".join(out)


def _split_wiki_target(raw_target: str) -> tuple[str, str]:
    target, sep, display = raw_target.partition("|")
    display = display if sep else target
    return target, display


def _safe_page_name(name: str) -> str | None:
    clean = unquote(name).strip().replace("\\", "/")
    if "|" in clean:
        clean = clean.split("|", 1)[0].strip()
    if not clean or clean in {".", ".."} or clean.endswith(".md"):
        return None
    if any(part in {".", ".."} for part in clean.split("/")):
        return None
    return clean


class DashboardHandler(BaseHTTPRequestHandler):
    server: DashboardServer

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        if path == "/":
            self._send_asset("index.html", "text/html; charset=utf-8")
        elif path == "/app.js":
            self._send_asset("app.js", "text/javascript; charset=utf-8")
        elif path == "/styles.css":
            self._send_asset("styles.css", "text/css; charset=utf-8")
        elif path.startswith("/wiki/"):
            name = _safe_page_name(path.removeprefix("/wiki/"))
            if not name:
                self._send_error(404, "wiki page not found")
                return
            self._send_wiki_page_html(name, query)
        elif path.startswith("/api/"):
            if not self._authorized(query):
                self._send_error(401, "missing or invalid token")
                return
            self._handle_api(path, query)
        else:
            self._send_error(404, "not found")

    def log_message(self, format: str, *args) -> None:
        return

    def _authorized(self, query: dict[str, list[str]]) -> bool:
        if query.get("token", [None])[0] == self.server.token:
            return True
        auth = self.headers.get("Authorization", "")
        return auth == f"Bearer {self.server.token}"

    def _handle_api(self, path: str, query: dict[str, list[str]]) -> None:
        if path == "/api/graph":
            self._send_file_json(self.server.graph_dir / "graph.json")
        elif path == "/api/report":
            report = self.server.graph_dir / "GRAPH_REPORT.md"
            if not report.exists():
                self._send_error(404, "report not found")
                return
            markdown = report.read_text(encoding="utf-8")
            self._send_json({"markdown": markdown, "html": render_markdown(markdown, token=query.get("token", [None])[0])})
        elif path == "/api/wiki":
            self._send_wiki_index()
        elif path.startswith("/api/wiki/"):
            name = _safe_page_name(path.removeprefix("/api/wiki/"))
            if not name:
                self._send_error(400, "invalid wiki page")
                return
            self._send_wiki_page_json(name, token=query.get("token", [None])[0])
        elif path == "/api/health":
            self._send_health()
        else:
            self._send_error(404, "api route not found")

    def _send_asset(self, name: str, content_type: str) -> None:
        try:
            data = resources.files("graphify.web").joinpath(name).read_bytes()
        except FileNotFoundError:
            self._send_error(404, "asset not found")
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self._write_body(data)

    def _send_file_json(self, path: Path) -> None:
        if not path.exists():
            self._send_error(404, f"missing {path.name}")
            return
        self._send_json(json.loads(path.read_text(encoding="utf-8")))

    def _send_wiki_index(self) -> None:
        wiki = self.server.graph_dir / "wiki"
        if not wiki.exists():
            self._send_error(404, "wiki not found")
            return
        index_order = self._wiki_index_order(wiki)
        pages = []
        for path in sorted(
            wiki.glob("*.md"),
            key=lambda p: (p.stem != "index", index_order.get(p.stem, len(index_order)), p.stem.lower()),
        ):
            first = next((line.lstrip("# ").strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()), path.stem)
            pages.append({"name": path.stem, "title": first, "path": f"/wiki/{path.stem}"})
        self._send_json({"pages": pages})

    def _wiki_index_order(self, wiki: Path) -> dict[str, int]:
        index = wiki / "index.md"
        if not index.exists():
            return {}
        markdown = index.read_text(encoding="utf-8")
        targets = re.findall(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", markdown)
        order: dict[str, int] = {}
        for idx, target in enumerate(targets):
            order.setdefault(target, idx)
            order.setdefault(_safe_filename(target), idx)
        return order

    def _send_wiki_page_json(self, name: str, *, token: str | None = None) -> None:
        page = self.server.graph_dir / "wiki" / f"{_safe_filename(name)}.md"
        if not page.exists():
            self._send_error(404, "wiki page not found")
            return
        markdown = page.read_text(encoding="utf-8")
        self._send_json({"name": name, "markdown": markdown, "html": render_markdown(markdown, token=token)})

    def _send_wiki_page_html(self, name: str, query: dict[str, list[str]]) -> None:
        if not self._authorized(query):
            self._send_error(401, "missing or invalid token")
            return
        page = self.server.graph_dir / "wiki" / f"{_safe_filename(name)}.md"
        if not page.exists():
            self._send_error(404, "wiki page not found")
            return
        body = render_markdown(page.read_text(encoding="utf-8"), token=query.get("token", [None])[0])
        data = f"<!doctype html><html><head><meta charset='utf-8'><title>{html.escape(name)}</title><link rel='stylesheet' href='/styles.css'></head><body><main class='wiki-page'>{body}</main></body></html>".encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self._write_body(data)

    def _send_health(self) -> None:
        graph_path = self.server.graph_dir / "graph.json"
        graph = {"exists": graph_path.exists(), "nodes": 0, "links": 0}
        if graph_path.exists():
            data = json.loads(graph_path.read_text(encoding="utf-8"))
            graph["nodes"] = len(data.get("nodes", []))
            graph["links"] = len(data.get("links", data.get("edges", [])))
        self._send_json({
            "project": str(self.server.project_path),
            "graph_dir": str(self.server.graph_dir),
            "graph": graph,
            "report": {"exists": (self.server.graph_dir / "GRAPH_REPORT.md").exists()},
            "wiki": {"exists": (self.server.graph_dir / "wiki").exists()},
        })

    def _send_json(self, data: object, status: int = 200) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self._write_body(body)

    def _send_error(self, status: int, message: str) -> None:
        self._send_json({"error": message}, status=status)

    def _write_body(self, body: bytes) -> None:
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, socket.timeout):
            return
