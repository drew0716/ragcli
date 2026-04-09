"""Web UI HTML for the RAG chat interface."""

UI_HTML = r"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ragcli</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<style>
:root{
  --bg:#0f172a;--bg2:#1e293b;--bg3:#334155;
  --text:#e2e8f0;--text2:#94a3b8;--text3:#64748b;
  --accent:#3b82f6;--accent2:#60a5fa;--accent-h:#2563eb;
  --green:#4ade80;--green-bg:#14532d;
  --red:#f87171;--red-bg:#7f1d1d;--yellow:#fbbf24;
  --border:#334155;--border2:#475569;
  --R:12px;--Rs:8px;
}
[data-theme="light"]{
  --bg:#f8fafc;--bg2:#fff;--bg3:#e2e8f0;
  --text:#1e293b;--text2:#475569;--text3:#94a3b8;
  --border:#e2e8f0;--border2:#cbd5e1;
}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:var(--bg);color:var(--text);height:100vh;display:flex;flex-direction:column;overflow:hidden}

/* HEADER */
.hdr{background:var(--bg2);border-bottom:1px solid var(--border);padding:.6rem 1rem;display:flex;align-items:center;justify-content:space-between;flex-shrink:0;gap:.75rem;flex-wrap:wrap}
.hdr-l{display:flex;align-items:center;gap:.75rem}
.logo{font-size:1.15rem;font-weight:700;white-space:nowrap}.logo span{color:var(--accent2)}
.dot{width:8px;height:8px;border-radius:50%;background:var(--green);display:inline-block}
.st{font-size:.72rem;color:var(--text3)}
.hdr-r{display:flex;align-items:center;gap:.4rem;flex-wrap:wrap}
.pb{padding:.3rem .65rem;border-radius:999px;border:1px solid var(--border);background:var(--bg);color:var(--text2);font-size:.78rem;cursor:pointer;transition:all .15s;white-space:nowrap}
.pb:hover{border-color:var(--accent2);color:var(--accent2)}
.pb.act{background:var(--accent);color:#fff;border-color:var(--accent)}
select.cs{padding:.3rem .65rem;border-radius:999px;border:1px solid var(--border);background:var(--bg);color:var(--text);font-size:.78rem;cursor:pointer}

/* LAYOUT: chat + sidebar */
.main{flex:1;display:flex;overflow:hidden}
.chat-col{flex:1;display:flex;flex-direction:column;min-width:0}
.chat-area{flex:1;overflow-y:auto;padding:1rem 1rem .5rem;scroll-behavior:smooth}
.chat-area::-webkit-scrollbar{width:6px}
.chat-area::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px}

/* SIDEBAR */
.sidebar{width:380px;background:var(--bg2);border-left:1px solid var(--border);display:flex;flex-direction:column;overflow:hidden;transition:width .25s,opacity .25s;flex-shrink:0}
.sidebar.closed{width:0;opacity:0;overflow:hidden;border:none}
.sb-hdr{padding:.75rem 1rem;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between;flex-shrink:0}
.sb-hdr h3{font-size:.9rem;font-weight:600}
.sb-close{background:none;border:none;color:var(--text2);font-size:1.1rem;cursor:pointer}
.sb-tabs{display:flex;border-bottom:1px solid var(--border);flex-shrink:0}
.sb-tab{flex:1;padding:.5rem;text-align:center;font-size:.78rem;color:var(--text3);cursor:pointer;border-bottom:2px solid transparent;transition:all .15s}
.sb-tab.act{color:var(--accent2);border-bottom-color:var(--accent2)}
.sb-body{flex:1;overflow-y:auto;padding:.75rem 1rem}

/* Source items in sidebar */
.src-item{background:var(--bg);border:1px solid var(--border);border-radius:var(--Rs);padding:.75rem;margin-bottom:.5rem;transition:border-color .15s}
.src-item:hover{border-color:var(--border2)}
.src-top{display:flex;justify-content:space-between;align-items:center;margin-bottom:.25rem}
.src-name{font-weight:600;font-size:.85rem}
.src-name a{color:var(--accent2);text-decoration:none}.src-name a:hover{text-decoration:underline}
.src-badge{font-size:.72rem;padding:.1rem .45rem;border-radius:999px;background:var(--bg3);color:var(--text2)}
.src-badge.hi{background:var(--green-bg);color:var(--green)}
.src-section{font-size:.75rem;color:var(--text3);margin-bottom:.4rem}
.src-content{font-size:.8rem;color:var(--text2);line-height:1.55;border-top:1px solid var(--border);padding-top:.4rem}
.src-open{display:inline-block;margin-top:.4rem;font-size:.75rem;color:var(--accent2);text-decoration:none;cursor:pointer}
.src-open:hover{text-decoration:underline}

/* Collection manager in sidebar */
.col-item{display:flex;justify-content:space-between;align-items:center;padding:.5rem .75rem;border:1px solid var(--border);border-radius:var(--Rs);margin-bottom:.4rem;font-size:.85rem}
.col-item.active{border-color:var(--accent2);background:rgba(59,130,246,.08)}
.col-name{font-weight:500}.col-count{color:var(--text3);font-size:.75rem}
.col-actions{display:flex;gap:.3rem}
.col-btn{padding:.2rem .5rem;border-radius:4px;border:1px solid var(--border);background:var(--bg);color:var(--text2);font-size:.72rem;cursor:pointer}
.col-btn:hover{border-color:var(--accent2);color:var(--accent2)}
.col-btn.del:hover{border-color:var(--red);color:var(--red)}
.col-create{display:flex;gap:.4rem;margin-top:.75rem}
.col-create input{flex:1;padding:.4rem .6rem;border-radius:var(--Rs);border:1px solid var(--border);background:var(--bg);color:var(--text);font-size:.8rem}

