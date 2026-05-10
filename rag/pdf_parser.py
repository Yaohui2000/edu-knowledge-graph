import fitz
import re
from pathlib import Path


class PDFParser:
    """
    PDF 教材解析器
    功能：
    1. 逐页解析
    2. 自动章节识别
    3. 从真正的第一章开始
    4. 过滤作者信息、版权页、目录等前置内容
    """

    def __init__(self, file_path):
        self.file_path = file_path
        self.doc = fitz.open(file_path)

        # 通用章节识别：第一章 / 第1章 / 第二章 ...
        self.chapter_pattern = re.compile(
            r"(第\s*[一二三四五六七八九十百千万0-9]+\s*章[^\n]*)"
        )

        # 真正的起始章节：第一章 / 第1章
        self.first_chapter_pattern = re.compile(
            r"(第\s*[一1]\s*章[^\n]*)"
        )

    def clean_text(self, text):
        text = text.replace("\u3000", " ")
        text = re.sub(r"\n+", "\n", text)
        return text.strip()

    def parse_by_page(self):
        chapters = []
        current_chapter = None
        total_chars = 0
        started = False   # 是否已经进入“正文第一章之后”

        for page_index, page in enumerate(self.doc):
            text = page.get_text()
            text = self.clean_text(text)

            if not text:
                continue

            total_chars += len(text)

            # 还没到第一章之前，全部跳过
            if not started:
                first_match = self.first_chapter_pattern.search(text)
                if not first_match:
                    continue
                started = True

            # 检测章节
            match = self.chapter_pattern.search(text)

            if match:
                # 保存上一章
                if current_chapter:
                    current_chapter["content"] = "\n".join(current_chapter["content"])
                    current_chapter["page_end"] = page_index
                    current_chapter["char_count"] = len(current_chapter["content"])
                    chapters.append(current_chapter)

                # 新章节
                current_chapter = {
                    "chapter_id": f"ch_{len(chapters)+1:02d}",
                    "title": match.group(1).strip(),
                    "page_start": page_index + 1,
                    "page_end": page_index + 1,
                    "content": [text]
                }
            else:
                if current_chapter:
                    current_chapter["content"].append(text)

        # 保存最后一章
        if current_chapter:
            current_chapter["content"] = "\n".join(current_chapter["content"])
            current_chapter["page_end"] = len(self.doc)
            current_chapter["char_count"] = len(current_chapter["content"])
            chapters.append(current_chapter)

        return chapters, total_chars

    def parse(self):
        chapters, total_chars = self.parse_by_page()

        return {
            "textbook_id": Path(self.file_path).stem,
            "filename": Path(self.file_path).name,
            "title": Path(self.file_path).stem,
            "total_pages": len(self.doc),
            "total_chars": total_chars,
            "chapters": chapters
        }


if __name__ == "__main__":
    pdf_path = "test.pdf"
    parser = PDFParser(pdf_path)
    result = parser.parse()

    print("=" * 60)
    print("教材名称:", result["title"])
    print("总页数:", result["total_pages"])
    print("总字符数:", result["total_chars"])
    print("章节数量:", len(result["chapters"]))
    print("=" * 60)

    for chapter in result["chapters"]:
        print("\n" + "-" * 40)
        print("章节ID:", chapter["chapter_id"])
        print("章节标题:", chapter["title"])
        print("起始页:", chapter["page_start"])
        print("结束页:", chapter["page_end"])
        print("字符数:", chapter["char_count"])
        print("\n内容预览:")
        print(chapter["content"][:300])
        print("-" * 40)