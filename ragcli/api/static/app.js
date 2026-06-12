// ragcli web UI application logic.
// All dynamic content is built with esc()/escAttr() and data-action
// attributes + delegated listeners — no string-interpolated inline handlers.

let sending = false, lastSources = [], theme = 'dark', sbMode = '';

const $ = id => document.getElementById(id);

// --- Textarea auto-resize + send on Enter ---
function autoR(el) { el.style.height = 'auto'; el.style.height = Math.min(el.scrollHeight, 120) + 'px'; }
$('qIn').addEventListener('input', e => autoR(e.target));
$('qIn').addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } });

// --- Theme ---
function togTheme() {
  theme = theme === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', theme);
  $('thBtn').textContent = theme === 'dark' ? 'Light' : 'Dark';
  mermaid.initialize({ theme: theme === 'dark' ? 'dark' : 'default', startOnLoad: false, securityLevel: 'strict' });
}

// --- Status + collections ---
async function loadStatus() {
  try {
    const [sr, cr] = await Promise.all([fetch('/status'), fetch('/collections')]);
    const s = await sr.json(), c = await cr.json();
    $('stText').textContent = s.total_documents + ' docs · ' + s.total_chunks + ' chunks';
    const sel = $('colSel'); sel.innerHTML = '';
    c.collections.forEach(col => {
      const o = document.createElement('option');
      o.value = col.name; o.textContent = col.name + ' (' + col.chunks + ')';
      if (col.name === c.active) o.selected = true;
      sel.appendChild(o);
    });
  } catch (e) { $('stText').textContent = 'error'; }
}

async function switchCol(name) {
  const r = await fetch('/collections/switch', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name }) });
  const d = await r.json();
  const area = $('chatArea');
  area.innerHTML = ''; lastSources = [];
  const notice = document.createElement('div');
  notice.style.cssText = 'text-align:center;padding:.5rem;font-size:.78rem;color:var(--text3);margin-bottom:.5rem';
  notice.textContent = 'Switched to collection "' + name + '" — ' + (d.chunks || 0) + ' chunks' + (d.docs_dir ? ' from ' + d.docs_dir : '');
  area.appendChild(notice);
  loadStatus(); loadWelcome();
}

// --- Sidebar ---
function openSB(mode) {
  sbMode = mode;
  $('sidebar').classList.remove('closed');
  $('sbTitle').textContent = { sources: 'Sources', graph: 'Knowledge Graph', docs: 'Documents', collections: 'Collections', settings: 'Settings' }[mode] || mode;
  const body = $('sbBody');
  if (mode === 'sources') renderSources(body);
  else if (mode === 'graph') loadGraph(body);
  else if (mode === 'docs') loadDocs(body);
  else if (mode === 'collections') loadCollections(body);
  else if (mode === 'settings') loadSettings(body);
}
function closeSB() { $('sidebar').classList.add('closed'); sbMode = ''; }

// --- Sources panel ---
function renderSources(el) {
  if (!lastSources.length) { el.innerHTML = '<p style="color:var(--text3)">No sources yet. Ask a question first.</p>'; return; }
  el.innerHTML = '';
  lastSources.forEach(s => {
    const rel = Math.round((s.relevance || 0) * 100);
    const cls = rel >= 70 ? 'hi' : '';
    const d = document.createElement('div'); d.className = 'src-item';
    d.innerHTML = '<div class="src-top"><span class="src-name"><a href="' + escAttr(s.file_url || '#') + '" target="_blank">' + esc(s.file_name || s.file) + '</a></span><span class="src-badge ' + cls + '">' + rel + '%</span></div>' +
      '<div class="src-section">' + esc(s.section || '') + '</div>' +
      '<div class="src-content">' + renderMd(s.content || '') + '</div>' +
      (s.file_url ? '<a class="src-open" href="' + escAttr(s.file_url) + '" target="_blank">Open document &rarr;</a>' : '');
    el.appendChild(d);
    enhanceRendered(d);
  });
}

// --- Knowledge graph panel ---
const ENTITY_COLORS = { money: '#4ade80', cost: '#4ade80', date: '#60a5fa', confirmation: '#fbbf24', confirmation_number: '#fbbf24', person: '#f472b6', location: '#a78bfa', hotel: '#fb923c', airline: '#22d3ee', organization: '#34d399', email: '#94a3b8', phone: '#94a3b8' };

function entityCard(e) {
  const srcNames = (e.sources || []).map(s => s.split('/').pop()).slice(0, 3).join(', ');
  const c = ENTITY_COLORS[e.type] || 'var(--text2)';
  return '<div class="src-item" style="cursor:pointer" data-action="show-entity" data-id="' + escAttr(e.id) + '">' +
    '<div style="display:flex;justify-content:space-between;align-items:center">' +
    '<span style="font-weight:600;font-size:.82rem">' + esc(e.value) + '</span>' +
    '<span style="font-size:.68rem;padding:.1rem .4rem;border-radius:999px;border:1px solid ' + c + ';color:' + c + '">' + esc(e.type) + '</span>' +
    '</div>' +
    '<div style="font-size:.72rem;color:var(--text3);margin-top:.15rem">' + e.connections + ' connections · ' + esc(srcNames) + '</div></div>';
}

async function loadGraph(el) {
  el.innerHTML = '<p style="color:var(--text3)">Loading...</p>';
  try {
    const r = await fetch('/graph'); const d = await r.json();
    const stats = d.stats || {}; const entities = d.entities || [];
    let html = '';

    html += '<div style="display:flex;gap:.5rem;margin-bottom:.75rem;flex-wrap:wrap">';
    html += '<div style="background:var(--bg);border:1px solid var(--border);border-radius:var(--Rs);padding:.4rem .6rem;font-size:.75rem"><b>' + (stats.total_nodes || 0) + '</b> nodes</div>';
    html += '<div style="background:var(--bg);border:1px solid var(--border);border-radius:var(--Rs);padding:.4rem .6rem;font-size:.75rem"><b>' + (stats.total_edges || 0) + '</b> connections</div>';
    html += '</div>';

    const types = stats.entity_types || {};
    const typeKeys = Object.keys(types).filter(t => t !== 'document').sort((a, b) => types[b] - types[a]);
    if (typeKeys.length) {
      html += '<div style="margin-bottom:.75rem">';
      typeKeys.forEach(t => {
        const c = ENTITY_COLORS[t] || 'var(--text2)';
        html += '<span style="display:inline-block;font-size:.7rem;padding:.15rem .45rem;border-radius:999px;border:1px solid ' + c + ';color:' + c + ';margin:0 .25rem .25rem 0">' + esc(t) + ' (' + types[t] + ')</span>';
      });
      html += '</div>';
    }

    html += '<div style="margin-bottom:.75rem"><input id="graphSearch" placeholder="Search entities..." style="width:100%;padding:.4rem .6rem;border-radius:var(--Rs);border:1px solid var(--border);background:var(--bg);color:var(--text);font-size:.8rem"></div>';
    html += '<div id="graphResults">';

    if (!entities.length) {
      html += '<p style="color:var(--text3);font-size:.82rem">No entities yet. Ingest documents to build the knowledge graph.</p>';
    } else {
      entities.slice(0, 50).forEach(e => { html += entityCard(e); });
    }
    html += '</div>';
    el.innerHTML = html;
  } catch (e) { el.innerHTML = '<p style="color:var(--red)">Error loading graph</p>'; }
}

