import re
from pathlib import Path


CHAPTER_RE = re.compile(r"(第\s*[一二三四五六七八九十百千万0-9]+\s*章[^\n]*)")
FIRST_RE = re.compile(r"第\s*[一1]\s*章")
MD_HEADING_RE = re.compile(r"^#{1,3}\s+(.+)", re.MULTILINE)


def _split_chapters(text: str, source_name: str) -> list[dict]:
    """Split plain text into chapters using Chinese chapter headings."""
    lines = text.splitlines()
    chapters, current, started = [], None, False

    for i, line in enumerate(lines):
        if not started:
            if FIRST_RE.search(line):
                started = True
            else:
                continue

        m = CHAPTER_RE.search(line)
        if m:
            if current:
                current["content"] = "\n".join(current["_buf"])
                current["char_count"] = len(current["content"])
                chapters.append(current)
            current = {
                "chapter_id": f"ch_{len(chapters)+1:02d}",
                "title": m.group(1).strip(),
                "page_start": 0,
                "page_end": 0,
                "_buf": [line],
            }
        elif current:
            current["_buf"].append(line)

    if current:
        current["content"] = "\n".join(current["_buf"])
        current["char_count"] = len(current["content"])
        chapters.append(current)

    # Fallback: no chapter headings found — treat whole file as one chapter
    if not chapters:
        chapters = [{
            "chapter_id": "ch_01",
            "title": source_name,
            "page_start": 0,
            "page_end": 0,
            "content": text,
            "char_count": len(text),
        }]

    for c in chapters:
        c.pop("_buf", None)
    return chapters


def parse_text(file_path: str) -> dict:
    path = Path(file_path)
    text = path.read_text(encoding="utf-8", errors="ignore")

    # For Markdown: strip heading markers but keep heading text
    if path.suffix.lower() == ".md":
        text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)

    chapters = _split_chapters(text, path.stem)
    return {
        "textbook_id": path.stem,
        "filename": path.name,
        "title": path.stem,
        "total_pages": 0,
        "total_chars": len(text),
        "chapters": chapters,
    }
