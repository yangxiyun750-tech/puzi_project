from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path


SOURCE = Path("full_score_original_rebuilt/天使的脸_original_rebuilt.musicxml")
OUTDIR = Path("final_production/baseline")
OUTPUT = OUTDIR / "天使的脸_pretranspose_repaired.musicxml"


LYRICS: dict[int, dict[int, dict[int, tuple[str, str | None]]]] = {
    15: {0:{1:("看",None),2:("想",None)},1:{1:("不",None),2:("看",None)},2:{1:("到",None),2:("看",None)},3:{1:("你",None),2:("你",None)},4:{1:("的",None),2:("的",None)}},
    16: {0:{1:("脸",None),2:("脸",None)},1:{1:("隔",None),2:("透",None)},2:{1:("离",None),2:("过",None)}},
    17: {0:{1:("衣",None),2:("潮",None)},1:{1:("上",None),2:("湿",None)},2:{1:("好",None),2:("的",None)},3:{1:("听",None),2:("护",None)},4:{1:("的",None),2:("目",None)}},
    18: {0:{1:("名",None),2:("镜",None)},3:{1:("字",None)},4:{1:("读",None),2:("只",None)},5:{1:("出",None),2:("看",None)},6:{1:("了",None),2:("到",None)}},
    19: {0:{1:("一",None),2:("一",None)},1:{1:("个",None),2:("双",None)},2:{2:("会",None)},3:{1:("青",None),2:("唱",None)},4:{1:("春",None),2:("歌",None)},5:{1:("的",None),2:("的",None)}},
    20: {0:{1:("笑",None),2:("眼",None)},1:{1:("颜","start")},2:{1:("", "stop")}},
    21: {0:{1:("你",None),2:("流",None)},1:{2:("淌",None)},2:{2:("着",None)},3:{1:("忙",None),2:("关",None)},4:{1:("碌",None),2:("怀",None)},5:{1:("的",None),2:("的",None)}},
    22: {0:{1:("身",None),2:("音",None)},2:{1:("影",None),2:("符",None)},3:{1:("如",None),2:("像",None)}},
    23: {0:{1:("飘",None),2:("生",None)},1:{1:("动",None)},2:{1:("的",None)},3:{1:("云",None),2:("命",None)},4:{2:("的",None)}},
    24: {0:{1:("朵",None),2:("泉",None)},1:{1:("我",None),2:("我",None)}},
    25: {0:{1:("无",None),2:("知",None)},1:{1:("数",None),2:("道",None)},2:{1:("次",None),2:("那",None)},3:{1:("去",None),2:("里",None)},4:{1:("猜",None),2:("不",None)},5:{1:("想",None),2:("会",None)}},
    26: {0:{1:("你",None),2:("有",None)},1:{1:("的",None)},2:{1:("模",None),2:("眼",None)},3:{1:("样",None),2:("泪",None)},4:{1:("你",None),2:("你",None)},5:{2:("用",None)}},
    27: {0:{1:("为",None),2:("汗",None)},1:{1:("我",None),2:("水",None)},2:{1:("送",None),2:("雕",None)},3:{1:("来",None),2:("刻",None)},4:{1:("早",None),2:("最",None)},5:{1:("春",None),2:("美",None)},6:{1:("的",None),2:("的",None)},7:{1:("暖",None),2:("容",None)}},
    28: {0:{1:("阳",None)}},
    33: {0:{2:("颜",None)}},
    34: {0:{1:("春",None)},1:{1:("天",None)},2:{1:("终",None)},3:{1:("于",None)},4:{1:("到",None)}},
    35: {0:{1:("了",None)},1:{1:("我",None)},2:{1:("已",None)}},
    36: {0:{1:("嗅",None)},1:{1:("到",None)},2:{1:("了",None)},3:{1:("花",None)},4:{1:("儿",None)},5:{1:("的",None)}},
    37: {0:{1:("芬",None)},1:{1:("芳",None)},2:{1:("在",None)},3:{1:("与",None)}},
    38: {0:{1:("病",None)},1:{1:("魔",None)},2:{1:("抗",None)},3:{1:("争",None)},4:{1:("的",None)}},
    39: {0:{1:("日",None)},2:{1:("子",None)},3:{1:("里",None)},4:{1:("我",None)},5:{1:("们",None)}},
    40: {0:{1:("曾",None)},1:{1:("一",None)},2:{1:("起",None)},3:{1:("许",None)},4:{1:("下",None)},5:{1:("希",None)}},
    41: {0:{1:("望",None)}},
    42: {0:{1:("让",None)},2:{1:("痛",None)},3:{1:("苦",None)}},
    43: {0:{1:("远",None)},2:{1:("离",None)},3:{1:("让",None)}},
    44: {0:{1:("美",None)},2:{1:("丽",None)},3:{1:("续",None)}},
    45: {0:{1:("航",None)},1:{1:("期",None)},2:{1:("待",None)}},
    46: {0:{1:("我",None)},3:{1:("走",None)},4:{1:("出",None)}},
    47: {0:{1:("病",None)},3:{1:("房",None)},4:{1:("你",None)}},
    48: {0:{1:("脱",None)},1:{1:("去",None)},2:{1:("口",None)},3:{1:("罩",None)},4:{1:("的",None)},5:{1:("那",None)},6:{1:("天",None)}},
    49: {0:{1:("一",None)},1:{1:("定",None)},2:{1:("让",None)},3:{1:("我",None)},4:{1:("看",None)},5:{1:("看",None)}},
    50: {0:{1:("", "continue")}},
    51: {0:{1:("天",None)},1:{1:("使",None)},2:{1:("的",None)}},
    52: {0:{1:("脸",None)}},
}


