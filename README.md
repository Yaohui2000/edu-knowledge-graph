# 教材知识图谱系统

基于 LLM 的教材知识图谱构建、多教材语义整合与 RAG 问答系统。

## 功能

- 上传 PDF/Markdown/TXT 教材，自动抽取知识点和关系，生成交互式知识图谱
- 多教材语义合并：Embedding + LLM 双重判断，识别跨教材重复知识点
- RAG 问答：FAISS 向量检索 + BM25 混合检索，每条回答附带原文引用

## 环境依赖

- Python 3.10+
- 无需 Node.js（前端使用 CDN）

## 安装

```bash
git clone <repo-url>
cd pdf-agent
pip install -r requirements.txt
```

## 配置

复制环境变量模板并填入 API Key：

```bash
cp .env.example .env
```

编辑 `.env`：

```
MINIMAX_API_KEY=your_api_key_here
MINIMAX_BASE_URL=https://api.minimax.chat/v1
MINIMAX_MODEL=MiniMax-M2.7
```

加载环境变量：

```bash
# Linux/macOS
export $(cat .env | xargs)

# Windows PowerShell
Get-Content .env | ForEach-Object { $k,$v = $_ -split '=',2; [System.Environment]::SetEnvironmentVariable($k,$v) }
```

也可以在启动后通过界面右上角「⚙ LLM 设置」填写 API Key，会保存到本地 `.config.json`（已在 `.gitignore` 中排除）。

## 启动

**开发环境：**

```bash
python web.py
```

**生产环境（阿里云等）：**

```bash
mkdir -p data/pdfs data/output
gunicorn -w 2 -b 0.0.0.0:5000 web:app
```

访问 `http://localhost:5000`

## 使用说明

1. **上传教材**：拖拽或点击选择 PDF/MD/TXT 文件，支持批量上传
2. **等待处理**：系统自动解析章节、抽取知识图谱、建立向量索引
3. **查看图谱**：点击「查看」打开交互式知识图谱，支持点击节点、缩放、搜索
4. **多教材合并**：上传 2 本以上教材后，选择教材点击「开始合并」，查看整合决策和压缩比
5. **RAG 问答**：在问答框输入问题，回答附带教材来源引用，点击引用可展开原文

## 项目结构

```
pdf-agent/
├── web.py              # Flask 主入口
├── main.py             # 命令行入口
├── config.py           # 配置管理（支持环境变量）
├── requirements.txt
├── .env.example
├── rag/
│   ├── pdf_parser.py   # PDF 解析
│   ├── text_parser.py  # MD/TXT 解析
│   ├── embed.py        # Embedding API 封装
│   ├── retriever.py    # FAISS + BM25 向量索引
│   └── chat.py         # RAG 问答
├── extractor/
│   ├── kg_extractor.py # Map-Reduce 知识图谱抽取
│   └── llm_client.py   # LLM API 封装
├── graph/
│   ├── builder.py      # 单教材去重合并
│   └── merger.py       # 跨教材语义合并
├── output/
│   ├── visualizer.py   # Cytoscape.js 可视化
│   └── json_exporter.py
└── docs/
    ├── 需求分析.md
    ├── 系统设计.md
    └── Agent架构说明.md
```

## 注意事项

- `.config.json` 和 `data/` 目录已在 `.gitignore` 中排除，不会提交到 Git
- 向量索引存储在内存中，服务重启后需重新上传教材
- 生产部署建议在 Nginx 后面运行 Gunicorn，并配置 HTTPS
