from pypdf import PdfReader
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

reader = PdfReader("天使的脸 - 乐谱和分谱.pdf")
page_number = int(sys.argv[1]) if len(sys.argv) > 1 else 1
page = reader.pages[page_number - 1]
print(f"===== PAGE {page_number} =====")
print(page.extract_text(extraction_mode="layout") or "")
