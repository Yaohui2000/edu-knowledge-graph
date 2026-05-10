def build(raw: dict) -> dict:
    nodes = _dedup_nodes(raw.get("nodes", []))
    id_map = {n["id"]: n["id"] for n in nodes}  # canonical ids
    # collect alias map from duplicates
    alias = {}
    for n in raw.get("nodes", []):
        if "_alias" in n:
            alias[n["id"]] = n["_alias"]
    edges = _dedup_edges(raw.get("edges", []), set(id_map), alias)
    return {"nodes": nodes, "edges": edges}


def _dedup_nodes(nodes: list) -> list:
    seen: dict = {}  # name -> first node
    result = []
    for n in nodes:
        key = n["name"]
        if key not in seen:
            seen[key] = n
            n.setdefault("freq", 0)
            n.setdefault("sources", [])
            result.append(n)
        else:
            existing = seen[key]
            existing["freq"] = existing.get("freq", 0) + 1
            src = n.get("source", "")
            if src and src not in existing["sources"]:
                existing["sources"].append(src)
            n["_alias"] = existing["id"]
    return result


def _dedup_edges(edges: list, valid_ids: set, alias: dict) -> list:
    seen, result = set(), []
    for e in edges:
        src = alias.get(e["source"], e["source"])
        tgt = alias.get(e["target"], e["target"])
        rel = e["relation_type"]
        key = (src, tgt, rel)
        if key not in seen and src in valid_ids and tgt in valid_ids:
            seen.add(key)
            result.append({"source": src, "target": tgt, "relation_type": rel, "description": e.get("description", "")})
    return result
