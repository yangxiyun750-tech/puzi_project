from __future__ import annotations

import sys
from pypdf import PdfReader


sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
reader = PdfReader("天使的脸 - 乐谱和分谱.pdf")
for i, page in enumerate(reader.pages[8:], 9):
    text = page.extract_text(extraction_mode="layout") or ""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    print(i, " | ".join(lines[:5]))