/* Upload panel in sidebar */
.upload-zone{border:2px dashed var(--border);border-radius:var(--R);padding:2rem 1rem;text-align:center;cursor:pointer;transition:border-color .2s}
.upload-zone:hover,.upload-zone.drag{border-color:var(--accent2)}
.upload-zone h4{margin-bottom:.25rem}
.upload-zone p{font-size:.8rem;color:var(--text3)}
.upload-zone input{display:none}
.upload-progress{margin-top:.75rem}
.upload-file{display:flex;align-items:center;justify-content:space-between;padding:.5rem .75rem;border:1px solid var(--border);border-radius:var(--Rs);margin-bottom:.4rem;font-size:.82rem}
.upload-file .uf-name{font-weight:500;flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.upload-file .uf-status{font-size:.75rem;margin-left:.5rem;white-space:nowrap}
.uf-status.ok{color:var(--green)}.uf-status.err{color:var(--red)}.uf-status.prog{color:var(--accent2)}

/* MESSAGES */
.msg{max-width:780px;margin:0 auto .75rem;display:flex;gap:.6rem}
.msg.user{flex-direction:row-reverse}
.av{width:30px;height:30px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:.7rem;font-weight:700;flex-shrink:0}
.msg.user .av{background:var(--accent);color:#fff}
.msg.assistant .av{background:var(--bg3);color:var(--accent2)}
.mb{flex:1;min-width:0}
.bubble{padding:.75rem 1rem;border-radius:var(--R);line-height:1.7;font-size:.92rem}
.msg.user .bubble{background:var(--accent);color:#fff;border-bottom-right-radius:4px}
.msg.assistant .bubble{background:var(--bg2);border:1px solid var(--border);border-bottom-left-radius:4px}
.bubble p{margin-bottom:.5rem}.bubble p:last-child{margin-bottom:0}
.bubble strong{font-weight:600}.bubble a{color:var(--accent2);text-decoration:underline;text-underline-offset:2px}
.bubble ul,.bubble ol{margin:.4rem 0 .5rem 1.5rem;padding-left:.5rem}.bubble li{margin-bottom:.25rem;line-height:1.5}.bubble ul ul,.bubble ol ol,.bubble ul ol,.bubble ol ul{margin:.2rem 0 .2rem 1rem}
.bubble code{background:var(--bg);padding:.1rem .3rem;border-radius:4px;font-size:.85em;font-family:'SF Mono',Menlo,monospace}
.bubble pre{background:var(--bg);border:1px solid var(--border);border-radius:var(--Rs);padding:.6rem;margin:.4rem 0;overflow-x:auto}
.bubble pre code{background:none;padding:0}
.bubble blockquote{border-left:3px solid var(--accent);padding-left:.6rem;color:var(--text2);margin:.4rem 0}
.bubble table{border-collapse:collapse;width:100%;margin:.4rem 0;font-size:.82rem}
.bubble th,.bubble td{border:1px solid var(--border);padding:.35rem .5rem}
.bubble th{background:var(--bg);font-weight:600;color:var(--accent2)}
.bubble table{font-size:.82rem;border:1px solid var(--border);border-radius:var(--Rs);overflow:hidden}
.bubble tr:nth-child(even){background:rgba(255,255,255,.03)}
.bubble td:first-child{font-weight:500}
.mermaid{margin:.5rem 0;text-align:center}
.mermaid svg{max-width:100%}

/* Source pills inline */
.src-pills{display:flex;gap:.3rem;margin-top:.4rem;flex-wrap:wrap}
.sp{font-size:.72rem;padding:.15rem .5rem;border-radius:999px;background:var(--bg);border:1px solid var(--border);color:var(--text2);cursor:pointer;transition:all .15s;text-decoration:none}
.sp:hover{border-color:var(--accent2);color:var(--accent2)}
.sp.hi{border-color:var(--green);color:var(--green)}

/* Suggestions */
.suggs{display:flex;gap:.35rem;margin-top:.4rem;flex-wrap:wrap}
.sg{font-size:.78rem;padding:.25rem .65rem;border-radius:999px;border:1px solid var(--border);background:var(--bg2);color:var(--text2);cursor:pointer;transition:all .15s}
.sg:hover{border-color:var(--accent2);color:var(--accent2);background:var(--bg)}

.msg-meta{font-size:.68rem;color:var(--text3);margin-top:.25rem}

/* INPUT */
.input-area{background:var(--bg2);border-top:1px solid var(--border);padding:.6rem 1rem;flex-shrink:0}
.input-row{max-width:780px;margin:0 auto;display:flex;gap:.5rem;align-items:flex-end}
.input-row textarea{flex:1;padding:.55rem .85rem;border-radius:var(--R);border:1px solid var(--border);background:var(--bg);color:var(--text);font-size:.92rem;outline:none;resize:none;min-height:42px;max-height:120px;font-family:inherit;line-height:1.4;transition:border-color .15s}
.input-row textarea:focus{border-color:var(--accent2)}
.input-row textarea::placeholder{color:var(--text3)}
.send{width:42px;height:42px;border-radius:50%;border:none;background:var(--accent);color:#fff;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:background .15s;flex-shrink:0}
.send:hover{background:var(--accent-h)}.send:disabled{background:var(--bg3);cursor:not-allowed}
.send svg{width:18px;height:18px}

/* Typing */
.typing{display:flex;gap:4px;padding:.4rem 0}
.typing span{width:7px;height:7px;border-radius:50%;background:var(--text3);animation:blink 1.4s infinite both}
.typing span:nth-child(2){animation-delay:.2s}
.typing span:nth-child(3){animation-delay:.4s}
@keyframes blink{0%,80%,100%{opacity:.3}40%{opacity:1}}

/* Welcome */
.welcome{max-width:600px;margin:3rem auto;text-align:center}
.welcome h2{font-size:1.4rem;margin-bottom:.4rem}
.welcome p{color:var(--text2);margin-bottom:1.25rem;font-size:.9rem}
.wc-grid{display:grid;grid-template-columns:1fr 1fr;gap:.6rem}
.wc{background:var(--bg2);border:1px solid var(--border);border-radius:var(--Rs);padding:.85rem;text-align:left;cursor:pointer;transition:border-color .15s}
.wc:hover{border-color:var(--accent2)}
.wc b{font-size:.85rem;display:block;margin-bottom:.15rem}.wc span{font-size:.78rem;color:var(--text2)}

@media(max-width:768px){
  .sidebar{position:fixed;right:0;top:0;bottom:0;z-index:50;width:100%}
  .sidebar.closed{width:0}
  .wc-grid{grid-template-columns:1fr}
}
</style>
</head>
<body>

<!-- HEADER -->
<div class="hdr">
  <div class="hdr-l">
    <div class="logo"><span>rag</span>cli</div>
    <span class="dot"></span>
    <span class="st" id="stText">connecting...</span>
  </div>
  <div class="hdr-r">
    <select class="cs" id="colSel" onchange="switchCol(this.value)"><option>default</option></select>
    <button class="pb" onclick="openSB('sources')">Sources</button>
    <button class="pb" onclick="openSB('graph')">Knowledge</button>
    <button class="pb" onclick="openSB('docs')">Docs</button>
    <button class="pb" onclick="openSB('collections')">Collections</button>
    <button class="pb" onclick="exportChat()">Export</button>
    <button class="pb" onclick="clearHist()">Clear</button>
    <button class="pb" onclick="openSB('settings')">Settings</button>
    <button class="pb" id="thBtn" onclick="togTheme()">Light</button>
  </div>
</div>

<!-- MAIN -->
<div class="main">
  <!-- Chat -->
  <div class="chat-col">
    <div class="chat-area" id="chatArea">
      <div class="welcome" id="welcome">
        <h2>Chat with your documents</h2>
        <p>Ask anything about your indexed files. Answers cite their sources.</p>
        <div class="wc-grid" id="wcCards"></div>
      </div>
    </div>
    <div class="input-area">
      <div class="input-row">
        <textarea id="qIn" placeholder="Ask a question..." rows="1" oninput="autoR(this)"></textarea>
        <button class="send" id="sendBtn" onclick="send()">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/></svg>
        </button>
      </div>
    </div>
  </div>

  <!-- Sidebar -->
  <div class="sidebar closed" id="sidebar">
    <div class="sb-hdr">
      <h3 id="sbTitle">Sources</h3>
      <button class="sb-close" onclick="closeSB()">&times;</button>
    </div>
    <div class="sb-body" id="sbBody"></div>
  </div>
</div>

<script>
// State
let sending=false, lastSources=[], lastSugs=[], theme='dark', sbMode='';

// Textarea auto-resize
function autoR(el){el.style.height='auto';el.style.height=Math.min(el.scrollHeight,120)+'px'}
document.getElementById('qIn').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send()}});

// Theme
function togTheme(){
  theme=theme==='dark'?'light':'dark';
  document.documentElement.setAttribute('data-theme',theme);
  document.getElementById('thBtn').textContent=theme==='dark'?'Light':'Dark';
}

// Status + collections
async function loadStatus(){
  try{
    const[sr,cr]=await Promise.all([fetch('/status'),fetch('/collections')]);
    const s=await sr.json(), c=await cr.json();
    document.getElementById('stText').textContent=s.total_documents+' docs \u00b7 '+s.total_chunks+' chunks';
    const sel=document.getElementById('colSel');sel.innerHTML='';
    c.collections.forEach(col=>{
      const o=document.createElement('option');o.value=col.name;o.textContent=col.name+' ('+col.chunks+')';
      if(col.name===c.active)o.selected=true;sel.appendChild(o);
    });
  }catch(e){document.getElementById('stText').textContent='error'}
}

async function switchCol(name){
  const r=await fetch('/collections/switch',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name})});
  const d=await r.json();
  document.getElementById('chatArea').innerHTML='';lastSources=[];
  // Show which collection is now active
  const area=document.getElementById('chatArea');
  const notice=document.createElement('div');
  notice.style.cssText='text-align:center;padding:.5rem;font-size:.78rem;color:var(--text3);margin-bottom:.5rem';
  notice.textContent='Switched to collection "'+name+'" \u2014 '+(d.chunks||0)+' chunks'+(d.docs_dir?' from '+d.docs_dir:'');
  area.appendChild(notice);
  loadStatus();loadWelcome();
}

// Sidebar
function openSB(mode){
  sbMode=mode;
  const sb=document.getElementById('sidebar');sb.classList.remove('closed');
  document.getElementById('sbTitle').textContent={sources:'Sources',graph:'Knowledge Graph',docs:'Documents',collections:'Collections',settings:'Settings'}[mode]||mode;
  const body=document.getElementById('sbBody');
  if(mode==='sources')renderSources(body);
  else if(mode==='graph')loadGraph(body);
  else if(mode==='docs')loadDocs(body);
  else if(mode==='collections')loadCollections(body);
  else if(mode==='settings')loadSettings(body);
}
function closeSB(){document.getElementById('sidebar').classList.add('closed');sbMode=''}

// Sources sidebar
function renderSources(el){
  if(!lastSources.length){el.innerHTML='<p style="color:var(--text3)">No sources yet. Ask a question first.</p>';return}
  el.innerHTML='';
  lastSources.forEach(s=>{
    const rel=Math.round((s.relevance||0)*100);
    const cls=rel>=70?'hi':'';
    const d=document.createElement('div');d.className='src-item';
    d.innerHTML='<div class="src-top"><span class="src-name"><a href="'+esc(s.file_url||'#')+'" target="_blank">'+esc(s.file_name||s.file)+'</a></span><span class="src-badge '+cls+'">'+rel+'%</span></div>'+
      '<div class="src-section">'+esc(s.section||'')+'</div>'+
      '<div class="src-content">'+renderMd(s.content||'')+'</div>'+
      (s.file_url?'<a class="src-open" href="'+esc(s.file_url)+'" target="_blank">Open document &rarr;</a>':'');
    el.appendChild(d);
  });
}

