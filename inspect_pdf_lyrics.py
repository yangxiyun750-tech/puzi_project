from __future__ import annotations

import re
import sys

import pdfplumber


def is_han(text: str) -> bool:
    return bool(re.fullmatch(r"[\u3400-\u9fff]+", text))


page_number = int(sys.argv[1])
with pdfplumber.open("天使的脸 - 乐谱和分谱.pdf") as pdf:
    page = pdf.pages[page_number - 1]
    print(f"PAGE {page_number} {page.width}x{page.height}")
    words = page.extract_words(x_tolerance=1, y_tolerance=1, keep_blank_chars=False)
    for word in words:
        text = word["text"]
        if is_han(text):
            print(f"{text}\tx0={word['x0']:.2f}\tx1={word['x1']:.2f}\ttop={word['top']:.2f}\tbottom={word['bottom']:.2f}")
