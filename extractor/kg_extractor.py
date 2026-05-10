from concurrent.futures import ThreadPoolExecutor, as_completed
from .llm_client import extract

CHUNK_SIZE = 4000
CHUNK_OVERLAP = 200


def _chunk_text(text: str) -> list[str]:
    if len(text) <= CHUNK_SIZE:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = start + CHUNK_SIZE
        chunks.append(text[start:end])
        start = end - CHUNK_OVERLAP
    return chunks


def _make_tasks(chapters: list, source: str) -> list[tuple]:
    """展开所有 (chapter, chunk_index, chunk_text) 任务"""
    tasks = []
    for ch in chapters:
        chunks = _chunk_text(ch["content"])
        for i, chunk in enumerate(chunks):
            title = ch["title"] if len(chunks) == 1 else f"{ch['title']} (片段{i+1}/{len(chunks)})"
            tasks.append((ch, title, chunk, source))
    return tasks


def _map_one(task: tuple) -> dict | None:
    ch, title, chunk, source = task
    try:
        result = extract(title, chunk)
        for n in result.get("nodes", []):
            n["chapter"] = ch["title"]
            n["source"] = source
        return result
    except Exception as e:
        print(f"[skip] {ch['chapter_id']} {title}: {e}")
        return None


def extract_from_chapters(chapters: list, source: str = "", max_workers: int = 4) -> dict:
    """Map（并行） + Reduce（汇总）"""
    tasks = _make_tasks(chapters, source)
    all_nodes, all_edges = [], []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_map_one, t): t for t in tasks}
        for future in as_completed(futures):
            result = future.result()
            if result:
                all_nodes.extend(result.get("nodes", []))
                all_edges.extend(result.get("edges", []))
    return {"nodes": all_nodes, "edges": all_edges}