// Knowledge graph sidebar
async function loadGraph(el){
  el.innerHTML='<p style="color:var(--text3)">Loading...</p>';
  try{
    const r=await fetch('/graph');const d=await r.json();
    const stats=d.stats||{};const entities=d.entities||[];
    let html='';

    // Stats summary
    html+='<div style="display:flex;gap:.5rem;margin-bottom:.75rem;flex-wrap:wrap">';
    html+='<div style="background:var(--bg);border:1px solid var(--border);border-radius:var(--Rs);padding:.4rem .6rem;font-size:.75rem"><b>'+stats.total_nodes+'</b> nodes</div>';
    html+='<div style="background:var(--bg);border:1px solid var(--border);border-radius:var(--Rs);padding:.4rem .6rem;font-size:.75rem"><b>'+stats.total_edges+'</b> connections</div>';
    html+='</div>';

    // Entity type breakdown
    const types=stats.entity_types||{};
    const typeKeys=Object.keys(types).filter(t=>t!=='document').sort((a,b)=>types[b]-types[a]);
    if(typeKeys.length){
      html+='<div style="margin-bottom:.75rem">';
      typeKeys.forEach(t=>{
        const colors={money:'#4ade80',date:'#60a5fa',confirmation:'#fbbf24',person:'#f472b6',location:'#a78bfa',hotel:'#fb923c',airline:'#22d3ee',organization:'#34d399',email:'#94a3b8',phone:'#94a3b8'};
        const c=colors[t]||'var(--text2)';
        html+='<span style="display:inline-block;font-size:.7rem;padding:.15rem .45rem;border-radius:999px;border:1px solid '+c+';color:'+c+';margin:0 .25rem .25rem 0">'+esc(t)+' ('+types[t]+')</span>';
      });
      html+='</div>';
    }

    // Search
    html+='<div style="margin-bottom:.75rem"><input id="graphSearch" placeholder="Search entities..." style="width:100%;padding:.4rem .6rem;border-radius:var(--Rs);border:1px solid var(--border);background:var(--bg);color:var(--text);font-size:.8rem" oninput="searchGraph(this.value)"></div>';
    html+='<div id="graphResults">';

    // Entity list
    if(!entities.length){
      html+='<p style="color:var(--text3);font-size:.82rem">No entities yet. Ingest documents to build the knowledge graph.</p>';
    }else{
      entities.slice(0,50).forEach(e=>{
        const srcNames=e.sources.map(s=>s.split('/').pop()).slice(0,3).join(', ');
        const colors={money:'#4ade80',date:'#60a5fa',confirmation:'#fbbf24',person:'#f472b6',location:'#a78bfa',hotel:'#fb923c',airline:'#22d3ee',organization:'#34d399'};
        const c=colors[e.type]||'var(--text2)';
        html+='<div class="src-item" style="cursor:pointer" onclick="showEntity(\''+esc(e.id)+'\')">';
        html+='<div style="display:flex;justify-content:space-between;align-items:center">';
        html+='<span style="font-weight:600;font-size:.82rem">'+esc(e.value)+'</span>';
        html+='<span style="font-size:.68rem;padding:.1rem .4rem;border-radius:999px;border:1px solid '+c+';color:'+c+'">'+esc(e.type)+'</span>';
        html+='</div>';
        html+='<div style="font-size:.72rem;color:var(--text3);margin-top:.15rem">'+e.connections+' connections \u00b7 '+esc(srcNames)+'</div>';
        html+='</div>';
      });
    }
    html+='</div>';
    el.innerHTML=html;
  }catch(e){el.innerHTML='<p style="color:var(--red)">Error loading graph</p>'}
}

let graphSearchTimer=null;
async function searchGraph(q){
  clearTimeout(graphSearchTimer);
  const results=document.getElementById('graphResults');
  if(!results)return;
  if(!q||q.length<2){
    // Reload just the results portion, not the whole panel
    graphSearchTimer=setTimeout(async()=>{
      try{
        const r=await fetch('/graph');const d=await r.json();
        const entities=d.entities||[];
        results.innerHTML='';
        entities.slice(0,50).forEach(e=>{
          const srcNames=e.sources.map(s=>s.split('/').pop()).slice(0,3).join(', ');
          const colors={money:'#4ade80',date:'#60a5fa',confirmation:'#fbbf24',person:'#f472b6',location:'#a78bfa',hotel:'#fb923c',airline:'#22d3ee',organization:'#34d399'};
          const c=colors[e.type]||'var(--text2)';
          results.innerHTML+='<div class="src-item" style="cursor:pointer" onclick="showEntity(\''+esc(e.id)+'\')"><div style="display:flex;justify-content:space-between;align-items:center"><span style="font-weight:600;font-size:.82rem">'+esc(e.value)+'</span><span style="font-size:.68rem;padding:.1rem .4rem;border-radius:999px;border:1px solid '+c+';color:'+c+'">'+esc(e.type)+'</span></div><div style="font-size:.72rem;color:var(--text3);margin-top:.15rem">'+e.connections+' connections \u00b7 '+esc(srcNames)+'</div></div>';
        });
      }catch(e){}
    },300);
    return;
  }
  // Debounce search
  graphSearchTimer=setTimeout(async()=>{
  try{
    const r=await fetch('/graph/search?q='+encodeURIComponent(q));
    const d=await r.json();
    let html='';
    if(d.entities&&d.entities.length){
      d.entities.forEach(e=>{
        const srcNames=(e.sources||[]).map(s=>s.split('/').pop()).slice(0,3).join(', ');
        html+='<div class="src-item">';
        html+='<div style="font-weight:600;font-size:.82rem">'+esc(e.entity)+'</div>';
        html+='<div style="font-size:.72rem;color:var(--text3)">'+esc(e.type)+' \u00b7 '+esc(srcNames)+'</div>';
        html+='</div>';
      });
    }
    if(d.related_sources&&d.related_sources.length){
      html+='<div style="font-size:.75rem;font-weight:600;margin:.5rem 0 .25rem;color:var(--text2)">Related documents</div>';
      d.related_sources.forEach(s=>{
        html+='<div style="font-size:.78rem;padding:.25rem 0;color:var(--text2)">'+esc(s.split('/').pop())+'</div>';
      });
    }
    if(!html)html='<p style="color:var(--text3);font-size:.82rem">No matches</p>';
    results.innerHTML=html;
  }catch(e){results.innerHTML='<p>Search error</p>'}
  },300);
}

async function showEntity(id){
  const body=document.getElementById('sbBody');
  try{
    const r=await fetch('/graph/entity/'+encodeURIComponent(id));
    const d=await r.json();
    if(!d.entity){body.innerHTML='<p>Entity not found</p>';return}
    let html='<button class="pb" onclick="loadGraph(document.getElementById(\'sbBody\'))" style="margin-bottom:.75rem">&larr; Back</button>';
    html+='<div style="font-size:1rem;font-weight:700;margin-bottom:.25rem">'+esc(d.entity.value)+'</div>';
    html+='<div style="font-size:.78rem;color:var(--text3);margin-bottom:.75rem">Type: '+esc(d.entity.type)+' \u00b7 Sources: '+d.entity.sources.length+'</div>';
    if(d.entity.sources.length){
      html+='<div style="font-size:.75rem;font-weight:600;margin-bottom:.25rem">Found in</div>';
      d.entity.sources.forEach(s=>{
        html+='<div style="font-size:.78rem;padding:.2rem 0;color:var(--accent2)">'+esc(s.split('/').pop())+'</div>';
      });
    }
    if(d.connections.length){
      html+='<div style="font-size:.75rem;font-weight:600;margin:.75rem 0 .25rem">Connected to</div>';
      d.connections.forEach(c=>{
        const label=c.value||c.id;
        const rel=c.relation==='contains'?'in document':'co-occurs';
        html+='<div class="src-item" style="padding:.4rem .6rem;cursor:pointer" onclick="'+(c.type==='document'?'':'showEntity(\''+esc(c.id)+'\')')+'">';
        html+='<span style="font-size:.8rem;font-weight:500">'+esc(label)+'</span>';
        html+=' <span style="font-size:.68rem;color:var(--text3)">'+esc(c.type)+' \u00b7 '+esc(rel)+'</span>';
        html+='</div>';
      });
    }
    body.innerHTML=html;
  }catch(e){body.innerHTML='<p>Error</p>'}
}

// Docs sidebar
async function loadDocs(el){
  el.innerHTML='<p style="color:var(--text3)">Loading...</p>';
  try{
    const r=await fetch('/summaries');const d=await r.json();
    const entries=Object.entries(d.summaries);
    if(!entries.length){el.innerHTML='<p style="color:var(--text3)">No summaries yet. Ingest documents first.</p>';return}
    el.innerHTML='';
    entries.forEach(([name,summary])=>{
      const div=document.createElement('div');div.className='src-item';
      div.innerHTML='<div class="src-name" style="margin-bottom:.25rem">'+esc(name)+'</div><div style="font-size:.8rem;color:var(--text2);line-height:1.5">'+esc(summary)+'</div>';
      el.appendChild(div);
    });
  }catch(e){el.innerHTML='<p>Error loading</p>'}
}

