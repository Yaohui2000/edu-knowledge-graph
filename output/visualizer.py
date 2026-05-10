import json
from pathlib import Path

# palette: up to 12 distinct source colors
COLORS = ["#6366f1","#f59e0b","#10b981","#ef4444","#3b82f6","#ec4899",
          "#8b5cf6","#14b8a6","#f97316","#84cc16","#06b6d4","#a855f7"]

HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>知识图谱</title>
<script src="https://unpkg.com/cytoscape@3.28.1/dist/cytoscape.min.js"></script>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{display:flex;height:100vh;font-family:sans-serif;background:#0f172a}}
#cy{{flex:1;height:100vh}}
#sidebar{{width:300px;background:#1e293b;color:#e2e8f0;padding:20px;overflow-y:auto;
  display:flex;flex-direction:column;gap:12px;border-left:1px solid #334155}}
#sidebar h3{{font-size:16px;color:#f8fafc;border-bottom:1px solid #334155;padding-bottom:8px}}
#search{{width:100%;padding:8px 10px;border-radius:8px;border:1px solid #475569;
  background:#0f172a;color:#e2e8f0;font-size:13px;outline:none}}
#search:focus{{border-color:#6366f1}}
#info{{font-size:13px;line-height:1.7;color:#cbd5e1}}
#info .field{{margin-bottom:6px}}
#info .label{{color:#94a3b8;font-size:11px;text-transform:uppercase;letter-spacing:.05em}}
#info .value{{color:#f1f5f9}}
#legend{{font-size:12px}}
.leg-item{{display:flex;align-items:center;gap:8px;margin-bottom:4px}}
.leg-dot{{width:10px;height:10px;border-radius:50%;flex-shrink:0}}
</style></head>
<body>
<div id="cy"></div>
<div id="sidebar">
  <h3>知识图谱</h3>
  <input id="search" placeholder="搜索知识点..." oninput="search(this.value)">
  <div id="info"><span style="color:#64748b">点击节点查看详情</span></div>
  <div id="legend"></div>
</div>
<script>
const data = {data};
const sources = [...new Set(data.nodes.map(n => n.source || '未知'))];
const palette = {palette};
const colorMap = Object.fromEntries(sources.map((s,i) => [s, palette[i % palette.length]]));

const maxFreq = Math.max(1, ...data.nodes.map(n => n.freq || 0));

const cy = cytoscape({{
  container: document.getElementById('cy'),
  elements: [
    ...data.nodes.map(n => ({{
      data: {{
        id: n.id, label: n.name||n.id, category: n.category||'', freq: n.freq||0,
        chapter: n.chapter||'', source: n.source||'', definition: n.definition||'',
        page: n.page||null,
        color: colorMap[n.source||'未知'],
        size: 24 + (n.freq||0) / maxFreq * 32
      }}
    }})),
    ...data.edges.map((e,i) => ({{
      data: {{ id:'e'+i, source: e.source, target: e.target, label: e.relation_type, description: e.description||'' }}
    }}))
  ],
  style: [
    {{ selector:'node', style:{{
      'background-color':'data(color)',
      'width':'data(size)', 'height':'data(size)',
      'label':'data(label)', 'color':'#f1f5f9', 'font-size':11,
      'text-valign':'bottom','text-margin-y':4,
      'text-outline-color':'#0f172a','text-outline-width':2,
      'border-width':0, 'transition-property':'border-width border-color',
      'transition-duration':'0.15s'
    }} }},
    {{ selector:'node.highlighted', style:{{'border-width':3,'border-color':'#fbbf24'}} }},
    {{ selector:'node.dimmed', style:{{'opacity':0.2}} }},
    {{ selector:'edge', style:{{
      'width':1.5,'line-color':'#334155','target-arrow-color':'#334155',
      'target-arrow-shape':'triangle','curve-style':'bezier',
      'label':'data(label)','font-size':9,'color':'#64748b',
      'text-rotation':'autorotate','text-outline-color':'#0f172a','text-outline-width':1.5
    }} }}
  ],
  layout:{{ name:'cose', animate:false, nodeRepulsion:8000, idealEdgeLength:120 }},
  wheelSensitivity: 0.3
}});

cy.on('tap','node', e => {{
  const d = e.target.data();
  document.getElementById('info').innerHTML = `
    <div class="field"><div class="label">名称</div><div class="value">${{d.label}}</div></div>
    <div class="field"><div class="label">分类</div><div class="value">${{d.category||'—'}}</div></div>
    <div class="field"><div class="label">定义</div><div class="value">${{d.definition||'—'}}</div></div>
    <div class="field"><div class="label">所在章节</div><div class="value">${{d.chapter||'—'}}</div></div>
    <div class="field"><div class="label">页码</div><div class="value">${{d.page||'—'}}</div></div>
    <div class="field"><div class="label">来源教材</div><div class="value">${{d.source||'—'}}</div></div>
    <div class="field"><div class="label">出现频次</div><div class="value">${{d.freq}}</div></div>`;
  cy.elements().addClass('dimmed');
  e.target.removeClass('dimmed').addClass('highlighted');
  e.target.neighborhood().removeClass('dimmed');
}});

cy.on('tap', e => {{
  if (e.target === cy) {{
    cy.elements().removeClass('dimmed highlighted');
    document.getElementById('info').innerHTML = '<span style="color:#64748b">点击节点查看详情</span>';
  }}
}});

function search(q) {{
  if (!q) {{ cy.elements().removeClass('dimmed highlighted'); return; }}
  const matched = cy.nodes().filter(n => n.data('label').includes(q));
  cy.elements().addClass('dimmed');
  matched.removeClass('dimmed').addClass('highlighted');
  matched.neighborhood().removeClass('dimmed');
}}

// legend
const leg = document.getElementById('legend');
leg.innerHTML = '<div style="color:#94a3b8;font-size:11px;text-transform:uppercase;letter-spacing:.05em;margin-bottom:6px">教材来源</div>' +
  sources.map(s => `<div class="leg-item"><div class="leg-dot" style="background:${{colorMap[s]}}"></div><span>${{s}}</span></div>`).join('');
</script>
</body></html>"""


def render(graph: dict, path: str) -> None:
    html = HTML.format(
        data=json.dumps(graph, ensure_ascii=False),
        palette=json.dumps(COLORS)
    )
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
