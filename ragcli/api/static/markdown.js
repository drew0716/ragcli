// Safe markdown rendering: markdown-it -> DOMPurify, with Mermaid (strict)
// and validated Chart.js blocks. Replaces the old hand-rolled regex renderer.

const md = window.markdownit({ html: false, linkify: true, breaks: false });

// Open links in a new tab.
const defaultLinkRender = md.renderer.rules.link_open ||
  ((tokens, idx, options, env, self) => self.renderToken(tokens, idx, options));
md.renderer.rules.link_open = (tokens, idx, options, env, self) => {
  tokens[idx].attrSet('target', '_blank');
  tokens[idx].attrSet('rel', 'noopener');
  return defaultLinkRender(tokens, idx, options, env, self);
};

function esc(t) { const d = document.createElement('div'); d.textContent = t == null ? '' : String(t); return d.innerHTML; }
function escAttr(t) {
  return String(t == null ? '' : t)
    .replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/'/g, '&#39;')
    .replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// Fenced mermaid/chart blocks are pulled out BEFORE markdown rendering; the
// raw block text never travels through HTML. enhanceRendered() mounts them.
let blockCounter = 0;
const pendingBlocks = new Map();

function extractSpecialBlocks(text) {
  return text
    .replace(/```mermaid\n([\s\S]*?)```/g, (_, code) => {
      const id = 'blk-' + (blockCounter++);
      pendingBlocks.set(id, { type: 'mermaid', code: code.trim() });
      return '\n\n<!--block:' + id + '-->\n\n';
    })
    .replace(/```chart\n([\s\S]*?)```/g, (_, json) => {
      const id = 'blk-' + (blockCounter++);
      pendingBlocks.set(id, { type: 'chart', code: json.trim() });
      return '\n\n<!--block:' + id + '-->\n\n';
    });
}

function renderMd(text) {
  if (!text) return '';
  const source = extractSpecialBlocks(String(text));
  let html = md.render(source);
  // Reinsert placeholders as mount-point divs (markdown-it escaped the comment).
  html = html.replace(/&lt;!--block:(blk-\d+)--&gt;/g,
    (_, id) => '<div class="special-block" data-block-id="' + escAttr(id) + '"></div>');
  return DOMPurify.sanitize(html, { ADD_ATTR: ['target'] });
}

function sanitizeChartConfig(raw) {
  const ALLOWED_TYPES = ['bar', 'doughnut', 'line', 'pie'];
  let cfg;
  try { cfg = JSON.parse(raw); } catch (e) { return null; }
  if (!cfg || typeof cfg !== 'object' || !ALLOWED_TYPES.includes(cfg.type)) return null;
  // Deep-clone keeping only plain data — drops functions, getters, and
  // prototype-polluting keys an LLM (or poisoned document) might emit.
  const plain = (v, depth) => {
    if (depth > 8) return undefined;
    if (v === null || ['string', 'number', 'boolean'].includes(typeof v)) return v;
    if (Array.isArray(v)) return v.map(x => plain(x, depth + 1)).filter(x => x !== undefined);
    if (typeof v === 'object') {
      const out = {};
      for (const k of Object.keys(v)) {
        if (k === '__proto__' || k === 'constructor' || k === 'prototype') continue;
        const p = plain(v[k], depth + 1);
        if (p !== undefined) out[k] = p;
      }
      return out;
    }
    return undefined;
  };
  return { type: cfg.type, data: plain(cfg.data, 0) || { labels: [], datasets: [] }, options: plain(cfg.options, 0) || {} };
}

function mountMermaid(el, code) {
  // Light cleanup for common LLM output issues (quoting labels, stray bold).
  let clean = code
    .replace(/(\w+)\[([^\]"]*[()/&,#:;].*?)\]/g, (_, node, label) => node + '["' + label.replace(/"/g, "'") + '"]')
    .replace(/(\w+)\(([^)"]*[[\]/&,#:;].*?)\)/g, (_, node, label) => node + '("' + label.replace(/"/g, "'") + '")')
    .replace(/\*\*/g, '');
  const fallback = () => {
    el.innerHTML = '<pre class="mermaid-fallback">' + esc(clean) + '</pre>';
  };
  try {
    mermaid.render('m-' + Math.random().toString(36).slice(2, 8), clean).then(({ svg }) => {
      el.innerHTML = DOMPurify.sanitize(svg, { USE_PROFILES: { svg: true, svgFilters: true } });
      el.classList.add('mermaid');
    }).catch(fallback);
  } catch (e) { fallback(); }
}

function mountChart(el, raw) {
  const cfg = sanitizeChartConfig(raw);
  if (!cfg) return;
  const wrap = document.createElement('div');
  wrap.style.cssText = 'max-width:500px;margin:.5rem 0';
  const canvas = document.createElement('canvas');
  canvas.height = 250;
  wrap.appendChild(canvas);
  el.appendChild(wrap);
  try { new Chart(canvas, cfg); } catch (e) { /* invalid config — skip */ }
}

// Auto-detect tables with chartable numeric data (costs/amounts, not dates/IDs)
function addVisualizeButtons(root) {
  root.querySelectorAll('table').forEach(table => {
    if (table.dataset.vizDone) return;
    table.dataset.vizDone = '1';
    const text = table.textContent || '';
    const moneyMatches = text.match(/[$£€]\s*[\d,.]+/g);
    const headerText = Array.from(table.querySelectorAll('th')).map(th => th.textContent).join(' ');
    const numHeaders = /(?:cost|amount|price|total|budget|expense|fee|rate|salary|revenue)/i.test(headerText);
    if (!((moneyMatches && moneyMatches.length >= 2) || numHeaders)) return;

    const holder = document.createElement('div');
    holder.style.cssText = 'margin:.4rem 0';
    const btn = document.createElement('button');
    btn.className = 'col-btn';
    btn.style.fontSize = '.72rem';
    btn.textContent = '📊 Visualize';
    const canvas = document.createElement('canvas');
    canvas.style.cssText = 'display:none;max-width:500px;margin-top:.4rem';
    canvas.height = 250;
    holder.appendChild(btn);
    holder.appendChild(canvas);
    table.insertAdjacentElement('afterend', holder);
    btn.addEventListener('click', () => chartFromTable(table, canvas));
  });
}

// Call after inserting renderMd() output into the DOM: mounts mermaid/chart
// blocks and adds Visualize buttons to financial tables.
function enhanceRendered(root) {
  root.querySelectorAll('.special-block[data-block-id]').forEach(el => {
    const block = pendingBlocks.get(el.dataset.blockId);
    if (!block) return;
    pendingBlocks.delete(el.dataset.blockId);
    el.classList.remove('special-block');
    if (block.type === 'mermaid') mountMermaid(el, block.code);
    else if (block.type === 'chart') mountChart(el, block.code);
  });
  addVisualizeButtons(root);
}