// Collections sidebar
async function loadCollections(el){
  el.innerHTML='<p style="color:var(--text3)">Loading...</p>';
  try{
    const r=await fetch('/collections');const d=await r.json();
    el.innerHTML='';
    d.collections.forEach(col=>{
      const isActive=col.name===d.active;
      // Collection card
      const div=document.createElement('div');div.className='col-item'+(isActive?' active':'');
      div.style.cssText='display:block;padding:.65rem .75rem';
      const docsDir=col.docs_dir||'./docs';
      div.innerHTML='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.25rem">'+
        '<div><span class="col-name">'+esc(col.name)+'</span> <span class="col-count">'+col.chunks+' chunks</span></div>'+
        '<div class="col-actions">'+(isActive?'<span style="font-size:.72rem;color:var(--accent2)">active</span>':
        '<button class="col-btn" onclick="switchCol(\''+esc(col.name)+'\');loadCollections(document.getElementById(\'sbBody\'))">Use</button>'+
        '<button class="col-btn del" onclick="deleteCol(\''+esc(col.name)+'\')">Delete</button>')+'</div></div>'+
        '<div style="font-size:.72rem;color:var(--text3)">Folder: '+esc(docsDir)+'</div>'+
        (isActive?'<div style="margin-top:.35rem"><button class="col-btn" onclick="reindexCol(\''+esc(col.name)+'\')">Re-index</button></div>':'');
      el.appendChild(div);

      // Upload zone under the active collection
      if(isActive){
        const upWrap=document.createElement('div');
        upWrap.style.cssText='margin:-.2rem 0 .75rem;padding:.6rem;border:1px solid var(--border);border-top:none;border-radius:0 0 var(--Rs) var(--Rs);background:var(--bg)';
        upWrap.innerHTML='<div style="font-size:.75rem;color:var(--text3);margin-bottom:.4rem">Upload files to <b>'+esc(col.name)+'</b></div>'+
          '<div class="upload-zone" id="upZone" style="padding:1rem"><h4 style="font-size:.85rem">Drop files here or click to browse</h4><p>PDF, DOCX, PPTX, XLSX, MD, TXT, HTML, CSV</p><input type="file" id="upFile" multiple accept=".pdf,.docx,.pptx,.xlsx,.xls,.md,.txt,.html,.csv"></div>'+
          '<div class="upload-progress" id="upProg"></div>';
        el.appendChild(upWrap);
        setTimeout(()=>{
          const zone=document.getElementById('upZone'),inp=document.getElementById('upFile');
          if(!zone||!inp)return;
          zone.onclick=()=>inp.click();
          inp.onchange=()=>{if(inp.files.length)uploadFiles(inp.files,col.name)};
          zone.ondragover=e=>{e.preventDefault();zone.classList.add('drag')};
          zone.ondragleave=()=>zone.classList.remove('drag');
          zone.ondrop=e=>{e.preventDefault();zone.classList.remove('drag');if(e.dataTransfer.files.length)uploadFiles(e.dataTransfer.files,col.name)};
        },0);

        // RSS feeds section
        const feedWrap=document.createElement('div');
        feedWrap.style.cssText='margin:-.2rem 0 .75rem;padding:.6rem;border:1px solid var(--border);border-top:none;border-radius:0 0 var(--Rs) var(--Rs);background:var(--bg)';
        feedWrap.innerHTML='<div style="font-size:.75rem;color:var(--text3);margin-bottom:.4rem">RSS feeds for <b>'+esc(col.name)+'</b></div>'+
          '<div id="feedList" style="margin-bottom:.4rem"></div>'+
          '<div style="display:flex;gap:.3rem"><input id="feedUrl" placeholder="RSS feed URL..." style="flex:1;padding:.35rem .5rem;border-radius:var(--Rs);border:1px solid var(--border);background:var(--bg2);color:var(--text);font-size:.78rem"><button class="col-btn" onclick="addFeed(\''+esc(col.name)+'\')">Add</button></div>'+
          '<div id="feedStatus" style="display:none;margin-top:.4rem;font-size:.75rem"></div>';
        el.appendChild(feedWrap);
        setTimeout(()=>loadFeeds(col.name),0);
      }
    });

    // Create new collection with folder browser
    const cr=document.createElement('div');cr.style.cssText='margin-top:1rem;padding-top:.75rem;border-top:1px solid var(--border)';
    cr.innerHTML='<div style="font-size:.8rem;font-weight:600;margin-bottom:.5rem">Create new collection</div>'+
      '<div class="col-create" style="margin-top:0"><input id="newColName" placeholder="Collection name..."></div>'+
      '<div class="col-create"><input id="newColDir" placeholder="Folder path (browse or type new)..." style="flex:1" ><button class="pb" onclick="openBrowser()">Browse</button></div>'+
      '<div style="font-size:.7rem;color:var(--text3);margin-top:.25rem;margin-bottom:.5rem">Browse an existing folder, or type a new path (e.g. <b>./work-policies</b>) — it will be created automatically. Uploads go into this folder.</div>'+
      '<button class="pb" id="createColBtn" onclick="createCol()" style="width:100%;padding:.45rem;text-align:center">Create Collection</button>'+
      '<div id="createColStatus" style="display:none;margin-top:.4rem;font-size:.78rem;text-align:center"></div>'+
      '<div id="folderBrowser" style="display:none;margin-top:.5rem;border:1px solid var(--border);border-radius:var(--Rs);max-height:250px;overflow-y:auto"></div>';
    el.appendChild(cr);
  }catch(e){el.innerHTML='<p>Error</p>'}
}

// Folder browser
async function openBrowser(startPath){
  const browser=document.getElementById('folderBrowser');
  browser.style.display='block';
  const path=startPath||'.';
  browser.innerHTML='<div style="padding:.5rem;color:var(--text3);font-size:.75rem">Loading...</div>';
  try{
    const r=await fetch('/browse?path='+encodeURIComponent(path));
    const d=await r.json();
    let html='<div style="padding:.4rem .6rem;font-size:.72rem;color:var(--text3);border-bottom:1px solid var(--border);word-break:break-all">'+esc(d.path)+'</div>';
    // Parent directory link
    if(d.parent&&d.parent!==d.path){
      html+='<div style="padding:.4rem .6rem;cursor:pointer;font-size:.82rem;border-bottom:1px solid var(--border)" onmouseover="this.style.background=\'var(--bg3)\'" onmouseout="this.style.background=\'none\'" onclick="openBrowser(\''+esc(d.parent)+'\')">&#x2191; ..</div>';
    }
    if(d.dirs&&d.dirs.length){
      d.dirs.forEach(dir=>{
        const fileInfo=dir.files>0?' <span style="color:var(--green);font-size:.72rem">'+dir.files+' docs</span>':'';
        html+='<div style="padding:.4rem .6rem;display:flex;justify-content:space-between;align-items:center;cursor:pointer;border-bottom:1px solid var(--border);font-size:.82rem" onmouseover="this.style.background=\'var(--bg3)\'" onmouseout="this.style.background=\'none\'">';
        html+='<span onclick="openBrowser(\''+esc(dir.path)+'\')">&#x1F4C1; '+esc(dir.name)+fileInfo+'</span>';
        html+='<button class="col-btn" onclick="event.stopPropagation();selectFolder(\''+esc(dir.path)+'\')">Select</button>';
        html+='</div>';
      });
    }else{
      html+='<div style="padding:.5rem .6rem;color:var(--text3);font-size:.78rem">No subfolders here</div>';
    }
    // Option to select current directory
    html+='<div style="padding:.5rem .6rem;border-top:1px solid var(--border)"><button class="pb" onclick="selectFolder(\''+esc(d.path)+'\')">Use this folder</button></div>';
    browser.innerHTML=html;
  }catch(e){browser.innerHTML='<div style="padding:.5rem;color:var(--red);font-size:.78rem">Error browsing</div>'}
}

function selectFolder(path){
  document.getElementById('newColDir').value=path;
  document.getElementById('folderBrowser').style.display='none';
}

