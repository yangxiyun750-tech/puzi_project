from __future__ import annotations

import math
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path

import pdfplumber


SOURCE_XML = Path("full_score_original_rebuilt/天使的脸_original_rebuilt.musicxml")
PAGE_RANGES = {2: (12, 14), 3: (15, 22), 4: (23, 29), 5: (30, 35), 6: (36, 41), 7: (42, 46), 8: (47, 54)}
NOTE_GLYPHS = {"œ", "˙", "w"}


root = ET.parse(SOURCE_XML).getroot()
names = [p.findtext("part-name") for p in root.find("part-list").findall("score-part")]
voice = root.findall("part")[names.index("Solo Voice")]


def is_han(text: str) -> bool:
    text = unicodedata.normalize("NFKC", text)
    return len(text) == 1 and "CJK" in unicodedata.name(text, "")


def source_notes(first: int, last: int):
    result = []
    for number in range(first, last + 1):
        measure = voice.find(f"measure[@number='{number}']")
        event_index = 0
        for note in measure.findall("note"):
            if note.find("chord") is not None or note.find("grace") is not None:
                continue
            if note.find("rest") is not None:
                continue
            p = note.find("pitch")
            result.append((number, event_index, f"{p.findtext('step')}{p.findtext('alter','')}{p.findtext('octave')}"))
            event_index += 1
    return result


with pdfplumber.open("天使的脸 - 乐谱和分谱.pdf") as pdf:
    for page_number, (first, last) in PAGE_RANGES.items():
        page = pdf.pages[page_number - 1]
        chars = [c for c in page.chars if c["x0"] >= 105]
        note_chars = [
            c for c in chars
            if 814 <= c["top"] <= 834 and c["text"] in NOTE_GLYPHS and "OpusStd" in c["fontname"]
        ]
        # One glyph per monophonic note onset; tolerate multiple glyph records at the same x.
        note_x = []
        for x in sorted(c["x0"] for c in note_chars):
            if not note_x or abs(x - note_x[-1]) > 1.0:
                note_x.append(x)
        xml_notes = source_notes(first, last)
        lyric_chars = [
            c for c in chars
            if 840 <= c["top"] <= 865 and is_han(c["text"])
        ]
        rows = [{"x": x, "lyrics": {}} for x in note_x]
        tops = sorted({round(c["top"], 1) for c in lyric_chars})
        for c in lyric_chars:
            verse = min(range(len(tops)), key=lambda i: abs(tops[i] - round(c["top"], 1))) + 1
            idx = min(range(len(note_x)), key=lambda i: abs(note_x[i] - c["x0"]))
            distance = abs(note_x[idx] - c["x0"])
            rows[idx]["lyrics"][verse] = unicodedata.normalize("NFKC", c["text"])
            rows[idx]["distance"] = max(distance, rows[idx].get("distance", 0))

        print(f"\nPAGE {page_number} measures {first}-{last}: PDF notes={len(note_x)} XML notes={len(xml_notes)} verses={len(tops)}")
        if len(note_x) != len(xml_notes):
            print("COUNT MISMATCH")
        for ordinal, (row, xml_note) in enumerate(zip(rows, xml_notes), 1):
            lyric_text = " ".join(f"v{k}={v}" for k, v in sorted(row["lyrics"].items()))
            print(f"{ordinal:02d} x={row['x']:.2f} m{xml_note[0]}#{xml_note[1]} {xml_note[2]} {lyric_text}")
