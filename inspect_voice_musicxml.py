from __future__ import annotations

import sys
import xml.etree.ElementTree as ET


path = sys.argv[1] if len(sys.argv) > 1 else "full_score_original_rebuilt/天使的脸_original_rebuilt.musicxml"
root = ET.parse(path).getroot()
names = [p.findtext("part-name") for p in root.find("part-list").findall("score-part")]
voice = root.findall("part")[names.index("Solo Voice")]
for measure in voice.findall("measure"):
    number = int(measure.get("number"))
    if number < 12:
        continue
    events = []
    for note in measure.findall("note"):
        if note.find("rest") is not None:
            label = "R"
        else:
            p = note.find("pitch")
            label = p.findtext("step") + p.findtext("alter", "") + p.findtext("octave")
        lyrics = "/".join(
            f"v{lyric.get('number', '1')}:{lyric.findtext('text', '')}[{lyric.findtext('syllabic', '')}]"
            for lyric in note.findall("lyric")
        )
        events.append(f"{label}:{note.findtext('type','?')}:{note.findtext('duration','?')}:{lyrics}")
    print(f"m{number}\t" + " | ".join(events))
