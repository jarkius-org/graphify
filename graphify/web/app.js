const params = new URLSearchParams(location.search);
const token = params.get('token') || '';
const api = (path) => fetch(`${path}${path.includes('?') ? '&' : '?'}token=${encodeURIComponent(token)}`).then((r) => {
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
});

const setText = (id, value) => { document.getElementById(id).textContent = value; };
const normalize = (value) => String(value || '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
let wikiPages = [];
let graphNodes = [];

document.querySelectorAll('nav button').forEach((button) => {
  button.addEventListener('click', () => {
    document.querySelectorAll('nav button').forEach((b) => b.classList.remove('active'));
    document.querySelectorAll('.view').forEach((v) => v.classList.remove('active'));
    button.classList.add('active');
    document.getElementById(button.dataset.view).classList.add('active');
  });
});

async function selectWikiPage(page, selectedButton = null) {
  document.querySelectorAll('#wiki-list .item').forEach((item) => item.classList.remove('active'));
  if (selectedButton) selectedButton.classList.add('active');
  const article = document.getElementById('wiki-page');
  article.textContent = 'Loading...';
  const detail = await api(`/api/wiki/${encodeURIComponent(page.name)}`);
  article.innerHTML = detail.html;
}

function renderWikiList(pages) {
  const list = document.getElementById('wiki-list');
  list.replaceChildren();
  document.getElementById('wiki-summary').textContent = `${pages.length} of ${wikiPages.length} pages`;
  for (const page of pages) {
    const item = document.createElement('button');
    item.className = 'item';
    item.textContent = page.title;
    item.title = page.name;
    item.addEventListener('click', () => selectWikiPage(page, item).catch((error) => {
      document.getElementById('wiki-page').textContent = error.message;
    }));
    list.appendChild(item);
  }
  if (!pages.length) {
    const empty = document.createElement('div');
    empty.className = 'summary';
    empty.textContent = 'No wiki pages match this search.';
    list.appendChild(empty);
  }
  return list.querySelector('.item');
}

async function loadWiki() {
  const data = await api('/api/wiki');
  wikiPages = data.pages;
  setText('wiki-count', wikiPages.length);
  const firstButton = renderWikiList(wikiPages);
  const indexPage = wikiPages.find((page) => page.name === 'index') || wikiPages[0];
  if (indexPage) {
    await selectWikiPage(indexPage, firstButton);
  }
}

function renderGraphList(nodes) {
  const graphList = document.getElementById('graph-list');
  graphList.replaceChildren();
  document.getElementById('graph-summary').textContent = `${nodes.length} of ${graphNodes.length} nodes`;
  for (const node of nodes.slice(0, 300)) {
    const item = document.createElement('div');
    item.className = 'item';
    item.textContent = node.label || node.id;
    graphList.appendChild(item);
  }
}

async function load() {
  try {
    const [health, report] = await Promise.all([api('/api/health'), api('/api/report').catch(() => ({ markdown: '', html: '' }))]);
    setText('node-count', health.graph.nodes);
    setText('link-count', health.graph.links);
    document.getElementById('status').textContent = health.graph_dir;
    const reportText = document.getElementById('report-text');
    if (report.html) {
      reportText.innerHTML = report.html;
    } else {
      reportText.textContent = report.markdown;
    }
    const topNodes = document.getElementById('top-nodes');
    topNodes.replaceChildren();
    const heading = document.createElement('h2');
    heading.textContent = 'Loaded Graph';
    const summary = document.createElement('p');
    summary.textContent = `${health.graph.nodes} nodes and ${health.graph.links} links from ${health.graph_dir}`;
    topNodes.append(heading, summary);

    await loadWiki().catch(() => setText('wiki-count', 0));
    api('/api/graph').then((graph) => {
      graphNodes = graph.nodes || [];
      renderGraphList(graphNodes);
    }).catch((error) => {
      document.getElementById('graph-summary').textContent = error.message;
    });
  } catch (error) {
    document.getElementById('status').textContent = error.message;
  }
}

document.getElementById('wiki-search').addEventListener('input', (event) => {
  const query = normalize(event.target.value);
  const pages = query
    ? wikiPages.filter((page) => normalize(`${page.title} ${page.name}`).includes(query))
    : wikiPages;
  const firstButton = renderWikiList(pages);
  if (pages[0]) {
    selectWikiPage(pages[0], firstButton).catch((error) => {
      document.getElementById('wiki-page').textContent = error.message;
    });
  }
});

document.getElementById('graph-search').addEventListener('input', (event) => {
  const query = normalize(event.target.value);
  const nodes = query
    ? graphNodes.filter((node) => normalize(`${node.label || ''} ${node.id || ''} ${node.source_file || ''}`).includes(query))
    : graphNodes;
  renderGraphList(nodes);
});

load();