let graphSearchTimer = null;
async function searchGraph(q) {
  clearTimeout(graphSearchTimer);
  const results = $('graphResults');
  if (!results) return;
  if (!q || q.length < 2) {
    graphSearchTimer = setTimeout(async () => {
      try {
        const r = await fetch('/graph'); const d = await r.json();
        results.innerHTML = (d.entities || []).slice(0, 50).map(entityCard).join('');
      } catch (e) { /* ignore */ }
    }, 300);
    return;
  }
  graphSearchTimer = setTimeout(async () => {
    try {
      const r = await fetch('/graph/search?q=' + encodeURIComponent(q));
      const d = await r.json();
      let html = '';
      (d.entities || []).forEach(e => {
        const srcNames = (e.sources || []).map(s => s.split('/').pop()).slice(0, 3).join(', ');
        html += '<div class="src-item"><div style="font-weight:600;font-size:.82rem">' + esc(e.entity) + '</div>' +
          '<div style="font-size:.72rem;color:var(--text3)">' + esc(e.type) + ' · ' + esc(srcNames) + '</div></div>';
      });
      if (d.related_sources && d.related_sources.length) {
        html += '<div style="font-size:.75rem;font-weight:600;margin:.5rem 0 .25rem;color:var(--text2)">Related documents</div>';
        d.related_sources.forEach(s => {
          html += '<div style="font-size:.78rem;padding:.25rem 0;color:var(--text2)">' + esc(s.split('/').pop()) + '</div>';
        });
      }
      results.innerHTML = html || '<p style="color:var(--text3);font-size:.82rem">No matches</p>';
    } catch (e) { results.innerHTML = '<p>Search error</p>'; }
  }, 300);
}

async function showEntity(id) {
  const body = $('sbBody');
  try {
    const r = await fetch('/graph/entity/' + encodeURIComponent(id));
    const d = await r.json();
    if (!d.entity) { body.innerHTML = '<p>Entity not found</p>'; return; }
    let html = '<button class="pb" data-action="back-graph" style="margin-bottom:.75rem">&larr; Back</button>';
    html += '<div style="font-size:1rem;font-weight:700;margin-bottom:.25rem">' + esc(d.entity.value) + '</div>';
    html += '<div style="font-size:.78rem;color:var(--text3);margin-bottom:.75rem">Type: ' + esc(d.entity.type) + ' · Sources: ' + d.entity.sources.length + '</div>';
    if (d.entity.sources.length) {
      html += '<div style="font-size:.75rem;font-weight:600;margin-bottom:.25rem">Found in</div>';
      d.entity.sources.forEach(s => {
        html += '<div style="font-size:.78rem;padding:.2rem 0;color:var(--accent2)">' + esc(s.split('/').pop()) + '</div>';
      });
    }
    if (d.connections.length) {
      html += '<div style="font-size:.75rem;font-weight:600;margin:.75rem 0 .25rem">Connected to</div>';
      d.connections.forEach(c => {
        const label = c.value || c.id;
        const rel = c.relation === 'contains' ? 'in document' : 'co-occurs';
        const action = c.type === 'document' ? '' : ' data-action="show-entity" data-id="' + escAttr(c.id) + '"';
        html += '<div class="src-item" style="padding:.4rem .6rem;cursor:pointer"' + action + '>' +
          '<span style="font-size:.8rem;font-weight:500">' + esc(label) + '</span>' +
          ' <span style="font-size:.68rem;color:var(--text3)">' + esc(c.type) + ' · ' + esc(rel) + '</span></div>';
      });
    }
    body.innerHTML = html;
  } catch (e) { body.innerHTML = '<p>Error</p>'; }
}

// --- Docs panel ---
async function loadDocs(el) {
  el.innerHTML = '<p style="color:var(--text3)">Loading...</p>';
  try {
    const r = await fetch('/summaries'); const d = await r.json();
    const entries = Object.entries(d.summaries);
    if (!entries.length) { el.innerHTML = '<p style="color:var(--text3)">No summaries yet. Ingest documents first.</p>'; return; }
    el.innerHTML = '';
    entries.forEach(([name, summary]) => {
      const div = document.createElement('div'); div.className = 'src-item';
      div.innerHTML = '<div class="src-name" style="margin-bottom:.25rem">' + esc(name) + '</div><div style="font-size:.8rem;color:var(--text2);line-height:1.5">' + esc(summary) + '</div>';
      el.appendChild(div);
    });
  } catch (e) { el.innerHTML = '<p>Error loading</p>'; }
}

