import json
import requests
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config

SYSTEM_PROMPT_TEXT = """你是一个教材知识图谱抽取专家。从给定的教材章节中抽取核心知识点及其关系。

严格按 JSON 格式输出：
{
  "nodes": [
    {
      "id": "node_001",
      "name": "知识点名称",
      "definition": "简明定义（1-2句）",
      "category": "核心概念|定理|方法|现象",
      "chapter": "章节标题",
      "page": 页码数字或null
    }
  ],
  "edges": [
    {
      "source": "node_001",
      "target": "node_002",
      "relation_type": "prerequisite|parallel|contains|applies_to",
      "description": "关系说明（1句）"
    }
  ]
}

relation_type 说明：
- prerequisite：学习target前必须先掌握source
- parallel：source与target是同层级并列概念
- contains：source包含target（上下位关系）
- applies_to：source是target的应用场景

只输出 JSON，不要其他内容。"""


def _make_client():
    cfg = config.load()
    return {
        "api_key": cfg["api_key"],
        "model": cfg.get("model", "MiniMax-M2.7"),
        "base_url": cfg.get("base_url", "https://api.minimax.chat/v1")
    }


def extract(chapter_title: str, content: str) -> dict:
    cfg = _make_client()
    
    prompt = f"章节：{chapter_title}\n\n{content}"
    
    # --- 调试代码：看一眼发出去的内容 ---
    print(f"\n[DEBUG] 正在发送章节: {chapter_title}")
    print(f"[DEBUG] 内容长度: {len(content)} 字符")    
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT_TEXT},
        {"role": "user", "content": prompt}
    ]
    
    response = requests.post(
        f"{cfg['base_url']}/text/chatcompletion_v2",
        headers={
            "Authorization": f"Bearer {cfg['api_key']}",
            "Content-Type": "application/json"
        },
        json={
            "model": cfg["model"],
            "messages": messages,
            "temperature": 0.3
        },
        timeout=120
    )
    
    result = response.json()
    
    # 提取返回的文本
    if "choices" in result and len(result["choices"]) > 0:
        text = result["choices"][0]["message"]["content"]
    else:
        raise Exception(f"API返回异常: {result}")
    
    # 解析 JSON（处理可能的 markdown 标记）
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    
    return json.loads(text.strip())