async function createCol(){
  const name=document.getElementById('newColName').value.trim();
  if(!name){document.getElementById('newColName').focus();return}
  const dir=document.getElementById('newColDir').value.trim()||null;
  const btn=document.getElementById('createColBtn');
  const statusEl=document.getElementById('createColStatus');
  btn.disabled=true;btn.textContent='Creating...';
  statusEl.style.display='block';
  statusEl.innerHTML='<div style="font-size:.8rem;margin-bottom:.4rem;color:var(--accent2)">Setting up collection...</div>'+
    '<div id="createBar" style="background:var(--bg);border:1px solid var(--border);border-radius:4px;height:6px;margin-bottom:.4rem;overflow:hidden"><div id="createFill" style="height:100%;background:var(--accent2);width:0%;transition:width .3s"></div></div>'+
    '<div id="createLog" style="max-height:150px;overflow-y:auto;font-size:.75rem;color:var(--text3)"></div>';
  try{
    const r=await fetch('/collections/create',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,docs_dir:dir})});
    const d=await r.json();

    if(d.total===0){
      // Empty collection — no files to index
      statusEl.innerHTML='<div style="color:var(--green);font-size:.8rem">\u2713 Created (empty \u2014 upload files to get started)</div>';
      btn.disabled=false;btn.textContent='Create Collection';
      loadStatus();
      setTimeout(()=>loadCollections(document.getElementById('sbBody')),1500);
      return;
    }

    // Poll for progress
    const log=document.getElementById('createLog');
    const fill=document.getElementById('createFill');
    if(log)log.textContent='Found '+d.total+' files in '+esc(d.docs_dir||dir||'')+'...';
    let lastSeen=0;

    const poll=setInterval(async()=>{
      try{
        const pr=await fetch('/collections/reindex/status');
        const p=await pr.json();
        if(p.status==='idle')return;

        if(fill&&p.total>0)fill.style.width=Math.round(p.processed/p.total*100)+'%';

        if(p.recent&&log){
          p.recent.forEach(evt=>{
            if(evt.processed<=lastSeen)return;
            lastSeen=evt.processed;
            const icon=evt.event.startsWith('error')?'\u2717':'\u2713';
            const iconColor=evt.event.startsWith('error')?'var(--red)':'var(--green)';
            const detail=evt.event.startsWith('error')?esc(evt.event):evt.chunks+' chunks';
            log.innerHTML+='<div><span style="color:'+iconColor+'">'+icon+'</span> '+esc(evt.file)+' <span style="color:var(--text3)">'+detail+'</span> <span style="float:right">'+evt.processed+'/'+evt.total+'</span></div>';
            log.scrollTop=log.scrollHeight;
          });
        }

        if(p.status==='done'){
          clearInterval(poll);
          if(fill)fill.style.width='100%';
          if(p.error){
            log.innerHTML+='<div style="color:var(--red);font-weight:600;margin-top:.3rem">\u2717 Error: '+esc(p.error)+'</div>';
          }else{
            log.innerHTML+='<div style="color:var(--green);font-weight:600;margin-top:.3rem">\u2713 Done! '+p.total_chunks+' chunks indexed</div>';
          }
          btn.disabled=false;btn.textContent='Create Collection';
          loadStatus();
          setTimeout(()=>loadCollections(document.getElementById('sbBody')),2000);
        }
      }catch(e){}
    },800);
  }catch(e){
    statusEl.innerHTML='<div style="color:var(--red);font-size:.8rem">Error: '+esc(e.message)+'</div>';
    btn.disabled=false;btn.textContent='Create Collection';
  }
}
async function deleteCol(name){
  if(!confirm('Delete collection "'+name+'"? Source files will NOT be deleted.'))return;
  await fetch('/collections/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name})});
  loadStatus();loadCollections(document.getElementById('sbBody'));
}
async function reindexCol(name){
  const prog=document.getElementById('upProg');
  if(!prog)return;
  prog.innerHTML='<div style="font-size:.8rem;font-weight:600;margin-bottom:.4rem">Re-indexing '+esc(name)+'...</div>'+
    '<div id="reindexBar" style="background:var(--bg);border:1px solid var(--border);border-radius:4px;height:6px;margin-bottom:.5rem;overflow:hidden"><div id="reindexFill" style="height:100%;background:var(--accent2);width:0%;transition:width .3s"></div></div>'+
    '<div id="reindexLog" style="max-height:200px;overflow-y:auto"><div style="font-size:.75rem;color:var(--text3)">Starting...</div></div>';

  // Start the reindex (returns immediately)
  try{
    const r=await fetch('/collections/reindex',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name})});
    const d=await r.json();
    const log=document.getElementById('reindexLog');
    const dirInfo=d.docs_dir?' from '+esc(d.docs_dir):'';
    log.innerHTML='<div style="font-size:.75rem;color:var(--text3)">Found '+d.total+' files'+dirInfo+'</div>';
  }catch(e){
    prog.innerHTML='<div class="upload-file"><span class="uf-name">Re-index failed</span><span class="uf-status err">'+esc(e.message)+'</span></div>';
    return;
  }

  // Poll for progress
  let lastSeen=0;
  const poll=setInterval(async()=>{
    try{
      const r=await fetch('/collections/reindex/status');
      const d=await r.json();
      if(d.status==='idle')return;
      const fill=document.getElementById('reindexFill');
      const log=document.getElementById('reindexLog');
      if(!fill||!log){clearInterval(poll);return}

      // Update progress bar
      if(d.total>0){
        const pct=Math.round(d.processed/d.total*100);
        fill.style.width=pct+'%';
      }

      // Show new events
      if(d.recent){
        d.recent.forEach(evt=>{
          if(evt.processed<=lastSeen)return;
          lastSeen=evt.processed;
          const icon=evt.event==='added'||evt.event==='updated'?'\u2713':
            evt.event==='deleted'?'\u2212':
            evt.event.startsWith('error')?'\u2717':'';
          const iconColor=evt.event.startsWith('error')?'var(--red)':'var(--green)';
          const detail=evt.event.startsWith('error')?'<span style="color:var(--red)">'+esc(evt.event)+'</span>':evt.chunks+' chunks';
          log.innerHTML+='<div style="font-size:.75rem;padding:.1rem 0"><span style="color:'+iconColor+'">'+icon+'</span> '+esc(evt.file)+' <span style="color:var(--text3)">'+detail+'</span> <span style="color:var(--text3);float:right">'+evt.processed+'/'+evt.total+'</span></div>';
          log.scrollTop=log.scrollHeight;
        });
      }

      // Done
      if(d.status==='done'){
        clearInterval(poll);
        fill.style.width='100%';
        if(d.error){
          log.innerHTML+='<div style="font-size:.8rem;font-weight:600;color:var(--red);margin-top:.4rem">\u2717 Error: '+esc(d.error)+'</div>';
        }else{
          log.innerHTML+='<div style="font-size:.8rem;font-weight:600;color:var(--green);margin-top:.4rem">\u2713 Done! '+d.total_chunks+' chunks indexed</div>';
        }
        loadStatus();
      }
    }catch(e){}
  },800);
}

// Upload files into a specific collection
async function uploadFiles(files,colName){
  const prog=document.getElementById('upProg');
  for(const file of files){
    const id='uf-'+Date.now()+Math.random();
    const size=(file.size/1024).toFixed(0)+'KB';
    prog.innerHTML+='<div class="upload-file" id="'+id+'"><span class="uf-name">'+esc(file.name)+' <span style="color:var(--text3)">('+size+')</span></span><span class="uf-status prog">uploading...</span></div>';
    try{
      const fd=new FormData();fd.append('file',file);
      const url='/upload?collection='+encodeURIComponent(colName);
      const r=await fetch(url,{method:'POST',body:fd});const d=await r.json();
      const uel=document.getElementById(id);
      if(d.status==='ok'){
        const added=d.added||[];const chunks=d.total_chunks;
        let summary=d.summaries&&Object.values(d.summaries)[0]||'';
        uel.querySelector('.uf-status').className='uf-status ok';
        if(added.length===0){
          uel.querySelector('.uf-status').textContent='already indexed';
        }else{
          uel.querySelector('.uf-status').textContent=chunks+' chunks';
        }
        if(summary){uel.innerHTML+='<div style="font-size:.72rem;color:var(--text3);margin-top:.25rem;padding:0 .75rem .5rem">'+esc(summary.slice(0,120))+'</div>'}
      }else{
        uel.querySelector('.uf-status').className='uf-status err';
        uel.querySelector('.uf-status').textContent=d.message||'error';
      }
    }catch(e){
      const uel=document.getElementById(id);
      if(uel){uel.querySelector('.uf-status').className='uf-status err';uel.querySelector('.uf-status').textContent='failed'}
    }
  }
  loadStatus();
  // Refresh chunk counts
  setTimeout(()=>{if(sbMode==='collections')loadCollections(document.getElementById('sbBody'))},500);
}

// RSS Feeds
async function loadFeeds(colName){
  const list=document.getElementById('feedList');
  if(!list)return;
  try{
    const r=await fetch('/feeds?collection='+encodeURIComponent(colName));
    const d=await r.json();
    if(!d.feeds||!d.feeds.length){
      list.innerHTML='<div style="font-size:.72rem;color:var(--text3)">No feeds added yet</div>';
      return;
    }
    list.innerHTML='';
    d.feeds.forEach(f=>{
      const lastFetch=f.last_fetched?'Last fetched: '+new Date(f.last_fetched).toLocaleDateString():'Never fetched';
      list.innerHTML+='<div style="display:flex;justify-content:space-between;align-items:center;padding:.3rem 0;border-bottom:1px solid var(--border);font-size:.75rem">'+
        '<div style="flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="'+esc(f.url)+'">'+esc(f.url)+'</div>'+
        '<div style="display:flex;gap:.2rem;margin-left:.3rem;flex-shrink:0">'+
        '<span style="color:var(--text3);font-size:.68rem">'+esc(lastFetch)+'</span>'+
        '<button class="col-btn del" onclick="removeFeed(\''+esc(colName)+'\',\''+esc(f.url)+'\')">x</button>'+
        '</div></div>';
    });
    // Add refresh button
    list.innerHTML+='<div style="margin-top:.3rem"><button class="col-btn" onclick="fetchFeeds(\''+esc(colName)+'\')">Refresh all feeds</button></div>';
  }catch(e){list.innerHTML='<div style="color:var(--red);font-size:.72rem">Error loading feeds</div>'}
}

async function addFeed(colName){
  const inp=document.getElementById('feedUrl');
  const url=inp.value.trim();if(!url)return;
  const status=document.getElementById('feedStatus');
  status.style.display='block';status.style.color='var(--accent2)';status.textContent='Adding feed...';
  try{
    await fetch('/feeds/add',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url,collection:colName})});
    inp.value='';
    status.style.color='var(--green)';status.textContent='\u2713 Feed added. Click "Refresh all feeds" to fetch articles.';
    loadFeeds(colName);
  }catch(e){status.style.color='var(--red)';status.textContent='Error: '+e.message}
}

async function removeFeed(colName,url){
  await fetch('/feeds/remove',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url,collection:colName})});
  loadFeeds(colName);
}