// --- Collections panel ---
async function loadCollections(el) {
  el.innerHTML = '<p style="color:var(--text3)">Loading...</p>';
  try {
    const r = await fetch('/collections'); const d = await r.json();
    el.innerHTML = '';
    d.collections.forEach(col => {
      const isActive = col.name === d.active;
      const div = document.createElement('div'); div.className = 'col-item' + (isActive ? ' active' : '');
      div.style.cssText = 'display:block;padding:.65rem .75rem';
      const docsDir = col.docs_dir || './docs';
      div.innerHTML = '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.25rem">' +
        '<div><span class="col-name">' + esc(col.name) + '</span> <span class="col-count">' + col.chunks + ' chunks</span></div>' +
        '<div class="col-actions">' + (isActive ? '<span style="font-size:.72rem;color:var(--accent2)">active</span>' :
          '<button class="col-btn" data-action="use-col" data-name="' + escAttr(col.name) + '">Use</button>' +
          '<button class="col-btn del" data-action="delete-col" data-name="' + escAttr(col.name) + '">Delete</button>') + '</div></div>' +
        '<div style="font-size:.72rem;color:var(--text3)">Folder: ' + esc(docsDir) + '</div>' +
        (isActive ? '<div style="margin-top:.35rem"><button class="col-btn" data-action="reindex-col" data-name="' + escAttr(col.name) + '">Re-index</button></div>' : '');
      el.appendChild(div);

      if (isActive) {
        // Upload zone under the active collection
        const upWrap = document.createElement('div');
        upWrap.style.cssText = 'margin:-.2rem 0 .75rem;padding:.6rem;border:1px solid var(--border);border-top:none;border-radius:0 0 var(--Rs) var(--Rs);background:var(--bg)';
        upWrap.innerHTML = '<div style="font-size:.75rem;color:var(--text3);margin-bottom:.4rem">Upload files to <b>' + esc(col.name) + '</b></div>' +
          '<div class="upload-zone" id="upZone" style="padding:1rem"><h4 style="font-size:.85rem">Drop files here or click to browse</h4><p>PDF, DOCX, PPTX, XLSX, MD, TXT, HTML, CSV</p><input type="file" id="upFile" multiple accept=".pdf,.docx,.pptx,.xlsx,.xls,.md,.txt,.html,.csv"></div>' +
          '<div class="upload-progress" id="upProg"></div>';
        el.appendChild(upWrap);
        const zone = upWrap.querySelector('#upZone'), inp = upWrap.querySelector('#upFile');
        zone.addEventListener('click', () => inp.click());
        inp.addEventListener('change', () => { if (inp.files.length) uploadFiles(inp.files, col.name); });
        zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('drag'); });
        zone.addEventListener('dragleave', () => zone.classList.remove('drag'));
        zone.addEventListener('drop', e => { e.preventDefault(); zone.classList.remove('drag'); if (e.dataTransfer.files.length) uploadFiles(e.dataTransfer.files, col.name); });

        // RSS feeds section
        const feedWrap = document.createElement('div');
        feedWrap.style.cssText = 'margin:-.2rem 0 .75rem;padding:.6rem;border:1px solid var(--border);border-top:none;border-radius:0 0 var(--Rs) var(--Rs);background:var(--bg)';
        feedWrap.innerHTML = '<div style="font-size:.75rem;color:var(--text3);margin-bottom:.4rem">RSS feeds for <b>' + esc(col.name) + '</b></div>' +
          '<div id="feedList" style="margin-bottom:.4rem"></div>' +
          '<div style="display:flex;gap:.3rem"><input id="feedUrl" placeholder="RSS feed URL..." style="flex:1;padding:.35rem .5rem;border-radius:var(--Rs);border:1px solid var(--border);background:var(--bg2);color:var(--text);font-size:.78rem"><button class="col-btn" data-action="add-feed" data-col="' + escAttr(col.name) + '">Add</button></div>' +
          '<div id="feedStatus" style="display:none;margin-top:.4rem;font-size:.75rem"></div>';
        el.appendChild(feedWrap);
        loadFeeds(col.name);
      }
    });

    // Create new collection with folder browser
    const cr = document.createElement('div'); cr.style.cssText = 'margin-top:1rem;padding-top:.75rem;border-top:1px solid var(--border)';
    cr.innerHTML = '<div style="font-size:.8rem;font-weight:600;margin-bottom:.5rem">Create new collection</div>' +
      '<div class="col-create" style="margin-top:0"><input id="newColName" placeholder="Collection name..."></div>' +
      '<div class="col-create"><input id="newColDir" placeholder="Folder path (browse or type new)..." style="flex:1"><button class="pb" data-action="open-browser">Browse</button></div>' +
      '<div style="font-size:.7rem;color:var(--text3);margin-top:.25rem;margin-bottom:.5rem">Browse a folder inside the project, or type a new relative path (e.g. <b>./work-policies</b>) — it will be created automatically. Uploads go into this folder.</div>' +
      '<button class="pb" id="createColBtn" data-action="create-col" style="width:100%;padding:.45rem;text-align:center">Create Collection</button>' +
      '<div id="createColStatus" style="display:none;margin-top:.4rem;font-size:.78rem;text-align:center"></div>' +
      '<div id="folderBrowser" style="display:none;margin-top:.5rem;border:1px solid var(--border);border-radius:var(--Rs);max-height:250px;overflow-y:auto"></div>';
    el.appendChild(cr);
  } catch (e) { el.innerHTML = '<p>Error</p>'; }
}

// --- Folder browser ---
async function openBrowser(startPath) {
  const browser = $('folderBrowser');
  browser.style.display = 'block';
  const path = startPath || '.';
  browser.innerHTML = '<div style="padding:.5rem;color:var(--text3);font-size:.75rem">Loading...</div>';
  try {
    const r = await fetch('/browse?path=' + encodeURIComponent(path));
    const d = await r.json();
    let html = '<div style="padding:.4rem .6rem;font-size:.72rem;color:var(--text3);border-bottom:1px solid var(--border);word-break:break-all">' + esc(d.path) + '</div>';
    if (d.parent && d.parent !== d.path) {
      html += '<div class="browse-row" style="padding:.4rem .6rem;cursor:pointer;font-size:.82rem;border-bottom:1px solid var(--border)" data-action="open-browser" data-path="' + escAttr(d.parent) + '">&#x2191; ..</div>';
    }
    if (d.dirs && d.dirs.length) {
      d.dirs.forEach(dir => {
        const fileInfo = dir.files > 0 ? ' <span style="color:var(--green);font-size:.72rem">' + dir.files + ' docs</span>' : '';
        html += '<div class="browse-row" style="padding:.4rem .6rem;display:flex;justify-content:space-between;align-items:center;cursor:pointer;border-bottom:1px solid var(--border);font-size:.82rem">' +
          '<span data-action="open-browser" data-path="' + escAttr(dir.path) + '">&#x1F4C1; ' + esc(dir.name) + fileInfo + '</span>' +
          '<button class="col-btn" data-action="select-folder" data-path="' + escAttr(dir.path) + '">Select</button></div>';
      });
    } else {
      html += '<div style="padding:.5rem .6rem;color:var(--text3);font-size:.78rem">No subfolders here</div>';
    }
    html += '<div style="padding:.5rem .6rem;border-top:1px solid var(--border)"><button class="pb" data-action="select-folder" data-path="' + escAttr(d.path) + '">Use this folder</button></div>';
    browser.innerHTML = html;
  } catch (e) { browser.innerHTML = '<div style="padding:.5rem;color:var(--red);font-size:.78rem">Error browsing</div>'; }
}

