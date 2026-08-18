from __future__ import annotations

import sys
import pdfplumber

sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")


page_number = int(sys.argv[1])
with pdfplumber.open("天使的脸 - 乐谱和分谱.pdf") as pdf:
    page = pdf.pages[page_number - 1]
    chars = [c for c in page.chars if 795 <= c["top"] <= 870 and c["x0"] >= 105]
    chars.sort(key=lambda c: (round(c["top"], 1), c["x0"]))
    for c in chars:
        t = c["text"].replace("\n", "\\n")
        print(f"{t!r}\tx={c['x0']:.2f}\ttop={c['top']:.2f}\tfont={c['fontname']}\tsize={c['size']:.2f}")
