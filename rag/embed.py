import requests
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config


def embed(texts: list[str]) -> list[list[float]]:
    cfg = config.load()
    resp = requests.post(
        f"{cfg['base_url']}/embeddings",
        headers={"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"},
        json={"model": "embo-01", "input": texts, "type": "query"},
        timeout=60
    )
    data = resp.json()
    return [item["embedding"] for item in data["data"]]