function selectFolder(path) {
  $('newColDir').value = path;
  $('folderBrowser').style.display = 'none';
}

async function createCol() {
  const name = $('newColName').value.trim();
  if (!name) { $('newColName').focus(); return; }
  const dir = $('newColDir').value.trim() || null;
  const btn = $('createColBtn');
  const statusEl = $('createColStatus');
  btn.disabled = true; btn.textContent = 'Creating...';
  statusEl.style.display = 'block';
  statusEl.innerHTML = '<div style="font-size:.8rem;margin-bottom:.4rem;color:var(--accent2)">Setting up collection...</div>' +
    '<div id="createBar" style="background:var(--bg);border:1px solid var(--border);border-radius:4px;height:6px;margin-bottom:.4rem;overflow:hidden"><div id="createFill" style="height:100%;background:var(--accent2);width:0%;transition:width .3s"></div></div>' +
    '<div id="createLog" style="max-height:150px;overflow-y:auto;font-size:.75rem;color:var(--text3)"></div>';
  try {
    const r = await fetch('/collections/create', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name, docs_dir: dir }) });
    if (!r.ok) {
      const err = await r.json().catch(() => ({}));
      throw new Error(err.detail || ('HTTP ' + r.status));
    }
    const d = await r.json();

    if (d.total === 0) {
      statusEl.innerHTML = '<div style="color:var(--green);font-size:.8rem">✓ Created (empty — upload files to get started)</div>';
      btn.disabled = false; btn.textContent = 'Create Collection';
      loadStatus();
      setTimeout(() => loadCollections($('sbBody')), 1500);
      return;
    }

    const log = $('createLog');
    const fill = $('createFill');
    if (log) log.textContent = 'Found ' + d.total + ' files in ' + (d.docs_dir || dir || '') + '...';
    let lastSeen = 0;

    const poll = setInterval(async () => {
      try {
        const pr = await fetch('/collections/reindex/status');
        const p = await pr.json();
        if (p.status === 'idle') return;

        if (fill && p.total > 0) fill.style.width = Math.round(p.processed / p.total * 100) + '%';

        if (p.recent && log) {
          p.recent.forEach(evt => {
            if (evt.processed <= lastSeen) return;
            lastSeen = evt.processed;
            const isErr = evt.event.startsWith('error');
            const icon = isErr ? '✗' : '✓';
            const iconColor = isErr ? 'var(--red)' : 'var(--green)';
            const detail = isErr ? esc(evt.event) : evt.chunks + ' chunks';
            log.innerHTML += '<div><span style="color:' + iconColor + '">' + icon + '</span> ' + esc(evt.file) + ' <span style="color:var(--text3)">' + detail + '</span> <span style="float:right">' + evt.processed + '/' + evt.total + '</span></div>';
            log.scrollTop = log.scrollHeight;
          });
        }

        if (p.status === 'done') {
          clearInterval(poll);
          if (fill) fill.style.width = '100%';
          if (p.error) {
            log.innerHTML += '<div style="color:var(--red);font-weight:600;margin-top:.3rem">✗ Error: ' + esc(p.error) + '</div>';
          } else {
            log.innerHTML += '<div style="color:var(--green);font-weight:600;margin-top:.3rem">✓ Done! ' + p.total_chunks + ' chunks indexed</div>';
          }
          btn.disabled = false; btn.textContent = 'Create Collection';
          loadStatus();
          setTimeout(() => loadCollections($('sbBody')), 2000);
        }
      } catch (e) { /* keep polling */ }
    }, 800);
  } catch (e) {
    statusEl.innerHTML = '<div style="color:var(--red);font-size:.8rem">Error: ' + esc(e.message) + '</div>';
    btn.disabled = false; btn.textContent = 'Create Collection';
  }
}

async function deleteCol(name) {
  if (!confirm('Delete collection "' + name + '"? Source files will NOT be deleted.')) return;
  await fetch('/collections/delete', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name }) });
  loadStatus(); loadCollections($('sbBody'));
}

async function reindexCol(name) {
  const prog = $('upProg');
  if (!prog) return;
  prog.innerHTML = '<div style="font-size:.8rem;font-weight:600;margin-bottom:.4rem">Re-indexing ' + esc(name) + '...</div>' +
    '<div id="reindexBar" style="background:var(--bg);border:1px solid var(--border);border-radius:4px;height:6px;margin-bottom:.5rem;overflow:hidden"><div id="reindexFill" style="height:100%;background:var(--accent2);width:0%;transition:width .3s"></div></div>' +
    '<div id="reindexLog" style="max-height:200px;overflow-y:auto"><div style="font-size:.75rem;color:var(--text3)">Starting...</div></div>';

  try {
    const r = await fetch('/collections/reindex', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name }) });
    const d = await r.json();
    const log = $('reindexLog');
    const dirInfo = d.docs_dir ? ' from ' + esc(d.docs_dir) : '';
    log.innerHTML = '<div style="font-size:.75rem;color:var(--text3)">Found ' + d.total + ' files' + dirInfo + '</div>';
  } catch (e) {
    prog.innerHTML = '<div class="upload-file"><span class="uf-name">Re-index failed</span><span class="uf-status err">' + esc(e.message) + '</span></div>';
    return;
  }

  let lastSeen = 0;
  const poll = setInterval(async () => {
    try {
      const r = await fetch('/collections/reindex/status');
      const d = await r.json();
      if (d.status === 'idle') return;
      const fill = $('reindexFill');
      const log = $('reindexLog');
      if (!fill || !log) { clearInterval(poll); return; }

      if (d.total > 0) fill.style.width = Math.round(d.processed / d.total * 100) + '%';

      if (d.recent) {
        d.recent.forEach(evt => {
          if (evt.processed <= lastSeen) return;
          lastSeen = evt.processed;
          const icon = evt.event === 'added' || evt.event === 'updated' ? '✓' :
            evt.event === 'deleted' ? '−' :
            evt.event.startsWith('error') ? '✗' : '';
          const iconColor = evt.event.startsWith('error') ? 'var(--red)' : 'var(--green)';
          const detail = evt.event.startsWith('error') ? '<span style="color:var(--red)">' + esc(evt.event) + '</span>' : evt.chunks + ' chunks';
          log.innerHTML += '<div style="font-size:.75rem;padding:.1rem 0"><span style="color:' + iconColor + '">' + icon + '</span> ' + esc(evt.file) + ' <span style="color:var(--text3)">' + detail + '</span> <span style="color:var(--text3);float:right">' + evt.processed + '/' + evt.total + '</span></div>';
          log.scrollTop = log.scrollHeight;
        });
      }

      if (d.status === 'done') {
        clearInterval(poll);
        fill.style.width = '100%';
        if (d.error) {
          log.innerHTML += '<div style="font-size:.8rem;font-weight:600;color:var(--red);margin-top:.4rem">✗ Error: ' + esc(d.error) + '</div>';
        } else {
          log.innerHTML += '<div style="font-size:.8rem;font-weight:600;color:var(--green);margin-top:.4rem">✓ Done! ' + d.total_chunks + ' chunks indexed</div>';
        }
        loadStatus();
      }
    } catch (e) { /* keep polling */ }
  }, 800);
}

