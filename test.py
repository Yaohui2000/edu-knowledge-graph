import argparse
from pathlib import Path

from rag.pdf_parser import PDFParser
from extractor.kg_extractor import extract_from_chapters
from graph.builder import build
from output.json_exporter import export
from output.visualizer import render

pdf_path='01_局部解剖学.pdf'
out_dir: str = "data/output"    
stem = Path(pdf_path).stem
chapters = PDFParser(pdf_path).parse()["chapters"]
chapters=chapters[210:213]
raw = extract_from_chapters(chapters, source=stem)
graph = build(raw)
export(graph, f"{out_dir}/{stem}.json")
render(graph, f"{out_dir}/{stem}.html")