async function fetchFeeds(colName){
  const status=document.getElementById('feedStatus');
  status.style.display='block';status.style.color='var(--accent2)';status.textContent='Fetching feeds...';
  try{
    const r=await fetch('/feeds/fetch?collection='+encodeURIComponent(colName),{method:'POST'});
    const d=await r.json();
    let msg='';
    d.feeds.forEach(f=>{
      const feedName=f.url.replace(/https?:\/\//,'').split('/')[0];
      if(f.error){msg+=feedName+': error ('+esc(f.error)+')\\n'}
      else{msg+=feedName+': '+f.new_count+' new / '+f.total+' total articles\\n'}
    });
    if(d.indexing){
      status.style.color='var(--accent2)';
      status.innerHTML=esc(msg).replace(/\\n/g,'<br>')+'<br>Indexing new articles...';
      // Poll for ingest progress
      const poll=setInterval(async()=>{
        try{
          const pr=await fetch('/collections/reindex/status');
          const p=await pr.json();
          if(p.status==='done'){
            clearInterval(poll);
            status.style.color='var(--green)';
            status.innerHTML=esc(msg).replace(/\\n/g,'<br>')+'<br>\u2713 '+p.total_chunks+' chunks indexed';
            loadStatus();loadFeeds(colName);
          }
        }catch(e){}
      },1000);
    }else{
      status.style.color='var(--green)';
      status.innerHTML=esc(msg).replace(/\\n/g,'<br>')+'\u2713 No new articles';
    }
  }catch(e){status.style.color='var(--red)';status.textContent='Error: '+e.message}
}

// Settings
let modelsData={};
async function loadSettings(el){
  el.innerHTML='<p style="color:var(--text3)">Loading...</p>';
  try{
    const[sr,mr,cr]=await Promise.all([fetch('/settings'),fetch('/models'),fetch('/cache/stats')]);
    const d=await sr.json();modelsData=await mr.json();const cs=await cr.json();
    const f=d.features;const llm=d.llm;const ret=d.retrieval;const keys=d.api_keys||{};
    const inp='display:block;width:100%;padding:.35rem .5rem;margin-top:.15rem;border-radius:var(--Rs);border:1px solid var(--border);background:var(--bg);color:var(--text);font-size:.8rem';
    let html='';

    // Features toggles
    html+='<div style="font-size:.85rem;font-weight:600;margin-bottom:.5rem">Features</div>';
    const toggles=[
      {key:'agentic_queries',label:'Agentic queries',desc:'LLM plans multi-step searches for complex questions'},
      {key:'knowledge_graph',label:'Knowledge graph',desc:'Extract entities and relationships from documents'},
      {key:'suggestions',label:'Follow-up suggestions',desc:'Suggest related questions after each answer'},
      {key:'query_cache',label:'Query cache',desc:'Cache answers for instant repeat queries'},
      {key:'auto_ingest',label:'Auto-ingest',desc:'Automatically index new documents'},
      {key:'watch_mode',label:'Watch mode',desc:'Monitor docs folder for changes'},
    ];
    toggles.forEach(t=>{
      const on=f[t.key];
      const bg=on?'var(--accent)':'var(--bg3)';
      const dot=on?'translateX(16px)':'translateX(0)';
      const tag=on?'<span style="color:var(--green);font-size:.68rem;margin-left:.3rem">ON</span>':'<span style="color:var(--text3);font-size:.68rem;margin-left:.3rem">OFF</span>';
      html+='<div style="display:flex;align-items:center;gap:.6rem;padding:.5rem 0;border-bottom:1px solid var(--border)">'+
        '<div onclick="toggleFeature(\''+t.key+'\','+(!on)+');loadSettings(document.getElementById(\'sbBody\'))" style="position:relative;width:40px;height:22px;flex-shrink:0;cursor:pointer;background:'+bg+';border-radius:22px;transition:.3s">'+
        '<div style="position:absolute;top:2px;left:2px;width:18px;height:18px;background:#fff;border-radius:50%;transition:.3s;transform:'+dot+'"></div></div>'+
        '<div style="flex:1"><div style="font-size:.8rem;font-weight:500">'+t.label+tag+'</div>'+
        '<div style="font-size:.7rem;color:var(--text3)">'+t.desc+'</div></div></div>';
    });

    // LLM settings
    html+='<div style="font-size:.85rem;font-weight:600;margin:1rem 0 .5rem">LLM Model</div>';
    html+='<div style="margin-bottom:.4rem"><label style="font-size:.75rem;color:var(--text2)">Provider</label>'+
      '<select id="setLlmProvider" onchange="updateModelDropdown()" style="'+inp+'">'+
      '<option value="local"'+(llm.provider==='local'?' selected':'')+'>Local (Ollama)</option>'+
      '<option value="openai"'+(llm.provider==='openai'?' selected':'')+'>OpenAI</option>'+
      '<option value="anthropic"'+(llm.provider==='anthropic'?' selected':'')+'>Anthropic</option></select></div>';
    html+='<div style="margin-bottom:.4rem"><label style="font-size:.75rem;color:var(--text2)">Model</label>'+
      '<select id="setLlmModel" style="'+inp+'"></select></div>';
    html+='<div id="modelInfo" style="font-size:.7rem;color:var(--text3);margin-bottom:.4rem"></div>';
    html+='<div style="margin-bottom:.4rem"><label style="font-size:.75rem;color:var(--text2)">Temperature</label>'+
      '<input id="setLlmTemp" type="number" step="0.1" min="0" max="2" value="'+llm.temperature+'" style="'+inp+'"></div>';

    // Retrieval
    html+='<div style="font-size:.85rem;font-weight:600;margin:1rem 0 .5rem">Retrieval</div>';
    html+='<div style="margin-bottom:.4rem"><label style="font-size:.75rem;color:var(--text2)">Top K (chunks per query)</label>'+
      '<input id="setTopK" type="number" min="1" max="30" value="'+ret.top_k+'" style="'+inp+'"></div>';

    // API Keys
    html+='<div style="font-size:.85rem;font-weight:600;margin:1rem 0 .5rem">API Keys</div>';
    html+='<div style="font-size:.7rem;color:var(--text3);margin-bottom:.4rem">Keys are saved to .env and never shown in full</div>';
    [['openai','OpenAI','sk-...'],['anthropic','Anthropic','sk-ant-...'],['cohere','Cohere','...']].forEach(([k,label,ph])=>{
      const hasKey=keys[k]&&keys[k]!=='';
      const badge=hasKey?'<span style="color:var(--green);font-size:.68rem;margin-left:.3rem">\u2713 set</span>':'<span style="color:var(--text3);font-size:.68rem;margin-left:.3rem">not set</span>';
      html+='<div style="margin-bottom:.4rem"><label style="font-size:.75rem;color:var(--text2)">'+label+badge+'</label>'+
        '<input id="apiKey_'+k+'" type="password" placeholder="'+ph+'" value="'+(keys[k]||'')+'" style="'+inp+'"></div>';
    });
    html+='<button class="col-btn" onclick="saveApiKeys()" style="margin-top:.3rem">Save API Keys</button>';
    html+='<div id="apiKeyStatus" style="display:none;font-size:.75rem;margin-top:.3rem"></div>';

    // Save + cache
    html+='<button class="pb" onclick="saveSettings()" style="width:100%;padding:.45rem;text-align:center;margin-top:1rem">Save Settings</button>';
    html+='<div id="settingsStatus" style="display:none;margin-top:.4rem;font-size:.78rem;text-align:center"></div>';
    html+='<div style="margin-top:1rem;padding-top:.75rem;border-top:1px solid var(--border)">';
    html+='<div style="font-size:.75rem;color:var(--text3)">Cache: '+cs.cached+' cached, '+cs.expired+' expired</div>';
    html+='<button class="col-btn" onclick="clearCache()" style="margin-top:.3rem">Clear cache</button></div>';

    el.innerHTML=html;

    // Populate model dropdown after render
    setTimeout(()=>updateModelDropdown(llm.model),0);
  }catch(e){el.innerHTML='<p style="color:var(--red)">Error loading settings</p>'}
}

function updateModelDropdown(currentModel){
  const prov=document.getElementById('setLlmProvider').value;
  const sel=document.getElementById('setLlmModel');
  const info=document.getElementById('modelInfo');
  if(!sel)return;
  sel.innerHTML='';

  if(prov==='local'){
    const installed=modelsData.local?.installed||[];
    const available=modelsData.local?.available||[];
    // Add installed models
    installed.forEach(m=>{
      const opt=document.createElement('option');opt.value=m;opt.textContent=m+' (installed)';
      if(m===currentModel)opt.selected=true;sel.appendChild(opt);
    });
    // Add available but not installed
    available.forEach(m=>{
      if(!installed.includes(m.name)){
        const opt=document.createElement('option');opt.value=m.name;
        opt.textContent=m.name+' \u2014 '+m.size+' \u2014 '+m.quality;
        if(m.name===currentModel)opt.selected=true;sel.appendChild(opt);
      }
    });
    info.innerHTML='<span style="color:var(--text3)">'+installed.length+' models installed.</span> '+
      'Select a new model and save \u2014 it will be downloaded automatically if needed.';
  }else if(prov==='openai'){
    (modelsData.openai||[]).forEach(m=>{
      const opt=document.createElement('option');opt.value=m;opt.textContent=m;
      if(m===currentModel)opt.selected=true;sel.appendChild(opt);
    });
    info.textContent='Requires OpenAI API key.';
  }else if(prov==='anthropic'){
    (modelsData.anthropic||[]).forEach(m=>{
      const opt=document.createElement('option');opt.value=m;opt.textContent=m;
      if(m===currentModel)opt.selected=true;sel.appendChild(opt);
    });
    info.textContent='Requires Anthropic API key.';
  }
}

async function toggleFeature(key,value){
  const body={features:{}};body.features[key]=value;
  await fetch('/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
}

async function saveSettings(){
  const status=document.getElementById('settingsStatus');
  const model=document.getElementById('setLlmModel').value;
  const provider=document.getElementById('setLlmProvider').value;
  const body={
    llm:{provider,model,temperature:parseFloat(document.getElementById('setLlmTemp').value)||0.1},
    retrieval:{top_k:parseInt(document.getElementById('setTopK').value)||8},
  };
  status.style.display='block';status.style.color='var(--accent2)';status.textContent='Saving...';
  try{
    await fetch('/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    // If local model not installed, offer to pull
    if(provider==='local'){
      const installed=modelsData.local?.installed||[];
      if(!installed.includes(model)){
        status.style.color='var(--accent2)';
        status.textContent='Downloading model '+model+'... (this may take a few minutes)';
        await fetch('/models/pull',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({model})});
        status.style.color='var(--green)';
        status.textContent='\u2713 Settings saved. Model '+model+' is downloading. Restart server when done.';
        return;
      }
    }
    status.style.color='var(--green)';status.textContent='\u2713 Settings saved. Restart server for model changes to take effect.';
  }catch(e){status.style.color='var(--red)';status.textContent='Error: '+e.message}
}

async function saveApiKeys(){
  const status=document.getElementById('apiKeyStatus');
  const body={};
  ['openai','anthropic','cohere'].forEach(k=>{
    const v=document.getElementById('apiKey_'+k).value;
    if(v&&!v.startsWith('****'))body[k]=v;
  });
  if(!Object.keys(body).length){status.style.display='block';status.style.color='var(--text3)';status.textContent='No new keys to save.';return}
  status.style.display='block';status.style.color='var(--accent2)';status.textContent='Saving...';
  try{
    await fetch('/settings/api-keys',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    status.style.color='var(--green)';status.textContent='\u2713 API keys saved to .env';
    setTimeout(()=>loadSettings(document.getElementById('sbBody')),1500);
  }catch(e){status.style.color='var(--red)';status.textContent='Error: '+e.message}
}

async function clearCache(){
  await fetch('/cache/clear',{method:'POST'});
  loadSettings(document.getElementById('sbBody'));
}

// Send message
async function send(){
  const inp=document.getElementById('qIn');const q=inp.value.trim();if(!q||sending)return;
  const w=document.getElementById('welcome');if(w)w.remove();
  sending=true;document.getElementById('sendBtn').disabled=true;
  inp.value='';inp.style.height='auto';
  addMsg('user',q);
  const tid=addTyping();
  try{
    const r=await fetch('/query',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:q,top_k:5,use_history:true})});
    const d=await r.json();rmTyping(tid);
    lastSources=d.sources||[];lastSugs=d.suggestions||[];
    addMsg('assistant',d.answer,d.sources,d.suggestions,d.latency_ms,d.meta);
    if(sbMode==='sources')renderSources(document.getElementById('sbBody'));
  }catch(e){rmTyping(tid);addMsg('assistant','Error: '+e.message)}
  finally{sending=false;document.getElementById('sendBtn').disabled=false;inp.focus()}
}

