import requests
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config
from .retriever import search

SYSTEM = """你是一个严谨的教材问答助手。严格遵守以下规则：
1. 只基于提供的上下文回答，不使用自身知识
2. 每个回答必须附带来源引用，格式为 [教材名称, 第X章, 第X页]
3. 如果上下文中找不到答案，回复"当前知识库中未找到相关信息"，不得猜测"""


def ask(question: str, top_k: int = 5) -> dict:
    chunks = search(question, top_k=top_k)
    if not chunks:
        return {"answer": "尚未加载任何教材，请先上传并处理 PDF。", "sources": []}

    context = "\n\n".join(
        f"[{i+1}] 《{c['source']}》{c['chapter']}（第{c['page_start']}页）：\n{c['text']}"
        for i, c in enumerate(chunks)
    )

    cfg = config.load()
    resp = requests.post(
        f"{cfg['base_url']}/text/chatcompletion_v2",
        headers={"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"},
        json={
            "model": cfg.get("model", "MiniMax-M2.7"),
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": f"参考原文：\n{context}\n\n问题：{question}"}
            ],
            "temperature": 0.2
        },
        timeout=120
    )
    answer = resp.json()["choices"][0]["message"]["content"]
    sources = [{"source": c["source"], "chapter": c["chapter"],
                "page_start": c["page_start"], "score": c.get("score", 0),
                "excerpt": c["text"]}
               for c in chunks]
    return {"answer": answer, "sources": sources}