// --- Upload ---
async function uploadFiles(files, colName) {
  const prog = $('upProg');
  for (const file of files) {
    const size = (file.size / 1024).toFixed(0) + 'KB';
    const row = document.createElement('div');
    row.className = 'upload-file';
    row.innerHTML = '<span class="uf-name">' + esc(file.name) + ' <span style="color:var(--text3)">(' + size + ')</span></span><span class="uf-status prog">uploading...</span>';
    prog.appendChild(row);
    const statusEl = row.querySelector('.uf-status');
    try {
      const fd = new FormData(); fd.append('file', file);
      const r = await fetch('/upload?collection=' + encodeURIComponent(colName), { method: 'POST', body: fd });
      const d = await r.json();
      if (r.ok && d.status === 'ok') {
        statusEl.className = 'uf-status ok';
        statusEl.textContent = (d.added || []).length === 0 ? 'already indexed' : d.total_chunks + ' chunks';
        if (d.errors && d.errors.length) {
          statusEl.className = 'uf-status err';
          statusEl.textContent = d.errors[0].message;
        }
      } else {
        statusEl.className = 'uf-status err';
        statusEl.textContent = d.detail || d.message || 'error';
      }
    } catch (e) {
      statusEl.className = 'uf-status err'; statusEl.textContent = 'failed';
    }
  }
  loadStatus();
  setTimeout(() => { if (sbMode === 'collections') loadCollections($('sbBody')); }, 500);
}

// --- RSS feeds ---
async function loadFeeds(colName) {
  const list = $('feedList');
  if (!list) return;
  try {
    const r = await fetch('/feeds?collection=' + encodeURIComponent(colName));
    const d = await r.json();
    if (!d.feeds || !d.feeds.length) {
      list.innerHTML = '<div style="font-size:.72rem;color:var(--text3)">No feeds added yet</div>';
      return;
    }
    list.innerHTML = '';
    d.feeds.forEach(f => {
      const lastFetch = f.last_fetched ? 'Last fetched: ' + new Date(f.last_fetched).toLocaleDateString() : 'Never fetched';
      list.innerHTML += '<div style="display:flex;justify-content:space-between;align-items:center;padding:.3rem 0;border-bottom:1px solid var(--border);font-size:.75rem">' +
        '<div style="flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="' + escAttr(f.url) + '">' + esc(f.url) + '</div>' +
        '<div style="display:flex;gap:.2rem;margin-left:.3rem;flex-shrink:0">' +
        '<span style="color:var(--text3);font-size:.68rem">' + esc(lastFetch) + '</span>' +
        '<button class="col-btn del" data-action="remove-feed" data-col="' + escAttr(colName) + '" data-url="' + escAttr(f.url) + '">x</button>' +
        '</div></div>';
    });
    list.innerHTML += '<div style="margin-top:.3rem"><button class="col-btn" data-action="fetch-feeds" data-col="' + escAttr(colName) + '">Refresh all feeds</button></div>';
  } catch (e) { list.innerHTML = '<div style="color:var(--red);font-size:.72rem">Error loading feeds</div>'; }
}

async function addFeed(colName) {
  const inp = $('feedUrl');
  const url = inp.value.trim(); if (!url) return;
  const status = $('feedStatus');
  status.style.display = 'block'; status.style.color = 'var(--accent2)'; status.textContent = 'Adding feed...';
  try {
    const r = await fetch('/feeds/add', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url, collection: colName }) });
    if (!r.ok) {
      const err = await r.json().catch(() => ({}));
      throw new Error(err.detail || ('HTTP ' + r.status));
    }
    inp.value = '';
    status.style.color = 'var(--green)'; status.textContent = '✓ Feed added. Click "Refresh all feeds" to fetch articles.';
    loadFeeds(colName);
  } catch (e) { status.style.color = 'var(--red)'; status.textContent = 'Error: ' + e.message; }
}

async function removeFeed(colName, url) {
  await fetch('/feeds/remove', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url, collection: colName }) });
  loadFeeds(colName);
}

