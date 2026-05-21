const params = new URLSearchParams(location.search);
const token = params.get('token') || '';
const api = (path) => fetch(`${path}${path.includes('?') ? '&' : '?'}token=${encodeURIComponent(token)}`).then((r) => {
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
});

const setText = (id, value) => { document.getElementById(id).textContent = value; };
const normalize = (value) => String(value || '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
let wikiPages = [];
let projectWikiPages = [];
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
  await selectPage({
    page,
    selectedButton,
    listId: 'wiki-list',
    articleId: 'wiki-page',
    apiPrefix: '/api/wiki',
  });
}

async function selectProjectWikiPage(page, selectedButton = null) {
  await selectPage({
    page,
    selectedButton,
    listId: 'project-wiki-list',
    articleId: 'project-wiki-page',
    apiPrefix: '/api/project-wiki',
  });
}

async function selectPage({ page, selectedButton = null, listId, articleId, apiPrefix }) {
  document.querySelectorAll(`#${listId} .item`).forEach((item) => item.classList.remove('active'));
  if (selectedButton) selectedButton.classList.add('active');
  const article = document.getElementById(articleId);
  article.textContent = 'Loading...';
  const detail = await api(`${apiPrefix}/${encodeURIComponent(page.name)}`);
  article.innerHTML = detail.html;
}

function renderPageList({ pages, allPages, listId, summaryId, emptyText, select }) {
  const list = document.getElementById(listId);
  list.replaceChildren();
  document.getElementById(summaryId).textContent = `${pages.length} of ${allPages.length} pages`;
  for (const page of pages) {
    const item = document.createElement('button');
    item.className = 'item';
    item.textContent = page.title;
    item.title = page.name;
    item.addEventListener('click', () => select(page, item).catch((error) => {
      const articleId = listId.replace('-list', '-page');
      document.getElementById(articleId).textContent = error.message;
    }));
    list.appendChild(item);
  }
  if (!pages.length) {
    const empty = document.createElement('div');
    empty.className = 'summary';
    empty.textContent = emptyText;
    list.appendChild(empty);
  }
  return list.querySelector('.item');
}

function renderWikiList(pages) {
  return renderPageList({
    pages,
    allPages: wikiPages,
    listId: 'wiki-list',
    summaryId: 'wiki-summary',
    emptyText: 'No wiki pages match this search.',
    select: selectWikiPage,
  });
}

function renderProjectWikiList(pages) {
  return renderPageList({
    pages,
    allPages: projectWikiPages,
    listId: 'project-wiki-list',
    summaryId: 'project-wiki-summary',
    emptyText: 'No project wiki pages match this search.',
    select: selectProjectWikiPage,
  });
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

async function loadProjectWiki() {
  const data = await api('/api/project-wiki');
  projectWikiPages = data.pages;
  setText('project-wiki-count', projectWikiPages.length);
  const firstButton = renderProjectWikiList(projectWikiPages);
  const indexPage = projectWikiPages.find((page) => page.name.endsWith('/index.md')) || projectWikiPages[0];
  if (indexPage) {
    await selectProjectWikiPage(indexPage, firstButton);
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
    await loadProjectWiki().catch(() => setText('project-wiki-count', 0));
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

document.getElementById('project-wiki-search').addEventListener('input', (event) => {
  const query = normalize(event.target.value);
  const pages = query
    ? projectWikiPages.filter((page) => normalize(`${page.title} ${page.name}`).includes(query))
    : projectWikiPages;
  const firstButton = renderProjectWikiList(pages);
  if (pages[0]) {
    selectProjectWikiPage(pages[0], firstButton).catch((error) => {
      document.getElementById('project-wiki-page').textContent = error.message;
    });
  }
});

document.getElementById('project-wiki-page').addEventListener('click', (event) => {
  if (!(event.target instanceof Element)) return;
  const link = event.target.closest('a[href^="/project-wiki/"]');
  if (!link) return;
  event.preventDefault();
  const url = new URL(link.href);
  const name = decodeURIComponent(url.pathname.replace('/project-wiki/', ''));
  const page = projectWikiPages.find((candidate) => candidate.name === name) || { name, title: name };
  selectProjectWikiPage(page).catch((error) => {
    document.getElementById('project-wiki-page').textContent = error.message;
  });
});

document.getElementById('graph-search').addEventListener('input', (event) => {
  const query = normalize(event.target.value);
  const nodes = query
    ? graphNodes.filter((node) => normalize(`${node.label || ''} ${node.id || ''} ${node.source_file || ''}`).includes(query))
    : graphNodes;
  renderGraphList(nodes);
});

load();
