"""Standalone dashboard output for graphify-out/graphify.html."""
from __future__ import annotations

import json
import re
from pathlib import Path

DASHBOARD_HTML = "graphify.html"


def remove_dashboard_html(graph_dir: str | Path) -> None:
    path = Path(graph_dir) / DASHBOARD_HTML
    if path.exists():
        path.unlink()


def write_dashboard_html(graph_dir: str | Path) -> Path:
    """Write a self-contained dashboard for graphify-out artifacts.

    ``graph.html`` remains the legacy force-directed visualization. This file is
    the product-facing overview that can be opened directly from disk.
    """
    out = Path(graph_dir)
    graph = _read_json(out / "graph.json", {"nodes": [], "links": []})
    report = _read_text(out / "GRAPH_REPORT.md")
    wiki = _read_wiki(out / "wiki")
    payload = _json_for_script({"graph": graph, "report": report, "wiki": wiki})
    html = _HTML_TEMPLATE.replace("__GRAPHIFY_DATA__", payload)
    target = out / DASHBOARD_HTML
    target.write_text(html, encoding="utf-8")
    return target


def _read_json(path: Path, default: object) -> object:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _read_wiki(wiki_dir: Path) -> list[dict[str, str]]:
    if not wiki_dir.exists():
        return []
    index_order = _wiki_index_order(wiki_dir)
    pages = []
    for path in sorted(
        wiki_dir.glob("*.md"),
        key=lambda p: (p.stem != "index", index_order.get(p.stem, len(index_order)), p.stem.lower()),
    ):
        markdown = path.read_text(encoding="utf-8")
        title = next((line.lstrip("# ").strip() for line in markdown.splitlines() if line.strip()), path.stem)
        pages.append({"name": path.stem, "title": title, "markdown": markdown})
    return pages


