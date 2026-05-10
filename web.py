import threading
import json
from flask import Flask, request, send_file, jsonify, render_template_string
from pathlib import Path
from main import run
from rag.pdf_parser import PDFParser
from rag.text_parser import parse_text
from rag.retriever import load_index_from_chapters, index_stats
from rag.chat import ask
from graph.merger import merge_graphs
from output.visualizer import render as render_html
import config

app = Flask(__name__)
UPLOAD_DIR = Path("data/pdfs")
OUTPUT_DIR = Path("data/output")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# job_id -> {"name", "size", "ext", "status": pending|processing|done|failed, "error"}
jobs: dict = {}
jobs_lock = threading.Lock()


def _process(job_id: str, dest: Path):
    with jobs_lock:
        jobs[job_id]["status"] = "processing"
    try:
        suffix = dest.suffix.lower()
        if suffix == ".pdf":
            parsed = PDFParser(str(dest)).parse()
        else:
            parsed = parse_text(str(dest))
        chapters = parsed["chapters"]
        chapter_list = [{"id": c["chapter_id"], "title": c["title"],
                         "page_start": c["page_start"], "char_count": c["char_count"]}
                        for c in chapters]
        run(str(dest), str(OUTPUT_DIR))
        load_index_from_chapters(chapters, source=Path(dest).stem)
        with jobs_lock:
            jobs[job_id]["status"] = "done"
            jobs[job_id]["chapters"] = chapter_list
    except Exception as e:
        with jobs_lock:
            jobs[job_id]["status"] = "failed"
            jobs[job_id]["error"] = str(e)


