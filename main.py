import argparse
from pathlib import Path

from rag.pdf_parser import PDFParser
from extractor.kg_extractor import extract_from_chapters
from graph.builder import build
from output.json_exporter import export
from output.visualizer import render


def run(pdf_path: str, out_dir: str = "data/output") -> None:
    stem = Path(pdf_path).stem
    print(f"[1/4] 解析 {pdf_path}")
    chapters = PDFParser(pdf_path).parse()["chapters"]
    print(f"      {len(chapters)} 个章节")

    print("[2/4] 抽取知识图谱...")
    raw = extract_from_chapters(chapters, source=stem)
    print(f"      原始节点 {len(raw['nodes'])}，边 {len(raw['edges'])}")

    print("[3/4] 去重合并...")
    graph = build(raw)
    print(f"      净节点 {len(graph['nodes'])}，边 {len(graph['edges'])}")

    print("[4/4] 导出结果...")
    export(graph, f"{out_dir}/{stem}.json")
    render(graph, f"{out_dir}/{stem}.html")
    print(f"      {out_dir}/{stem}.json")
    print(f"      {out_dir}/{stem}.html")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", help="PDF 文件路径")
    parser.add_argument("--out", default="data/output", help="输出目录")
    args = parser.parse_args()
    run(args.pdf, args.out)