def _wiki_index_order(wiki_dir: Path) -> dict[str, int]:
    index = wiki_dir / "index.md"
    if not index.exists():
        return {}
    markdown = index.read_text(encoding="utf-8")
    targets = re.findall(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", markdown)
    order: dict[str, int] = {}
    for idx, target in enumerate(targets):
        order.setdefault(target, idx)
        safe = target.replace("/", "-").replace(" ", "_").replace(":", "-")
        safe = re.sub(r'[<>:"/\\|?*]', "_", safe).strip(". ")[:200] or "unnamed"
        order.setdefault(safe, idx)
    return order


def _json_for_script(data: object) -> str:
    return (
        json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )


_HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Graphify Dashboard</title>
  <style>
    * { box-sizing: border-box; }
    body { margin: 0; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #172033; background: #f5f7fa; }
    .shell { min-height: 100vh; display: grid; grid-template-columns: 236px 1fr; }
    aside { background: #101827; color: #f8fafc; padding: 20px; display: flex; flex-direction: column; gap: 18px; }
    .brand { font-size: 22px; font-weight: 750; }
    .meta { color: #aeb8c7; font-size: 13px; line-height: 1.45; overflow-wrap: anywhere; }
    nav { display: grid; gap: 8px; }
    button, input { font: inherit; }
    nav button { border: 0; border-radius: 6px; padding: 10px 12px; text-align: left; color: #dce3ec; background: transparent; cursor: pointer; }
    nav button.active, nav button:hover { color: #fff; background: #334155; }
    main { min-width: 0; padding: 22px; overflow: auto; }
    .view { display: none; }
    .view.active { display: block; }
    .metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-bottom: 18px; }
    .metric, .panel, .list, pre { background: #fff; border: 1px solid #dfe5ed; border-radius: 8px; padding: 15px; }
    .metric span { display: block; font-size: 30px; font-weight: 750; }
    .metric label { color: #64748b; font-size: 13px; }
    .toolbar { display: grid; grid-template-columns: minmax(180px, 420px); margin-bottom: 12px; }
    input { width: 100%; border: 1px solid #cbd5e1; border-radius: 6px; padding: 10px 12px; background: #fff; color: #172033; }
    .list { display: grid; gap: 8px; max-height: 70vh; overflow: auto; }
    .item { border: 1px solid #e2e8f0; border-radius: 6px; background: #fff; padding: 10px 12px; overflow-wrap: anywhere; }
    .item strong { display: block; margin-bottom: 4px; }
    .item small { color: #64748b; }
    pre { white-space: pre-wrap; overflow-wrap: anywhere; margin: 0; line-height: 1.5; }
    .wiki-layout { display: grid; grid-template-columns: minmax(180px, 280px) 1fr; gap: 14px; align-items: start; }
    .wiki-page h1, .wiki-page h2, .wiki-page h3, .markdown h1, .markdown h2, .markdown h3 { margin-top: 0; }
    .markdown { line-height: 1.55; }
    .wiki-page a, .markdown a { color: #155eef; }
    .wiki-page code, .markdown code { background: #eef2f7; border-radius: 4px; padding: 1px 4px; }
    .empty { color: #64748b; }
    @media (max-width: 800px) {
      .shell { grid-template-columns: 1fr; }
      aside { min-height: auto; }
      .metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .wiki-layout { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <div class="shell">
    <aside>
      <div class="brand">Graphify</div>
      <nav>
        <button data-view="overview" class="active">Overview</button>
        <button data-view="nodes">Nodes</button>
        <button data-view="wiki">Wiki</button>
        <button data-view="report">Report</button>
      </nav>
      <div id="meta" class="meta"></div>
    </aside>
    <main>
      <section id="overview" class="view active">
        <div class="metrics">
          <div class="metric"><span id="node-count">0</span><label>Nodes</label></div>
          <div class="metric"><span id="edge-count">0</span><label>Edges</label></div>
          <div class="metric"><span id="community-count">0</span><label>Communities</label></div>
          <div class="metric"><span id="wiki-count">0</span><label>Wiki Pages</label></div>
        </div>
        <div class="panel">
          <h2>Top Connected Nodes</h2>
          <div id="top-nodes" class="list"></div>
        </div>
      </section>
      <section id="nodes" class="view">
        <div class="toolbar"><input id="node-search" placeholder="Search nodes"></div>
        <div id="node-list" class="list"></div>
      </section>
      <section id="wiki" class="view">
        <div class="wiki-layout">
          <div id="wiki-list" class="list"></div>
          <article id="wiki-page" class="panel wiki-page"></article>
        </div>
      </section>
      <section id="report" class="view">
        <article id="report-text" class="panel markdown"></article>
      </section>
    </main>
  </div>
  <script id="graphify-data" type="application/json">__GRAPHIFY_DATA__</script>
  <script>
    const data = JSON.parse(document.getElementById('graphify-data').textContent);
    const graph = data.graph || {};
    const nodes = graph.nodes || [];
    const edges = graph.links || graph.edges || [];
    const wiki = data.wiki || [];
    const byId = new Map(nodes.map((node) => [node.id, node]));
    const degree = new Map(nodes.map((node) => [node.id, 0]));
    for (const edge of edges) {
      const source = typeof edge.source === 'object' ? edge.source.id : edge.source;
      const target = typeof edge.target === 'object' ? edge.target.id : edge.target;
      degree.set(source, (degree.get(source) || 0) + 1);
      degree.set(target, (degree.get(target) || 0) + 1);
    }
    const communities = new Set(nodes.map((node) => node.community).filter((value) => value !== undefined && value !== null));
    const text = (id, value) => { document.getElementById(id).textContent = value; };
    text('node-count', nodes.length);
    text('edge-count', edges.length);
    text('community-count', communities.size);
    text('wiki-count', wiki.length);
    text('meta', 'Standalone file: graphify.html');

    document.querySelectorAll('nav button').forEach((button) => {
      button.addEventListener('click', () => {
        document.querySelectorAll('nav button').forEach((b) => b.classList.remove('active'));
        document.querySelectorAll('.view').forEach((view) => view.classList.remove('active'));
        button.classList.add('active');
        document.getElementById(button.dataset.view).classList.add('active');
      });
    });

    const nodeTitle = (node) => node.label || node.id || '(unnamed)';
    const renderNode = (node) => {
      const item = document.createElement('div');
      item.className = 'item';
      const title = document.createElement('strong');
      title.textContent = nodeTitle(node);
      const detail = document.createElement('small');
      detail.textContent = [
        node.id,
        node.source_file,
        node.type || node.file_type,
        `degree ${degree.get(node.id) || 0}`
      ].filter(Boolean).join(' | ');
      item.append(title, detail);
      return item;
    };
    const renderList = (container, items) => {
      container.replaceChildren();
      if (!items.length) {
        const empty = document.createElement('div');
        empty.className = 'empty';
        empty.textContent = 'No items found.';
        container.appendChild(empty);
        return;
      }
      for (const item of items) container.appendChild(renderNode(item));
    };
    const topNodes = nodes.slice().sort((a, b) => (degree.get(b.id) || 0) - (degree.get(a.id) || 0)).slice(0, 20);
    renderList(document.getElementById('top-nodes'), topNodes);
    const nodeList = document.getElementById('node-list');
    const search = document.getElementById('node-search');
    const updateSearch = () => {
      const query = search.value.trim().toLowerCase();
      const filtered = query
        ? nodes.filter((node) => JSON.stringify(node).toLowerCase().includes(query)).slice(0, 300)
        : nodes.slice(0, 300);
      renderList(nodeList, filtered);
    };
    search.addEventListener('input', updateSearch);
    updateSearch();

    const wikiList = document.getElementById('wiki-list');
    const wikiPage = document.getElementById('wiki-page');
    const safeFilename = (value) => String(value || '')
      .replaceAll('/', '-')
      .replaceAll(' ', '_')
      .replaceAll(':', '-')
      .replace(/[<>:"/\\\\|?*]/g, '_')
      .replace(/^[. ]+|[. ]+$/g, '')
      .slice(0, 200) || 'unnamed';
    const wikiByName = new Map(wiki.map((page) => [page.name, page]));
    const wikiByTitle = new Map(wiki.map((page) => [page.title, page]));
    const splitWikiLink = (value) => {
      const body = String(value || '').slice(2, -2);
      const pipe = body.indexOf('|');
      const target = pipe >= 0 ? body.slice(0, pipe) : body;
      const label = pipe >= 0 ? body.slice(pipe + 1) : body;
      return { target, label };
    };
    const resolveWikiPage = (target, label) => {
      return wikiByName.get(target)
        || wikiByName.get(safeFilename(target))
        || wikiByTitle.get(target)
        || wikiByName.get(label)
        || wikiByName.get(safeFilename(label))
        || wikiByTitle.get(label)
        || null;
    };
    const appendFormattedText = (parent, value) => {
      for (const chunk of String(value || '').split(/(`[^`]+`|\\*\\*[^*]+\\*\\*)/g)) {
        if (!chunk) continue;
        if (chunk.startsWith('`') && chunk.endsWith('`')) {
          const code = document.createElement('code');
          code.textContent = chunk.slice(1, -1);
          parent.appendChild(code);
        } else if (chunk.startsWith('**') && chunk.endsWith('**')) {
          const strong = document.createElement('strong');
          strong.textContent = chunk.slice(2, -2);
          parent.appendChild(strong);
        } else {
          parent.appendChild(document.createTextNode(chunk));
        }
      }
    };
    const openWikiPage = (page) => {
      if (!page) return;
      wikiPage.replaceChildren();
      wikiPage.appendChild(renderMarkdown(page.markdown || ''));
      document.querySelectorAll('nav button').forEach((b) => b.classList.remove('active'));
      document.querySelectorAll('.view').forEach((view) => view.classList.remove('active'));
      document.querySelector('nav button[data-view="wiki"]').classList.add('active');
      document.getElementById('wiki').classList.add('active');
    };
    const appendInline = (parent, value) => {
      for (const part of String(value || '').split(/(\\[\\[[^\\]]+\\]\\])/g)) {
        if (!part) continue;
        if (part.startsWith('[[') && part.endsWith(']]')) {
          const { target, label } = splitWikiLink(part);
          const page = resolveWikiPage(target, label);
          if (page) {
            const link = document.createElement('a');
            link.href = `#wiki-${page.name}`;
            link.textContent = label;
            link.addEventListener('click', (event) => {
              event.preventDefault();
              openWikiPage(page);
            });
            parent.appendChild(link);
          } else {
            parent.appendChild(document.createTextNode(label));
          }
          continue;
        }
        appendFormattedText(parent, part);
      }
    };
    const renderMarkdown = (markdown) => {
      const root = document.createElement('div');
      let list = null;
      const closeList = () => { list = null; };
      for (const raw of String(markdown || '').split('\\n')) {
        const line = raw.trimEnd();
        if (!line) {
          closeList();
          continue;
        }
        const heading = line.match(/^(#{1,3})\\s+(.*)$/);
        if (heading) {
          closeList();
          const el = document.createElement(`h${heading[1].length}`);
          appendInline(el, heading[2]);
          root.appendChild(el);
          continue;
        }
        if (line.startsWith('- ')) {
          if (!list) {
            list = document.createElement('ul');
            root.appendChild(list);
          }
          const item = document.createElement('li');
          appendInline(item, line.slice(2));
          list.appendChild(item);
          continue;
        }
        closeList();
        const p = document.createElement('p');
        appendInline(p, line);
        root.appendChild(p);
      }
      return root;
    };
    document.getElementById('report-text').appendChild(renderMarkdown(data.report || 'GRAPH_REPORT.md not found.'));
    for (const page of wiki) {
      const button = document.createElement('button');
      button.className = 'item';
      button.textContent = page.title || page.name;
      button.addEventListener('click', () => openWikiPage(page));
      wikiList.appendChild(button);
    }
    if (wiki[0]) {
      wikiPage.appendChild(renderMarkdown(wiki[0].markdown || ''));
    } else {
      wikiPage.textContent = 'No wiki pages found.';
    }
  </script>
</body>
</html>
"""
