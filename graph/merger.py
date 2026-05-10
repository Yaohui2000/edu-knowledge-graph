import json
import math
import requests
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config

EMBED_SIM_THRESHOLD = 0.85
COMPRESS_RATIO = 0.30


def _cfg():
    return config.load()


# ── Embedding ──────────────────────────────────────────────────────────────

def _embed_batch(texts: list[str]) -> list[list[float]]:
    cfg = _cfg()
    resp = requests.post(
        f"{cfg['base_url']}/embeddings",
        headers={"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"},
        json={"model": "embo-01", "input": texts, "type": "query"},
        timeout=60
    )
    data = resp.json()
    return [item["embedding"] for item in data["data"]]


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na and nb else 0.0


# ── LLM judge ─────────────────────────────────────────────────────────────

def _llm_judge(group: list[dict]) -> dict:
    """Ask LLM whether a group of nodes refer to the same concept and pick the best."""
    cfg = _cfg()
    names = [f"[{n['id']}] {n['name']} ({n.get('source','')}): {n.get('definition','')[:80]}" for n in group]
    prompt = (
        "以下知识点是否描述同一概念？如果是，选出描述最完整的版本作为保留节点。\n\n"
        + "\n".join(names)
        + '\n\n严格按JSON输出：{"same": true/false, "keep_id": "节点ID或null", "reason": "一句话理由", "confidence": 0.0-1.0}'
    )
    resp = requests.post(
        f"{cfg['base_url']}/text/chatcompletion_v2",
        headers={"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"},
        json={"model": cfg.get("model", "MiniMax-M2.7"),
              "messages": [{"role": "user", "content": prompt}],
              "temperature": 0.1},
        timeout=60
    )
    text = resp.json()["choices"][0]["message"]["content"].strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


# ── Core merge logic ───────────────────────────────────────────────────────

def merge_graphs(graphs: list[dict]) -> dict:
    """
    graphs: list of {nodes, edges} dicts, each node must have 'source' field.
    Returns {nodes, edges, decisions, stats}.
    """
    all_nodes = []
    for g in graphs:
        all_nodes.extend(g.get("nodes", []))

    orig_chars = sum(len(n.get("definition", "")) for n in all_nodes)

    # Step 1: embed all node names
    names = [n["name"] for n in all_nodes]
    embeddings = _embed_batch(names)

    # Step 2: greedy clustering by cosine similarity
    clusters: list[list[int]] = []
    assigned = [False] * len(all_nodes)
    for i in range(len(all_nodes)):
        if assigned[i]:
            continue
        cluster = [i]
        assigned[i] = True
        for j in range(i + 1, len(all_nodes)):
            if not assigned[j] and _cosine(embeddings[i], embeddings[j]) >= EMBED_SIM_THRESHOLD:
                cluster.append(j)
                assigned[j] = True
        clusters.append(cluster)

    # Step 3: LLM judge for multi-node clusters, build decisions
    decisions = []
    merged_nodes = []
    alias: dict[str, str] = {}  # old_id -> canonical_id
    decision_counter = 1

    for cluster in clusters:
        group = [all_nodes[i] for i in cluster]

        if len(group) == 1:
            n = group[0]
            n.setdefault("freq", 1)
            n.setdefault("sources", [n.get("source", "")])
            merged_nodes.append(n)
            decisions.append({
                "decision_id": f"dec_{decision_counter:03d}",
                "action": "keep",
                "affected_nodes": [n["id"]],
                "result_node": n["id"],
                "reason": "唯一节点，无需合并",
                "confidence": 1.0
            })
        else:
            verdict = _llm_judge(group)
            if verdict.get("same", False) and verdict.get("keep_id"):
                keep_id = verdict["keep_id"]
                keep_node = next((n for n in group if n["id"] == keep_id), group[0])
                keep_node["freq"] = len(group)
                keep_node["sources"] = list({n.get("source", "") for n in group})
                merged_nodes.append(keep_node)
                for n in group:
                    alias[n["id"]] = keep_node["id"]
                decisions.append({
                    "decision_id": f"dec_{decision_counter:03d}",
                    "action": "merge",
                    "affected_nodes": [n["id"] for n in group],
                    "result_node": keep_node["id"],
                    "reason": verdict.get("reason", ""),
                    "confidence": verdict.get("confidence", 0.0)
                })
            else:
                # LLM says not same — keep all
                for n in group:
                    n.setdefault("freq", 1)
                    n.setdefault("sources", [n.get("source", "")])
                    merged_nodes.append(n)
                decisions.append({
                    "decision_id": f"dec_{decision_counter:03d}",
                    "action": "keep",
                    "affected_nodes": [n["id"] for n in group],
                    "result_node": None,
                    "reason": verdict.get("reason", "语义不同，分别保留"),
                    "confidence": verdict.get("confidence", 0.0)
                })
        decision_counter += 1

    # Step 4: enforce 30% compression — trim definitions if needed
    merged_chars = sum(len(n.get("definition", "")) for n in merged_nodes)
    if orig_chars > 0 and merged_chars / orig_chars > COMPRESS_RATIO:
        budget = int(orig_chars * COMPRESS_RATIO)
        per_node = max(20, budget // len(merged_nodes))
        for n in merged_nodes:
            if len(n.get("definition", "")) > per_node:
                n["definition"] = n["definition"][:per_node] + "…"
        merged_chars = sum(len(n.get("definition", "")) for n in merged_nodes)

    # Step 5: merge edges
    valid_ids = {n["id"] for n in merged_nodes}
    all_edges = []
    for g in graphs:
        all_edges.extend(g.get("edges", []))

    seen_edges, merged_edges = set(), []
    for e in all_edges:
        src = alias.get(e["source"], e["source"])
        tgt = alias.get(e["target"], e["target"])
        key = (src, tgt, e.get("relation_type", ""))
        if key not in seen_edges and src in valid_ids and tgt in valid_ids:
            seen_edges.add(key)
            merged_edges.append({**e, "source": src, "target": tgt})

    stats = {
        "orig_nodes": len(all_nodes),
        "merged_nodes": len(merged_nodes),
        "orig_chars": orig_chars,
        "merged_chars": merged_chars,
        "compress_ratio": round(merged_chars / orig_chars, 4) if orig_chars else 0
    }

    return {"nodes": merged_nodes, "edges": merged_edges, "decisions": decisions, "stats": stats}