INDEX = r"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>知识图谱生成器</title>
<style>
*{box-sizing:border-box}
body{font-family:sans-serif;max-width:760px;margin:48px auto;padding:0 16px;background:#f5f6fa}
h2{margin-bottom:24px}
#drop{border:2px dashed #aab;border-radius:12px;padding:48px;text-align:center;
  background:#fff;cursor:pointer;transition:background .2s;color:#667}
#drop.over{background:#eef2ff;border-color:#6366f1}
#drop input{display:none}
table{width:100%;border-collapse:collapse;margin-top:24px;background:#fff;border-radius:10px;overflow:hidden;box-shadow:0 1px 4px #0001}
th,td{padding:10px 14px;text-align:left;font-size:14px}
th{background:#f0f1f5;font-weight:600}
tr+tr td{border-top:1px solid #eee}
.badge{display:inline-block;padding:2px 10px;border-radius:99px;font-size:12px;font-weight:600}
.pending{background:#fef9c3;color:#854d0e}
.processing{background:#dbeafe;color:#1e40af}
.done{background:#dcfce7;color:#166534}
.failed{background:#fee2e2;color:#991b1b}
a{color:#6366f1;text-decoration:none}a:hover{text-decoration:underline}
#merge-box{margin-top:32px;background:#fff;border-radius:10px;padding:20px;box-shadow:0 1px 4px #0001}
#merge-box h3{margin:0 0 12px;font-size:15px}
#merge-stems{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:12px;min-height:32px}
.stem-chip{padding:4px 12px;border-radius:99px;background:#eef2ff;color:#4338ca;font-size:13px;cursor:pointer;border:1px solid #c7d2fe}
.stem-chip.selected{background:#6366f1;color:#fff;border-color:#6366f1}
#merge-btn{padding:8px 20px;background:#6366f1;color:#fff;border:none;border-radius:8px;font-size:14px;cursor:pointer}
#merge-btn:disabled{opacity:.5;cursor:not-allowed}
#merge-result{margin-top:16px;font-size:13px}
.stat-row{display:flex;gap:24px;margin-bottom:12px;flex-wrap:wrap}
.stat{background:#f0f1f5;border-radius:8px;padding:8px 16px;text-align:center}
.stat .v{font-size:20px;font-weight:700;color:#6366f1}
.stat .l{font-size:11px;color:#64748b;margin-top:2px}
.dec-table{width:100%;border-collapse:collapse;margin-top:8px;font-size:12px}
.dec-table th{background:#f0f1f5;padding:6px 8px;text-align:left}
.dec-table td{padding:6px 8px;border-top:1px solid #eee}
.act-merge{color:#7c3aed}.act-keep{color:#16a34a}.act-remove{color:#dc2626}
#chat-box{margin-top:32px;background:#fff;border-radius:10px;padding:20px;box-shadow:0 1px 4px #0001}
#chat-box h3{margin:0 0 4px;font-size:15px}
#idx-status{font-size:12px;color:#64748b;margin-bottom:12px}
#chat-input{display:flex;gap:8px}
#chat-q{flex:1;padding:9px 12px;border:1px solid #cbd5e1;border-radius:8px;font-size:14px;outline:none}
#chat-q:focus{border-color:#6366f1}
#chat-send{padding:9px 20px;background:#6366f1;color:#fff;border:none;border-radius:8px;font-size:14px;cursor:pointer}
#chat-send:disabled{opacity:.5;cursor:not-allowed}
#chat-history{margin-top:16px;display:flex;flex-direction:column;gap:16px}
.qa-item{font-size:13px}
.qa-q{font-weight:600;color:#1e293b;margin-bottom:4px}
.qa-a{color:#334155;line-height:1.7;white-space:pre-wrap}
.qa-sources{margin-top:8px;display:flex;flex-direction:column;gap:4px}
.qa-src{background:#f0f1f5;border-radius:6px;font-size:12px;color:#475569}
.qa-src summary{padding:6px 10px;cursor:pointer;display:flex;justify-content:space-between;align-items:center}
.qa-src .src-title{font-weight:600;color:#6366f1}
.qa-src .src-score{font-size:11px;color:#94a3b8;margin-left:8px}
.qa-src .src-text{padding:6px 10px 8px;border-top:1px solid #e2e8f0;color:#334155;line-height:1.6;white-space:pre-wrap}
</style></head>
<body>
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:24px">
  <h2 style="margin:0">知识图谱生成器</h2>
  <a href="/settings" style="font-size:13px;color:#6366f1">⚙ LLM 设置</a>
</div>
<div id="drop" onclick="document.getElementById('fi').click()"
  ondragover="ev(event,'over')" ondragleave="ev(event,'')" ondrop="drop(event)">
  <input id="fi" type="file" accept=".pdf,.md,.txt" multiple onchange="queue(this.files)">
  <div>拖拽文件到此处，或点击选择</div>
  <div style="font-size:12px;margin-top:6px">支持 PDF、Markdown、TXT，可批量上传</div>
</div>
<table id="tbl" style="display:none">
  <thead><tr><th>文件名</th><th>格式</th><th>大小</th><th>状态</th><th>操作</th></tr></thead>
  <tbody id="tbody"></tbody>
</table>
<div id="merge-box" style="display:none">
  <h3>多教材知识图谱合并</h3>
  <div style="font-size:12px;color:#64748b;margin-bottom:8px">选择 2 本以上已完成的教材进行语义合并</div>
  <div id="merge-stems"></div>
  <button id="merge-btn" onclick="doMerge()" disabled>开始合并</button>
  <div id="merge-result"></div>
</div>
<div id="chat-box">
  <h3>教材问答</h3>
  <div id="idx-status">索引加载中...</div>
  <div id="chat-input">
    <input id="chat-q" placeholder="输入问题，回答将引用教材原文..." onkeydown="if(event.key==='Enter')sendQ()">
    <button id="chat-send" onclick="sendQ()">提问</button>
  </div>
  <div id="chat-history"></div>
</div>
<script>
const rows = {};

function ev(e, cls) {
  e.preventDefault();
  document.getElementById('drop').className = cls;
}
function drop(e) {
  ev(e, '');
  queue(e.dataTransfer.files);
}

async function queue(files) {
  for (const f of files) {
    const fd = new FormData();
    fd.append('file', f);
    const res = await fetch('/upload', {method:'POST', body:fd});
    const d = await res.json();
    if (d.job_id) addRow(d.job_id, f.name, f.size);
  }
}

function fmt(n) {
  return n < 1024*1024 ? (n/1024).toFixed(1)+' KB' : (n/1024/1024).toFixed(1)+' MB';
}

function addRow(id, name, size) {
  document.getElementById('tbl').style.display = '';
  const ext = name.split('.').pop().toUpperCase();
  const tr = document.createElement('tr');
  tr.id = 'r_'+id;
  tr.innerHTML = `<td>${name}</td><td>${ext}</td><td>${fmt(size)}</td>
    <td><span class="badge pending" id="s_${id}">等待中</span></td>
    <td id="a_${id}">—</td>`;
  document.getElementById('tbody').appendChild(tr);
  rows[id] = {name, size};
  poll(id);
}

const STATUS_TEXT = {pending:'等待中', processing:'解析中', done:'已完成', failed:'失败'};
const doneStemSet = new Set();

function refreshMergeChips() {
  const box = document.getElementById('merge-stems');
  box.innerHTML = [...doneStemSet].map(s =>
    `<span class="stem-chip" id="chip_${s}" onclick="toggleChip('${s}')">${s}</span>`
  ).join('');
  const hasDone = doneStemSet.size >= 1;
  document.getElementById('chat-box').style.display = hasDone ? '' : 'none';
  document.getElementById('merge-box').style.display = doneStemSet.size >= 2 ? '' : 'none';
  updateMergeBtn();
  if (hasDone) refreshIndexStatus();
}

function toggleChip(s) {
  const el = document.getElementById('chip_'+s);
  el.classList.toggle('selected');
  updateMergeBtn();
}

function updateMergeBtn() {
  const sel = document.querySelectorAll('.stem-chip.selected').length;
  document.getElementById('merge-btn').disabled = sel < 2;
}

async function doMerge() {
  const stems = [...document.querySelectorAll('.stem-chip.selected')].map(el => el.id.replace('chip_',''));
  const btn = document.getElementById('merge-btn');
  btn.disabled = true; btn.textContent = '合并中...';
  document.getElementById('merge-result').innerHTML = '<span style="color:#64748b">正在进行语义对齐，请稍候...</span>';
  const res = await fetch('/api/merge', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({stems})});
  const d = await res.json();
  btn.disabled = false; btn.textContent = '开始合并';
  if (d.error) { document.getElementById('merge-result').textContent = d.error; return; }
  const s = d.stats;
  const ratio = (s.compress_ratio * 100).toFixed(1);
  const mergeCount = d.decisions.filter(x => x.action === 'merge').length;
  document.getElementById('merge-result').innerHTML = `
    <div class="stat-row">
      <div class="stat"><div class="v">${s.orig_nodes}</div><div class="l">原始节点</div></div>
      <div class="stat"><div class="v">${s.merged_nodes}</div><div class="l">合并后节点</div></div>
      <div class="stat"><div class="v">${s.orig_chars.toLocaleString()}</div><div class="l">原始字符数</div></div>
      <div class="stat"><div class="v">${s.merged_chars.toLocaleString()}</div><div class="l">整合后字符数</div></div>
      <div class="stat"><div class="v" style="color:${parseFloat(ratio)<=30?'#16a34a':'#dc2626'}">${ratio}%</div><div class="l">压缩比</div></div>
    </div>
    <div style="margin-bottom:8px">
      <a href="/view-merged" target="_blank">查看合并图谱</a> &nbsp;
      <a href="/download-merged">下载 JSON</a>
    </div>
    <details><summary style="cursor:pointer;font-size:13px;color:#6366f1">整合决策列表（${mergeCount} 次合并，共 ${d.decisions.length} 条）</summary>
    <table class="dec-table">
      <thead><tr><th>决策ID</th><th>操作</th><th>涉及节点</th><th>理由</th><th>置信度</th></tr></thead>
      <tbody>${d.decisions.filter(x=>x.action==='merge').map(x=>`<tr>
        <td>${x.decision_id}</td>
        <td class="act-${x.action}">${x.action}</td>
        <td style="font-size:11px">${x.affected_nodes.join(', ')}</td>
        <td>${x.reason}</td>
        <td>${(x.confidence*100).toFixed(0)}%</td>
      </tr>`).join('')}</tbody>
    </table></details>`;
}

async function poll(id) {
  const res = await fetch('/status/'+id);
  const d = await res.json();
  const badge = document.getElementById('s_'+id);
  badge.className = 'badge '+d.status;
  badge.textContent = STATUS_TEXT[d.status] || d.status;
  if (d.status === 'done') {
    const stem = encodeURIComponent(d.stem);
    document.getElementById('a_'+id).innerHTML =
      `<a href="/view/${stem}" target="_blank">查看</a> &nbsp;
       <a href="/download/${stem}">JSON</a>`;
    if (d.chapters && d.chapters.length) {
      const detail = document.createElement('tr');
      detail.innerHTML = `<td colspan="5" style="padding:0">
        <details style="padding:10px 14px;background:#f8fafc">
          <summary style="cursor:pointer;font-size:13px;color:#6366f1">
            章节结构（${d.chapters.length} 章）
          </summary>
          <table style="width:100%;margin-top:8px;font-size:13px;border-collapse:collapse">
            <thead><tr style="color:#94a3b8">
              <th style="text-align:left;padding:4px 8px">章节</th>
              <th style="text-align:left;padding:4px 8px">标题</th>
              <th style="text-align:right;padding:4px 8px">起始页</th>
              <th style="text-align:right;padding:4px 8px">字符数</th>
            </tr></thead>
            <tbody>${d.chapters.map(c => `<tr>
              <td style="padding:4px 8px;color:#64748b">${c.id}</td>
              <td style="padding:4px 8px">${c.title}</td>
              <td style="padding:4px 8px;text-align:right;color:#64748b">${c.page_start}</td>
              <td style="padding:4px 8px;text-align:right;color:#64748b">${c.char_count.toLocaleString()}</td>
            </tr>`).join('')}</tbody>
          </table>
        </details></td>`;
      document.getElementById('r_'+id).after(detail);
    }
    doneStemSet.add(d.stem);
    refreshMergeChips();
  } else if (d.status === 'failed') {
    document.getElementById('a_'+id).textContent = d.error || '';
  } else {
    setTimeout(() => poll(id), 1500);
  }
}
async function refreshIndexStatus() {
  const res = await fetch('/api/index-stats');
  const d = await res.json();
  const el = document.getElementById('idx-status');
  if (el) el.textContent = `已索引 ${d.sources} 本教材，共 ${d.chunks} 个知识块` +
    (d.source_list.length ? `（${d.source_list.join('、')}）` : '');
}

async function sendQ() {
  const q = document.getElementById('chat-q').value.trim();
  if (!q) return;
  const btn = document.getElementById('chat-send');
  btn.disabled = true;
  document.getElementById('chat-q').value = '';
  const item = document.createElement('div');
  item.className = 'qa-item';
  item.innerHTML = `<div class="qa-q">${q}</div><div class="qa-a" style="color:#94a3b8">思考中...</div>`;
  document.getElementById('chat-history').prepend(item);
  const res = await fetch('/api/chat', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({question:q})});
  const d = await res.json();
  const srcs = (d.sources||[]).map((s,i) => `<details class="qa-src">
    <summary>
      <span class="src-title">【${i+1}】《${s.source}》${s.chapter}（第${s.page_start}页）</span>
      <span class="src-score">相关度 ${(s.score*100).toFixed(1)}%</span>
    </summary>
    <div class="src-text">${s.excerpt}</div>
  </details>`).join('');
  item.innerHTML = `<div class="qa-q">${q}</div>
    <div class="qa-a">${d.answer||d.error||''}</div>
    ${srcs ? `<div class="qa-sources">${srcs}</div>` : ''}`;
  btn.disabled = false;
}
</script>
</body></html>"""


SETTINGS = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>LLM 设置</title>
<style>
*{box-sizing:border-box}
body{font-family:sans-serif;max-width:560px;margin:48px auto;padding:0 16px;background:#f5f6fa}
h2{margin-bottom:24px}
label{display:block;font-size:13px;color:#475569;margin-bottom:4px;margin-top:16px}
input{width:100%;padding:9px 12px;border:1px solid #cbd5e1;border-radius:8px;font-size:14px;outline:none}
input:focus{border-color:#6366f1}
button{margin-top:24px;padding:9px 24px;background:#6366f1;color:#fff;border:none;border-radius:8px;font-size:14px;cursor:pointer}
button:hover{background:#4f46e5}
#msg{margin-top:12px;font-size:13px;color:#16a34a}
a{color:#6366f1;font-size:13px;text-decoration:none}
</style></head>
<body>
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:24px">
  <h2 style="margin:0">LLM 设置</h2>
  <a href="/">← 返回</a>
</div>
<label>API Key</label>
<input id="api_key" type="password" placeholder="sk-..." value="{{api_key}}">
<label>Base URL <span style="color:#94a3b8">（留空使用默认 Anthropic 地址）</span></label>
<input id="base_url" placeholder="https://api.example.com" value="{{base_url}}">
<label>模型名称</label>
<input id="model" placeholder="claude-sonnet-4-6" value="{{model}}">
<button onclick="save()">保存</button>
<div id="msg"></div>
<script>
async function save() {
  const res = await fetch('/api/config', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({
      api_key: document.getElementById('api_key').value,
      base_url: document.getElementById('base_url').value,
      model: document.getElementById('model').value
    })
  });
  document.getElementById('msg').textContent = res.ok ? '已保存' : '保存失败';
}
</script>
</body></html>"""


@app.get("/")
def index():
    return render_template_string(INDEX)


@app.get("/settings")
def settings():
    cfg = config.load()
    return render_template_string(SETTINGS, **cfg)


@app.post("/api/config")
def save_config():
    data = request.get_json()
    config.save({k: data[k] for k in ("api_key", "base_url", "model") if k in data})
    return jsonify(ok=True)


@app.post("/upload")
def upload():
    f = request.files.get("file")
    if not f:
        return jsonify(error="no file"), 400
    dest = UPLOAD_DIR / f.filename
    f.save(dest)
    stem = Path(f.filename).stem
    job_id = stem
    with jobs_lock:
        jobs[job_id] = {"name": f.filename, "stem": stem, "status": "pending", "error": ""}
    threading.Thread(target=_process, args=(job_id, dest), daemon=True).start()
    return jsonify(job_id=job_id)


@app.get("/status/<job_id>")
def status(job_id):
    with jobs_lock:
        job = jobs.get(job_id)
    if not job:
        return jsonify(error="not found"), 404
    return jsonify(**job)


@app.get("/view/<stem>")
def view(stem):
    path = OUTPUT_DIR / f"{stem}.html"
    return send_file(path) if path.exists() else ("Not found", 404)


@app.get("/download/<stem>")
def download(stem):
    path = OUTPUT_DIR / f"{stem}.json"
    return send_file(path, as_attachment=True) if path.exists() else ("Not found", 404)


@app.get("/api/done-stems")
def done_stems():
    with jobs_lock:
        stems = [j["stem"] for j in jobs.values() if j["status"] == "done"]
    return jsonify(stems=stems)


@app.post("/api/merge")
def api_merge():
    stems = request.get_json().get("stems", [])
    if len(stems) < 2:
        return jsonify(error="至少选择 2 本教材"), 400
    graphs = []
    for stem in stems:
        p = OUTPUT_DIR / f"{stem}.json"
        if not p.exists():
            return jsonify(error=f"{stem} 尚未处理完成"), 400
        graphs.append(json.loads(p.read_text(encoding="utf-8")))
    merged = merge_graphs(graphs)
    out_json = OUTPUT_DIR / "_merged.json"
    out_html = OUTPUT_DIR / "_merged.html"
    out_json.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    render_html(merged, str(out_html))
    return jsonify(stats=merged["stats"], decisions=merged["decisions"])


@app.get("/view-merged")
def view_merged():
    path = OUTPUT_DIR / "_merged.html"
    return send_file(path) if path.exists() else ("Not found", 404)


@app.get("/download-merged")
def download_merged():
    path = OUTPUT_DIR / "_merged.json"
    return send_file(path, as_attachment=True) if path.exists() else ("Not found", 404)


@app.get("/api/index-stats")
def api_index_stats():
    return jsonify(index_stats())


@app.post("/api/chat")
def api_chat():
    data = request.get_json()
    question = (data or {}).get("question", "").strip()
    if not question:
        return jsonify(error="问题不能为空"), 400
    result = ask(question)
    return jsonify(result)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