async function fetchFeeds(colName) {
  const status = $('feedStatus');
  status.style.display = 'block'; status.style.color = 'var(--accent2)'; status.textContent = 'Fetching feeds...';
  try {
    const r = await fetch('/feeds/fetch?collection=' + encodeURIComponent(colName), { method: 'POST' });
    const d = await r.json();
    let msg = '';
    (d.feeds || []).forEach(f => {
      const feedName = f.url.replace(/https?:\/\//, '').split('/')[0];
      if (f.error) { msg += feedName + ': error (' + f.error + ')\n'; }
      else { msg += feedName + ': ' + f.new_count + ' new / ' + f.total + ' total articles\n'; }
    });
    if (d.indexing) {
      status.style.color = 'var(--accent2)';
      status.innerHTML = esc(msg).replace(/\n/g, '<br>') + '<br>Indexing new articles...';
      const poll = setInterval(async () => {
        try {
          const pr = await fetch('/collections/reindex/status');
          const p = await pr.json();
          if (p.status === 'done') {
            clearInterval(poll);
            status.style.color = 'var(--green)';
            status.innerHTML = esc(msg).replace(/\n/g, '<br>') + '<br>✓ ' + p.total_chunks + ' chunks indexed';
            loadStatus(); loadFeeds(colName);
          }
        } catch (e) { /* keep polling */ }
      }, 1000);
    } else {
      status.style.color = 'var(--green)';
      status.innerHTML = esc(msg).replace(/\n/g, '<br>') + '✓ No new articles';
    }
  } catch (e) { status.style.color = 'var(--red)'; status.textContent = 'Error: ' + e.message; }
}

// --- Settings ---
let modelsData = {};
async function loadSettings(el) {
  el.innerHTML = '<p style="color:var(--text3)">Loading...</p>';
  try {
    const [sr, mr, cr] = await Promise.all([fetch('/settings'), fetch('/models'), fetch('/cache/stats')]);
    const d = await sr.json(); modelsData = await mr.json(); const cs = await cr.json();
    const f = d.features; const llm = d.llm; const ret = d.retrieval; const keys = d.api_keys || {};
    const inp = 'display:block;width:100%;padding:.35rem .5rem;margin-top:.15rem;border-radius:var(--Rs);border:1px solid var(--border);background:var(--bg);color:var(--text);font-size:.8rem';
    let html = '';

    html += '<div style="font-size:.85rem;font-weight:600;margin-bottom:.5rem">Features</div>';
    const toggles = [
      { key: 'agentic_queries', label: 'Agentic queries', desc: 'LLM plans multi-step searches for complex questions' },
      { key: 'knowledge_graph', label: 'Knowledge graph', desc: 'Extract entities and relationships from documents' },
      { key: 'suggestions', label: 'Follow-up suggestions', desc: 'Suggest related questions after each answer' },
      { key: 'query_cache', label: 'Query cache', desc: 'Cache answers for instant repeat queries' },
      { key: 'auto_ingest', label: 'Auto-ingest', desc: 'Automatically index new documents' },
      { key: 'watch_mode', label: 'Watch mode', desc: 'Monitor docs folder for changes' },
    ];
    toggles.forEach(t => {
      const on = f[t.key];
      const bg = on ? 'var(--accent)' : 'var(--bg3)';
      const dot = on ? 'translateX(16px)' : 'translateX(0)';
      const tag = on ? '<span style="color:var(--green);font-size:.68rem;margin-left:.3rem">ON</span>' : '<span style="color:var(--text3);font-size:.68rem;margin-left:.3rem">OFF</span>';
      html += '<div style="display:flex;align-items:center;gap:.6rem;padding:.5rem 0;border-bottom:1px solid var(--border)">' +
        '<div data-action="toggle-feature" data-key="' + escAttr(t.key) + '" data-value="' + (!on) + '" style="position:relative;width:40px;height:22px;flex-shrink:0;cursor:pointer;background:' + bg + ';border-radius:22px;transition:.3s">' +
        '<div style="position:absolute;top:2px;left:2px;width:18px;height:18px;background:#fff;border-radius:50%;transition:.3s;transform:' + dot + '"></div></div>' +
        '<div style="flex:1"><div style="font-size:.8rem;font-weight:500">' + esc(t.label) + tag + '</div>' +
        '<div style="font-size:.7rem;color:var(--text3)">' + esc(t.desc) + '</div></div></div>';
    });

    html += '<div style="font-size:.85rem;font-weight:600;margin:1rem 0 .5rem">LLM Model</div>';
    html += '<div style="margin-bottom:.4rem"><label style="font-size:.75rem;color:var(--text2)">Provider</label>' +
      '<select id="setLlmProvider" style="' + inp + '">' +
      '<option value="local"' + (llm.provider === 'local' ? ' selected' : '') + '>Local (Ollama)</option>' +
      '<option value="openai"' + (llm.provider === 'openai' ? ' selected' : '') + '>OpenAI</option>' +
      '<option value="anthropic"' + (llm.provider === 'anthropic' ? ' selected' : '') + '>Anthropic</option></select></div>';
    html += '<div style="margin-bottom:.4rem"><label style="font-size:.75rem;color:var(--text2)">Model</label>' +
      '<select id="setLlmModel" style="' + inp + '"></select></div>';
    html += '<div id="modelInfo" style="font-size:.7rem;color:var(--text3);margin-bottom:.4rem"></div>';
    html += '<div style="margin-bottom:.4rem"><label style="font-size:.75rem;color:var(--text2)">Temperature</label>' +
      '<input id="setLlmTemp" type="number" step="0.1" min="0" max="2" value="' + escAttr(llm.temperature) + '" style="' + inp + '"></div>';

    html += '<div style="font-size:.85rem;font-weight:600;margin:1rem 0 .5rem">Retrieval</div>';
    html += '<div style="margin-bottom:.4rem"><label style="font-size:.75rem;color:var(--text2)">Top K (chunks per query)</label>' +
      '<input id="setTopK" type="number" min="1" max="30" value="' + escAttr(ret.top_k) + '" style="' + inp + '"></div>';

    html += '<div style="font-size:.85rem;font-weight:600;margin:1rem 0 .5rem">API Keys</div>';
    html += '<div style="font-size:.7rem;color:var(--text3);margin-bottom:.4rem">Keys are saved to .env and never shown in full</div>';
    [['openai', 'OpenAI', 'sk-...'], ['anthropic', 'Anthropic', 'sk-ant-...'], ['cohere', 'Cohere', '...']].forEach(([k, label, ph]) => {
      const hasKey = keys[k] && keys[k] !== '';
      const badge = hasKey ? '<span style="color:var(--green);font-size:.68rem;margin-left:.3rem">✓ set</span>' : '<span style="color:var(--text3);font-size:.68rem;margin-left:.3rem">not set</span>';
      html += '<div style="margin-bottom:.4rem"><label style="font-size:.75rem;color:var(--text2)">' + label + badge + '</label>' +
        '<input id="apiKey_' + k + '" type="password" placeholder="' + escAttr(ph) + '" value="' + escAttr(keys[k] || '') + '" style="' + inp + '"></div>';
    });
    html += '<button class="col-btn" data-action="save-api-keys" style="margin-top:.3rem">Save API Keys</button>';
    html += '<div id="apiKeyStatus" style="display:none;font-size:.75rem;margin-top:.3rem"></div>';

    html += '<button class="pb" data-action="save-settings" style="width:100%;padding:.45rem;text-align:center;margin-top:1rem">Save Settings</button>';
    html += '<div id="settingsStatus" style="display:none;margin-top:.4rem;font-size:.78rem;text-align:center"></div>';
    html += '<div style="margin-top:1rem;padding-top:.75rem;border-top:1px solid var(--border)">';
    html += '<div style="font-size:.75rem;color:var(--text3)">Cache: ' + cs.cached + ' cached, ' + cs.expired + ' expired</div>';
    html += '<button class="col-btn" data-action="clear-cache" style="margin-top:.3rem">Clear cache</button></div>';

    el.innerHTML = html;
    updateModelDropdown(llm.model);
  } catch (e) { el.innerHTML = '<p style="color:var(--red)">Error loading settings</p>'; }
}

function updateModelDropdown(currentModel) {
  const prov = $('setLlmProvider').value;
  const sel = $('setLlmModel');
  const info = $('modelInfo');
  if (!sel) return;
  sel.innerHTML = '';

  if (prov === 'local') {
    const installed = (modelsData.local && modelsData.local.installed) || [];
    const available = (modelsData.local && modelsData.local.available) || [];
    installed.forEach(m => {
      const opt = document.createElement('option'); opt.value = m; opt.textContent = m + ' (installed)';
      if (m === currentModel) opt.selected = true; sel.appendChild(opt);
    });
    available.forEach(m => {
      if (!installed.includes(m.name)) {
        const opt = document.createElement('option'); opt.value = m.name;
        opt.textContent = m.name + ' — ' + m.size + ' — ' + m.quality;
        if (m.name === currentModel) opt.selected = true; sel.appendChild(opt);
      }
    });
    info.textContent = installed.length + ' models installed. Select a new model and save — it will be downloaded automatically if needed.';
  } else {
    (modelsData[prov] || []).forEach(m => {
      const opt = document.createElement('option'); opt.value = m; opt.textContent = m;
      if (m === currentModel) opt.selected = true; sel.appendChild(opt);
    });
    info.textContent = prov === 'openai' ? 'Requires OpenAI API key.' : 'Requires Anthropic API key.';
  }
}

async function toggleFeature(key, value) {
  const body = { features: {} }; body.features[key] = value;
  await fetch('/settings', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
}

async function saveSettings() {
  const status = $('settingsStatus');
  const model = $('setLlmModel').value;
  const provider = $('setLlmProvider').value;
  const body = {
    llm: { provider, model, temperature: parseFloat($('setLlmTemp').value) || 0.1 },
    retrieval: { top_k: parseInt($('setTopK').value) || 8 },
  };
  status.style.display = 'block'; status.style.color = 'var(--accent2)'; status.textContent = 'Saving...';
  try {
    await fetch('/settings', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    if (provider === 'local') {
      const installed = (modelsData.local && modelsData.local.installed) || [];
      if (!installed.includes(model)) {
        status.style.color = 'var(--accent2)';
        status.textContent = 'Downloading model ' + model + '... (this may take a few minutes)';
        await fetch('/models/pull', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ model }) });
        status.style.color = 'var(--green)';
        status.textContent = '✓ Settings saved. Model ' + model + ' is downloading in the background.';
        return;
      }
    }
    status.style.color = 'var(--green)'; status.textContent = '✓ Settings saved and applied.';
  } catch (e) { status.style.color = 'var(--red)'; status.textContent = 'Error: ' + e.message; }
}

