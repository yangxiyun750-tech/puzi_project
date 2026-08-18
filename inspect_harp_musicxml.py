from __future__ import annotations

import sys
import xml.etree.ElementTree as ET


path = sys.argv[1] if len(sys.argv) > 1 else "final_production/baseline/lyrics_roundtrip.musicxml"
root = ET.parse(path).getroot()
names = [p.findtext("part-name") for p in root.find("part-list").findall("score-part")]
harp = root.findall("part")[names.index("Harp")]
for measure in harp.findall("measure"):
    number = int(measure.get("number"))
    events = []
    idx = 0
    for note in measure.findall("note"):
        if note.find("rest") is not None:
            label = "R"
        else:
            p = note.find("pitch")
            label = p.findtext("step") + p.findtext("alter", "") + p.findtext("octave")
        flags = []
        if note.find("notations/arpeggiate") is not None:
            flags.append("ARP")
        if note.find("notations/glissando") is not None:
            flags.append("GLISS:" + note.find("notations/glissando").get("type", ""))
        events.append(f"#{idx}:{label}:st{note.findtext('staff','1')}:{note.findtext('type','?')}:{','.join(flags)}")
        if note.find("chord") is None:
            idx += 1
    if any("ARP" in e or "GLISS" in e for e in events) or number in (33,):
        print(f"m{number}\t" + " | ".join(events))