def add_lyric(note: ET.Element, verse: int, text: str, extend: str | None) -> None:
    lyric = ET.SubElement(note, "lyric", number=str(verse))
    if text:
        ET.SubElement(lyric, "syllabic").text = "single"
        ET.SubElement(lyric, "text").text = text
    if extend:
        ET.SubElement(lyric, "extend", type=extend)


def add_harp_glissando(root: ET.Element) -> None:
    names = [p.findtext("part-name") for p in root.find("part-list").findall("score-part")]
    harp = root.findall("part")[names.index("Harp")]
    measure = harp.find("measure[@number='33']")
    lower = [
        n for n in measure.findall("note")
        if n.findtext("staff", "1") == "2" and n.find("rest") is None and n.find("chord") is None
    ]
    if len(lower) != 2:
        raise RuntimeError(f"Harp m33: expected two lower-staff notes, found {len(lower)}")
    start, stop = lower
    for note, kind, text in ((start, "start", "gliss."), (stop, "stop", None)):
        notations = note.find("notations")
        if notations is None:
            notations = ET.SubElement(note, "notations")
        gliss = ET.SubElement(notations, "glissando", type=kind, number="1", **{"line-type": "solid"})
        if text:
            gliss.text = text


def main() -> int:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    tree = ET.parse(SOURCE)
    root = tree.getroot()
    names = [p.findtext("part-name") for p in root.find("part-list").findall("score-part")]
    voice = root.findall("part")[names.index("Solo Voice")]
    inserted = 0
    for measure in voice.findall("measure"):
        number = int(measure.get("number"))
        if number < 15:
            continue
        pitched = [n for n in measure.findall("note") if n.find("rest") is None and n.find("chord") is None and n.find("grace") is None]
        for note in pitched:
            for lyric in list(note.findall("lyric")):
                note.remove(lyric)
        for note_index, verses in LYRICS.get(number, {}).items():
            if note_index >= len(pitched):
                raise RuntimeError(f"m{number} note {note_index}: no pitched event")
            for verse, (text, extend) in sorted(verses.items()):
                add_lyric(pitched[note_index], verse, text, extend)
                inserted += 1
    add_harp_glissando(root)
    if inserted != 188:
        raise RuntimeError(f"unexpected lyric object count {inserted}")
    ET.indent(tree, space="  ")
    tree.write(OUTPUT, encoding="UTF-8", xml_declaration=True)
    print(f"wrote {OUTPUT} with {inserted} lyric objects")
    return 0


if __name__ == "__main__":
    sys.exit(main())