async function saveApiKeys() {
  const status = $('apiKeyStatus');
  const body = {};
  ['openai', 'anthropic', 'cohere'].forEach(k => {
    const v = $('apiKey_' + k).value;
    if (v && !v.startsWith('****')) body[k] = v;
  });
  if (!Object.keys(body).length) { status.style.display = 'block'; status.style.color = 'var(--text3)'; status.textContent = 'No new keys to save.'; return; }
  status.style.display = 'block'; status.style.color = 'var(--accent2)'; status.textContent = 'Saving...';
  try {
    await fetch('/settings/api-keys', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    status.style.color = 'var(--green)'; status.textContent = '✓ API keys saved to .env';
    setTimeout(() => loadSettings($('sbBody')), 1500);
  } catch (e) { status.style.color = 'var(--red)'; status.textContent = 'Error: ' + e.message; }
}

async function clearCache() {
  await fetch('/cache/clear', { method: 'POST' });
  loadSettings($('sbBody'));
}

// --- Chat ---
async function send() {
  const inp = $('qIn'); const q = inp.value.trim(); if (!q || sending) return;
  const w = $('welcome'); if (w) w.remove();
  sending = true; $('sendBtn').disabled = true;
  inp.value = ''; inp.style.height = 'auto';
  addMsg('user', q);
  const tid = addTyping();
  try {
    const r = await fetch('/query', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question: q, top_k: 5, use_history: true }) });
    const d = await r.json(); rmTyping(tid);
    lastSources = d.sources || [];
    addMsg('assistant', d.answer, d.sources, d.suggestions, d.latency_ms, d.meta);
    if (sbMode === 'sources') renderSources($('sbBody'));
  } catch (e) { rmTyping(tid); addMsg('assistant', 'Error: ' + e.message); }
  finally { sending = false; $('sendBtn').disabled = false; inp.focus(); }
}