function addMsg(role,content,sources,sugs,lat,meta){
  const a=document.getElementById('chatArea');const d=document.createElement('div');d.className='msg '+role;
  let h='<div class="av">'+(role==='user'?'You':'AI')+'</div><div class="mb"><div class="bubble">';
  h+=role==='assistant'?renderMd(content):esc(content);
  h+='</div>';
  if(sources&&sources.length){
    h+='<div class="src-pills">';
    sources.forEach(s=>{
      const rel=Math.round((s.relevance||0)*100);const cls=rel>=70?'hi':'';
      const name=(s.file_name||s.file||'').split('/').pop();
      if(s.file_url){h+='<a class="sp '+cls+'" href="'+esc(s.file_url)+'" target="_blank" title="Open '+esc(name)+'">'+esc(name)+' '+rel+'%</a>'}
      else{h+='<span class="sp '+cls+'" onclick="openSB(\'sources\')">'+esc(name)+' '+rel+'%</span>'}
    });
    h+='</div>';
  }
  if(sugs&&sugs.length){h+='<div class="suggs">';sugs.forEach(s=>{h+='<span class="sg" onclick="askSug(this)">'+esc(s)+'</span>'});h+='</div>'}
  if(lat||meta){
    const m=meta||{};
    let metaParts=[];
    if(lat)metaParts.push((lat/1000).toFixed(1)+'s');
    if(sources)metaParts.push(sources.length+' sources');
    if(m.strategy==='agentic')metaParts.push('\ud83e\udde0 agent');
    else if(m.strategy==='broad')metaParts.push('\ud83d\udcca broad scan');
    else if(m.strategy==='specific')metaParts.push('\ud83c\udfaf targeted');
    if(m.used_cache)metaParts.push('\u26a1 cached');
    if(m.used_graph)metaParts.push('\ud83d\udd17 graph');
    if(m.cost_usd>0)metaParts.push('$'+m.cost_usd.toFixed(4));
    if(m.total_session_cost>0)metaParts.push('session: $'+m.total_session_cost.toFixed(4));
    if(m.model)metaParts.push(m.model);
    h+='<div class="msg-meta">'+metaParts.join(' \u00b7 ')+'</div>';
  }
  h+='</div>';d.innerHTML=h;a.appendChild(d);a.scrollTop=a.scrollHeight;
}
function addTyping(){const a=document.getElementById('chatArea');const d=document.createElement('div');const id='t-'+Date.now();d.id=id;d.className='msg assistant';d.innerHTML='<div class="av">AI</div><div class="mb"><div class="bubble"><div class="typing"><span></span><span></span><span></span></div></div></div>';a.appendChild(d);a.scrollTop=a.scrollHeight;return id}
function rmTyping(id){const e=document.getElementById(id);if(e)e.remove()}
function askSug(el){document.getElementById('qIn').value=el.textContent;send()}

// Export
async function exportChat(){try{const r=await fetch('/export');const d=await r.json();const b=new Blob([d.markdown],{type:'text/markdown'});const u=URL.createObjectURL(b);const a=document.createElement('a');a.href=u;a.download='rag-session.md';a.click();URL.revokeObjectURL(u)}catch(e){alert('Export failed: '+e.message)}}

// Clear
async function clearHist(){await fetch('/history/clear',{method:'POST'});document.getElementById('chatArea').innerHTML='';lastSources=[];loadWelcome()}

