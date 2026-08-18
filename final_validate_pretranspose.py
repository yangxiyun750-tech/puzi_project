from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path


PATH = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("final_production/baseline/repaired_v2.musicxml")
root = ET.parse(PATH).getroot()
parts = root.findall("part")
names = [p.findtext("part-name") for p in root.find("part-list").findall("score-part")]
assert len(parts) == 18
assert all(len(p.findall("measure")) == 54 for p in parts)

voice = parts[names.index("Solo Voice")]
lyrics = []
for measure in voice.findall("measure"):
    for note in measure.findall("note"):
        for lyric in note.findall("lyric"):
            lyrics.append((int(measure.get("number")), lyric.get("number", "1"), lyric.findtext("text", ""), lyric.find("extend") is not None))
text = "".join(x[2] for x in lyrics)
for expected in (
    "看看你的脸", "想看看你的脸", "读出了一个青春的笑颜", "只看到一双会唱歌的眼",
    "飘动的云朵", "生命的泉", "春天终于到了", "嗅到了花儿的芬芳",
    "在与病魔抗争的日子里我们曾一起许下希望", "让痛苦远离让美丽续航",
    "病房你脱去口罩的那天一定让我看看天使的脸",
):
    assert all(ch in text for ch in expected), expected
assert sum(1 for x in lyrics if x[0] >= 15) == 186

harp = parts[names.index("Harp")]
assert sum(1 for _ in harp.iter("arpeggiate")) == 42
assert sum(1 for _ in harp.iter("slide")) == 2
slides = list(harp.iter("slide"))
assert [s.get("type") for s in slides] == ["start", "stop"]
assert slides[0].text == "gliss."

first = {name: part.find("measure[@number='1']") for name, part in zip(names, parts)}
assert first["Flute"].findtext("attributes/key/fifths") == "5"
assert first["B-flat Clarinet"].findtext("attributes/key/fifths") == "-5"
assert first["Horn in F 1"].findtext("attributes/key/fifths") == "6"
assert first["B-flat Clarinet"].findtext("attributes/transpose/chromatic") == "-2"
assert first["Horn in F 1"].findtext("attributes/transpose/chromatic") == "-7"

print("PASS")
print(f"18 parts; 54 measures; {len(lyrics)} total lyrics; 42 Harp arpeggiate tags; native Harp glissando start/stop; B-major source written-key map verified")