function addMsg(role, content, sources, sugs, lat, meta) {
  const a = $('chatArea'); const d = document.createElement('div'); d.className = 'msg ' + role;
  let h = '<div class="av">' + (role === 'user' ? 'You' : 'AI') + '</div><div class="mb"><div class="bubble">';
  h += role === 'assistant' ? renderMd(content) : esc(content);
  h += '</div>';
  if (sources && sources.length) {
    h += '<div class="src-pills">';
    sources.forEach(s => {
      const rel = Math.round((s.relevance || 0) * 100); const cls = rel >= 70 ? 'hi' : '';
      const name = (s.file_name || s.file || '').split('/').pop();
      if (s.file_url) { h += '<a class="sp ' + cls + '" href="' + escAttr(s.file_url) + '" target="_blank" title="Open ' + escAttr(name) + '">' + esc(name) + ' ' + rel + '%</a>'; }
      else { h += '<span class="sp ' + cls + '" data-action="open-sources">' + esc(name) + ' ' + rel + '%</span>'; }
    });
    h += '</div>';
  }
  if (sugs && sugs.length) { h += '<div class="suggs">'; sugs.forEach(s => { h += '<span class="sg" data-action="ask-sug">' + esc(s) + '</span>'; }); h += '</div>'; }
  if (lat || meta) {
    const m = meta || {};
    const metaParts = [];
    if (lat) metaParts.push((lat / 1000).toFixed(1) + 's');
    if (sources) metaParts.push(sources.length + ' sources');
    if (m.strategy === 'agentic') metaParts.push('🧠 agent');
    else if (m.strategy === 'broad') metaParts.push('📊 broad scan');
    else if (m.strategy === 'specific') metaParts.push('🎯 targeted');
    if (m.used_cache) metaParts.push('⚡ cached');
    if (m.used_graph) metaParts.push('🔗 graph');
    if (m.cost_usd > 0) metaParts.push('$' + m.cost_usd.toFixed(4));
    if (m.total_session_cost > 0) metaParts.push('session: $' + m.total_session_cost.toFixed(4));
    if (m.model) metaParts.push(esc(m.model));
    h += '<div class="msg-meta">' + metaParts.join(' · ') + '</div>';
  }
  h += '</div>'; d.innerHTML = h; a.appendChild(d);
  if (role === 'assistant') enhanceRendered(d);
  a.scrollTop = a.scrollHeight;
}

function addTyping() {
  const a = $('chatArea'); const d = document.createElement('div'); const id = 't-' + Date.now();
  d.id = id; d.className = 'msg assistant';
  d.innerHTML = '<div class="av">AI</div><div class="mb"><div class="bubble"><div class="typing"><span></span><span></span><span></span></div></div></div>';
  a.appendChild(d); a.scrollTop = a.scrollHeight; return id;
}
function rmTyping(id) { const e = $(id); if (e) e.remove(); }

// --- Export / clear ---
async function exportChat() {
  try {
    const r = await fetch('/export'); const d = await r.json();
    const b = new Blob([d.markdown], { type: 'text/markdown' });
    const u = URL.createObjectURL(b);
    const a = document.createElement('a'); a.href = u; a.download = 'rag-session.md'; a.click();
    URL.revokeObjectURL(u);
  } catch (e) { alert('Export failed: ' + e.message); }
}

async function clearHist() {
  await fetch('/history/clear', { method: 'POST' });
  $('chatArea').innerHTML = ''; lastSources = []; loadWelcome();
}

// --- Welcome ---
function loadWelcome() {
  let el = $('wcCards');
  if (!el) {
    $('chatArea').innerHTML = '<div class="welcome" id="welcome"><h2>Chat with your documents</h2><p>Ask anything about your indexed files. Answers cite their sources.</p><div class="wc-grid" id="wcCards"></div></div>';
    el = $('wcCards');
  }
  const samples = [
    { t: 'Summarize', d: 'Get an overview of all documents', q: 'Give me a summary of all the documents you have' },
    { t: 'Find details', d: 'Search for specific information', q: 'What are the key dates and confirmation numbers?' },
    { t: 'Compare', d: 'Compare across documents', q: 'What are all the costs and payments mentioned?' },
    { t: 'Timeline', d: 'Chronological order', q: 'What is the chronological timeline of events?' },
  ];
  el.innerHTML = '';
  samples.forEach(s => {
    const card = document.createElement('div');
    card.className = 'wc';
    card.innerHTML = '<b>' + esc(s.t) + '</b><span>' + esc(s.d) + '</span>';
    card.addEventListener('click', () => { $('qIn').value = s.q; send(); });
    el.appendChild(card);
  });
}

// --- Delegated events ---
document.addEventListener('click', e => {
  const t = e.target.closest('[data-action]');
  if (!t) return;
  const a = t.dataset.action;
  if (a === 'show-entity') showEntity(t.dataset.id);
  else if (a === 'back-graph') loadGraph($('sbBody'));
  else if (a === 'use-col') { switchCol(t.dataset.name).then(() => loadCollections($('sbBody'))); }
  else if (a === 'delete-col') deleteCol(t.dataset.name);
  else if (a === 'reindex-col') reindexCol(t.dataset.name);
  else if (a === 'add-feed') addFeed(t.dataset.col);
  else if (a === 'remove-feed') { e.stopPropagation(); removeFeed(t.dataset.col, t.dataset.url); }
  else if (a === 'fetch-feeds') fetchFeeds(t.dataset.col);
  else if (a === 'open-browser') openBrowser(t.dataset.path);
  else if (a === 'select-folder') { e.stopPropagation(); selectFolder(t.dataset.path); }
  else if (a === 'create-col') createCol();
  else if (a === 'save-api-keys') saveApiKeys();
  else if (a === 'save-settings') saveSettings();
  else if (a === 'clear-cache') clearCache();
  else if (a === 'toggle-feature') { toggleFeature(t.dataset.key, t.dataset.value === 'true').then(() => loadSettings($('sbBody'))); }
  else if (a === 'ask-sug') { $('qIn').value = t.textContent; send(); }
  else if (a === 'open-sources') openSB('sources');
});

document.addEventListener('input', e => {
  if (e.target.id === 'graphSearch') searchGraph(e.target.value);
});

document.addEventListener('change', e => {
  if (e.target.id === 'setLlmProvider') updateModelDropdown();
});

// --- Header wiring ---
document.querySelectorAll('.hdr [data-panel]').forEach(btn =>
  btn.addEventListener('click', () => openSB(btn.dataset.panel)));
$('exportBtn').addEventListener('click', exportChat);
$('clearBtn').addEventListener('click', clearHist);
$('thBtn').addEventListener('click', togTheme);
$('sbCloseBtn').addEventListener('click', closeSB);
$('sendBtn').addEventListener('click', send);
$('colSel').addEventListener('change', e => switchCol(e.target.value));

// --- Init ---
mermaid.initialize({ theme: 'dark', startOnLoad: false, securityLevel: 'strict' });
loadStatus(); loadWelcome();
(async () => {
  try {
    const r = await fetch('/history'); const d = await r.json();
    if (d.messages && d.messages.length) {
      const w = $('welcome'); if (w) w.remove();
      d.messages.forEach(m => addMsg(m.role, m.content));
    }
  } catch (e) { /* server starting up */ }
})();