// Welcome
async function loadWelcome(){
  let el=document.getElementById('wcCards');
  if(!el){
    const a=document.getElementById('chatArea');
    a.innerHTML='<div class="welcome" id="welcome"><h2>Chat with your documents</h2><p>Ask anything about your indexed files. Answers cite their sources.</p><div class="wc-grid" id="wcCards"></div></div>';
    el=document.getElementById('wcCards');
  }
  const samples=[
    {t:'Summarize',d:'Get an overview of all documents',q:'Give me a summary of all the documents you have'},
    {t:'Find details',d:'Search for specific information',q:'What are the key dates and confirmation numbers?'},
    {t:'Compare',d:'Compare across documents',q:'What are all the costs and payments mentioned?'},
    {t:'Timeline',d:'Chronological order',q:'What is the chronological timeline of events?'},
  ];
  el.innerHTML='';samples.forEach(s=>{
    el.innerHTML+='<div class="wc" onclick="askWc(\''+s.q.replace(/'/g,"\\'") +'\')"><b>'+s.t+'</b><span>'+s.d+'</span></div>';
  });
}
function askWc(q){document.getElementById('qIn').value=q;send()}

// Markdown
let chartCounter=0;
function renderMd(t){if(!t)return'';let h=t;
  h=h.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');

  // Mermaid blocks: ```mermaid ... ```
  h=h.replace(/```mermaid\n([\s\S]*?)```/g,(_,code)=>{
    const id='mermaid-'+Date.now()+Math.random().toString(36).slice(2,6);
    // Sanitize mermaid code: fix common LLM issues
    let clean=code.trim();
    // Unescape HTML entities that we escaped above
    clean=clean.replace(/&amp;/g,'&').replace(/&lt;/g,'<').replace(/&gt;/g,'>');
    // Wrap node labels containing special chars in quotes
    // Match: A[label with (parens) or special chars] and fix to A["label with (parens)"]
    clean=clean.replace(/(\w+)\[([^\]"]*[()\/&,#:;].*?)\]/g,(_,node,label)=>node+'["'+label.replace(/"/g,"'")+'"]');
    // Same for (round nodes)
    clean=clean.replace(/(\w+)\(([^)"]*[[\]\/&,#:;].*?)\)/g,(_,node,label)=>node+'("'+label.replace(/"/g,"'")+'")');
    // Remove any ** bold markers the LLM might include
    clean=clean.replace(/\*\*/g,'');
    setTimeout(()=>{
      const el=document.getElementById(id);
      if(!el)return;
      try{
        mermaid.render(id+'-svg',clean).then(({svg})=>{
          el.innerHTML=svg;
        }).catch(()=>{
          // Fallback: show as styled text instead of error
          el.innerHTML='<pre style="background:var(--bg);border:1px solid var(--border);border-radius:var(--Rs);padding:.75rem;font-size:.8rem;color:var(--text2);white-space:pre-wrap">'+esc(clean)+'</pre>';
        });
      }catch(e){
        el.innerHTML='<pre style="background:var(--bg);border:1px solid var(--border);border-radius:var(--Rs);padding:.75rem;font-size:.8rem;color:var(--text2);white-space:pre-wrap">'+esc(clean)+'</pre>';
      }
    },100);
    return '<div id="'+id+'" style="margin:.5rem 0;text-align:center"></div>';
  });

  // Chart blocks: ```chart {...json} ```
  h=h.replace(/```chart\n([\s\S]*?)```/g,(_,json)=>{
    const cid='chart-'+(chartCounter++);
    setTimeout(()=>{try{
      const cfg=JSON.parse(json.trim().replace(/&amp;/g,'&').replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/&quot;/g,'"'));
      const canvas=document.getElementById(cid);
      if(canvas)new Chart(canvas,cfg);
    }catch(e){console.log('Chart error:',e)}},100);
    return '<div style="max-width:500px;margin:.5rem 0"><canvas id="'+cid+'" height="250"></canvas></div>';
  });

  // Code blocks
  h=h.replace(/```(\w*)\n([\s\S]*?)```/g,(_,l,c)=>'<pre><code>'+c.trim()+'</code></pre>');
  h=h.replace(/`([^`]+)`/g,'<code>$1</code>');

  // Markdown tables — detect and convert pipe-delimited tables
  h=h.replace(/((?:^[|].+[|]$\n?){2,})/gm,(tableBlock)=>{
    const rows=tableBlock.trim().split('\n').filter(r=>r.trim());
    if(rows.length<2)return tableBlock;
    // Check if second row is separator (|---|---|)
    const isSep=r=>/^[|\s:-]+$/.test(r);
    let html='<table>';
    let inHead=true;
    rows.forEach((row,i)=>{
      if(isSep(row)){inHead=false;return}
      const cells=row.split('|').filter((_,j,a)=>j>0&&j<a.length-1).map(c=>c.trim());
      if(inHead&&i===0){
        html+='<thead><tr>'+cells.map(c=>'<th>'+c+'</th>').join('')+'</tr></thead><tbody>';
      }else{
        html+='<tr>'+cells.map(c=>'<td>'+c+'</td>').join('')+'</tr>';
      }
    });
    html+='</tbody></table>';
    return html;
  });

  // Headers
  h=h.replace(/^#### (.+)$/gm,'<h4>$1</h4>');h=h.replace(/^### (.+)$/gm,'<h3>$1</h3>');
  h=h.replace(/^## (.+)$/gm,'<h2>$1</h2>');h=h.replace(/^# (.+)$/gm,'<h1>$1</h1>');
  // Bold + italic
  h=h.replace(/\*\*\*(.+?)\*\*\*/g,'<strong><em>$1</em></strong>');
  h=h.replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>');h=h.replace(/\*(.+?)\*/g,'<em>$1</em>');
  h=h.replace(/__(.+?)__/g,'<strong>$1</strong>');h=h.replace(/_(.+?)_/g,'<em>$1</em>');
  // Links
  h=h.replace(/\[([^\]]+)\]\((https?:\/\/[^\)]+)\)/g,'<a href="$2" target="_blank" rel="noopener">$1</a>');
  h=h.replace(/(?<!["=])(https?:\/\/[^\s<]+)/g,'<a href="$1" target="_blank" rel="noopener">$1</a>');
  // Other
  h=h.replace(/^&gt; (.+)$/gm,'<blockquote>$1</blockquote>');h=h.replace(/^---$/gm,'<hr>');
  // Lists: match both top-level and indented items (- item, * item,  - sub-item)
  h=h.replace(/^[ \t]*[\*\-] (.+)$/gm,'<li>$1</li>');
  h=h.replace(/((?:<li>.*<\/li>\n?)+)/g,'<ul>$1</ul>');
  h=h.replace(/^[ \t]*\d+\. (.+)$/gm,'<li>$1</li>');
  h=h.replace(/((?:<li>.*<\/li>\n?)+)/g,m=>/^<ul>/.test(m)?m:'<ol>'+m+'</ol>');
  // Paragraphs
  h=h.split(/\n\n+/).map(b=>{b=b.trim();if(!b)return'';if(/^<(h[1-6]|ul|ol|li|pre|blockquote|hr|table|div|canvas)/.test(b))return b;return'<p>'+b.replace(/\n/g,'<br>')+'</p>'}).join('\n');

  // Auto-detect tables with chartable numeric data (costs/amounts, not dates/IDs)
  h=h.replace(/(<table>[\s\S]*?<\/table>)/g,(table)=>{
    // Must have dollar/currency amounts — not just any numbers
    const moneyMatches=table.match(/[\$\£\€]\s*[\d,.]+/g);
    // Or at least a column header suggesting numbers (Cost, Amount, Price, Total, Budget)
    const numHeaders=/(?:cost|amount|price|total|budget|expense|fee|rate|salary|revenue)/i.test(table);
    if((moneyMatches&&moneyMatches.length>=2)||numHeaders){
      const cid='auto-chart-'+(chartCounter++);
      return table+'<div style="margin:.4rem 0"><button class="col-btn" onclick="chartFromTable(this.parentElement.previousElementSibling,\''+cid+'\')" style="font-size:.72rem">\ud83d\udcca Visualize</button><canvas id="'+cid+'" style="display:none;max-width:500px;margin-top:.4rem" height="250"></canvas></div>';
    }
    return table;
  });

  return h;
}

// Auto-generate chart from table data
function chartFromTable(tableEl,canvasId){
  if(!tableEl||!tableEl.querySelector)return;
  const canvas=document.getElementById(canvasId);
  if(!canvas)return;

  const headers=[];const rows=[];
  tableEl.querySelectorAll('thead th').forEach(th=>headers.push(th.textContent.trim()));
  tableEl.querySelectorAll('tbody tr').forEach(tr=>{
    const cells=[];tr.querySelectorAll('td').forEach(td=>cells.push(td.textContent.trim()));
    if(cells.length)rows.push(cells);
  });
  if(!headers.length||!rows.length)return;

  // Filter out rows that are section headers or totals (no numeric data or summary rows)
  const dataRows=rows.filter(r=>{
    const nums=r.slice(1).filter(c=>/[\d.]/.test(c.replace(/[\$\£\€,]/g,'')));
    return nums.length>0;
  });
  if(!dataRows.length)return;

  const labels=dataRows.map(r=>r[0]||'');
  const parseNum=s=>parseFloat((s||'').replace(/[\$\£\€,\s]/g,''))||0;

  // Find ALL numeric columns
  const numCols=[];
  for(let c=1;c<headers.length;c++){
    const numCount=dataRows.filter(r=>parseNum(r[c])!==0).length;
    if(numCount>=dataRows.length*0.3)numCols.push(c);
  }
  if(!numCols.length)return;

  const colors=['#3b82f6','#10b981','#f59e0b','#ef4444','#8b5cf6','#ec4899','#06b6d4','#84cc16','#f97316','#6366f1'];
  const isComparison=numCols.length>=2;
  const isFewItems=dataRows.length<=6&&!isComparison;

  // Build datasets
  const datasets=[];
  if(isComparison){
    // Multi-column: grouped bar chart (e.g., Jeff/Drew vs Lori/Pam)
    numCols.forEach((col,i)=>{
      datasets.push({
        label:headers[col]||'Series '+(i+1),
        data:dataRows.map(r=>parseNum(r[col])),
        backgroundColor:colors[i%colors.length],
        borderColor:colors[i%colors.length],
        borderWidth:1,
      });
    });
  }else{
    // Single numeric column
    const col=numCols[0];
    datasets.push({
      label:headers[col]||'Value',
      data:dataRows.map(r=>parseNum(r[col])),
      backgroundColor:isFewItems?colors.slice(0,dataRows.length):colors[0],
      borderColor:isFewItems?'rgba(0,0,0,0.2)':colors[0],
      borderWidth:1,
    });
  }

  const chartType=isFewItems?'doughnut':'bar';

  canvas.style.display='block';
  canvas.height=isComparison?Math.max(250,dataRows.length*20+100):220;

  // Destroy existing chart if re-clicking
  const existing=Chart.getChart(canvas);
  if(existing)existing.destroy();

  new Chart(canvas,{
    type:chartType,
    data:{labels,datasets},
    options:{
      responsive:true,
      indexAxis:isComparison&&dataRows.length>5?'y':'x',
      plugins:{
        legend:{display:isComparison||isFewItems,position:isFewItems?'right':'top',labels:{color:'#94a3b8',font:{size:11}}},
        title:{display:false},
        tooltip:{callbacks:{label:ctx=>{
          let val=ctx.parsed.y??ctx.parsed;
          if(typeof val==='object')val=val.y||val.x||0;
          return ctx.dataset.label+': $'+val.toLocaleString();
        }}},
      },
      scales:chartType!=='doughnut'?{
        y:{beginAtZero:true,ticks:{color:'#94a3b8',callback:v=>'$'+v.toLocaleString()}},
        x:{ticks:{color:'#94a3b8',maxRotation:45}},
      }:undefined,
    }
  });
}

function esc(t){const d=document.createElement('div');d.textContent=t;return d.innerHTML}

// Init
mermaid.initialize({theme:'dark',startOnLoad:false});
loadStatus();loadWelcome();
(async()=>{try{const r=await fetch('/history');const d=await r.json();if(d.messages&&d.messages.length){const w=document.getElementById('welcome');if(w)w.remove();d.messages.forEach(m=>addMsg(m.role,m.content))}}catch(e){}})();
</script>
</body>
</html>"""
