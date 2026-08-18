"""Notation Object QA — pairing validation for 13 notation classes.

    tie / slur / tuplet / grace note / tremolo / trill / arpeggio /
    glissando / articulation / dynamics / hairpin(wedge) / ottava / fermata

Pairing rules are validated on the RAW MusicXML (ScoreIR models only a
subset). Unmatched "stop" annotations are SAFE_REPAIR (deterministic
cleanup of a dangling annotation); unterminated "start" annotations are
AI_REVIEW (the missing end may be an OMR miss that a human/AI must
confirm against the source).
"""

from __future__ import annotations

from pathlib import Path

from lxml import etree

from qa.qa_model import QACategory, QAIssue, QAStageResult, QAStatus

from score_engine.score_ir.score_ir import Score


def _local(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


class NotationQA:
    """Pairing and presence QA for notation objects."""

    def run(
        self,
        raw_xml: str | Path,
        exported_xml: str | Path | None = None,
        score: Score | None = None,
        pairing_source: str | Path | None = None,
        fidelity_dangling: dict[str, int] | None = None,
    ) -> QAStageResult:
        stage = QAStageResult(stage=QACategory.NOTATION_OBJECT)
        tree = etree.parse(str(raw_xml))
        root = tree.getroot()
        pairing_tree = etree.parse(str(pairing_source or raw_xml))
        pairing_root = pairing_tree.getroot()

        presence: dict[str, int] = {}
        # presence counts always come from the RAW OMR XML
        for part_elem in root.findall(".//part"):
            for meas in part_elem.findall("measure"):
                for note in meas.findall("note"):
                    if note.find("grace") is not None:
                        presence["grace"] = presence.get("grace", 0) + 1
                    notations = note.find("notations")
                    if notations is None:
                        continue
                    for child in notations:
                        tag = _local(child.tag)
                        presence[tag] = presence.get(tag, 0) + 1

from collections import Counter
from pathlib import Path

from lxml import etree

from qa.qa_model import QACategory, QAIssue, QAStageResult, QAStatus

from score_engine.score_ir.score_ir import Score


def _local(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


class NotationQA:
    """Pairing and presence QA for notation objects."""

    def run(
        self,
        raw_xml: str | Path,
        exported_xml: str | Path | None = None,
        score: Score | None = None,
        pairing_source: str | Path | None = None,
        fidelity_dangling: dict[str, int] | None = None,
    ) -> QAStageResult:
        stage = QAStageResult(stage=QACategory.NOTATION_OBJECT)
        tree = etree.parse(str(raw_xml))
        root = tree.getroot()
        pairing_tree = etree.parse(str(pairing_source or raw_xml))
        pairing_root = pairing_tree.getroot()

        presence: dict[str, int] = {}
        # presence counts always come from the RAW OMR XML
        for part_elem in root.findall(".//part"):
            for meas in part_elem.findall("measure"):
                for note in meas.findall("note"):
                    if note.find("grace") is not None:
                        presence["grace"] = presence.get("grace", 0) + 1
                    notations = note.find("notations")
                    if notations is None:
                        continue
                    for child in notations:
                        tag = _local(child.tag)
                        presence[tag] = presence.get(tag, 0) + 1

        for part_elem in pairing_root.findall(".//part"):
            part_id = part_elem.get("id", "P?")

            # Tie and slur pairing use Counter because the same number
            # is reused across the score (Audiveris outputs number="1"
            # for every tie/slur).
            open_tie: Counter = Counter()
            open_slur: Counter = Counter()
            open_tuplet: dict[str, str] = {}
            open_gliss: dict[str, str] = {}
            open_octave: dict[str, str] = {}
            open_wedge: dict[str, str] = {}    # "type:number" -> location

            for meas in part_elem.findall("measure"):
                mn = meas.get("number", "?")
                notes = [c for c in meas if _local(c.tag) == "note"]

                for note in notes:
                    n_voice = note.findtext("voice", "1")
                    n_id = note.get("id", "")
                    notations = note.find("notations")
                    if notations is None:
                        continue

                    for child in notations:
                        tag = _local(child.tag)
                        if tag == "tie":
                            continue
                        n_type = child.get("type", "")
                        n_num = child.get("number", "1")
                        loc = f"M{mn}-V{n_voice}"

                        if tag == "tied":
                            if n_type == "start":
                                open_tie[n_num] += 1
                            elif n_type == "stop":
                                if open_tie[n_num] > 0:
                                    open_tie[n_num] -= 1
                                else:
                                    stage.issues.append(
                                        QAIssue(
                                            issue_id=f"NOT-TIE-DANGLE-STOP-{part_id}-M{mn}",
                                            category=QACategory.NOTATION_OBJECT,
                                            check="tie_pairing",
                                            status=QAStatus.SAFE_REPAIR,
                                            severity="medium",
                                            part_id=part_id,
                                            measure_number=mn,
                                            voice_id=f"{part_id}-V{n_voice}",
                                            note_id=n_id,
                                            description=f"Tie stop without a matching start ({loc})",
                                            evidence={"tie_number": n_num},
                                            fix={"action": "remove_dangling_tie_stop"},
                                        )
                                    )
                        elif tag == "slur":
                            if n_type == "start":
                                open_slur[n_num] += 1
                            elif n_type == "continue":
                                if open_slur[n_num] <= 0:
                                    stage.issues.append(
                                        QAIssue(
                                            issue_id=f"NOT-SLUR-DANGLE-CONT-{part_id}-M{mn}",
                                            category=QACategory.NOTATION_OBJECT,
                                            check="slur_pairing",
                                            status=QAStatus.SAFE_REPAIR,
                                            severity="medium",
                                            part_id=part_id,
                                            measure_number=mn,
                                            voice_id=f"{part_id}-V{n_voice}",
                                            note_id=n_id,
                                            description=f"Slur continue without an open slur ({loc})",
                                            evidence={"slur_number": n_num},
                                            fix={"action": "remove_dangling_slur_continue"},
                                        )
                                    )
                            elif n_type == "stop":
                                if open_slur[n_num] > 0:
                                    open_slur[n_num] -= 1
                                else:
                                    stage.issues.append(
                                        QAIssue(
                                            issue_id=f"NOT-SLUR-DANGLE-STOP-{part_id}-M{mn}",
                                            category=QACategory.NOTATION_OBJECT,
                                            check="slur_pairing",
                                            status=QAStatus.SAFE_REPAIR,
                                            severity="medium",
                                            part_id=part_id,
                                            measure_number=mn,
                                            voice_id=f"{part_id}-V{n_voice}",
                                            note_id=n_id,
                                            description=f"Slur stop without a matching start ({loc})",
                                            evidence={"slur_number": n_num},
                                            fix={"action": "remove_dangling_slur_stop"},
                                        )
                                    )
                        elif tag == "tuplet":
                            if n_type == "start":
                                open_tuplet[n_num] = loc
                            elif n_type == "stop":
                                if n_num not in open_tuplet:
                                    stage.issues.append(
                                        QAIssue(
                                            issue_id=f"NOT-TUPLET-DANGLE-STOP-{part_id}-M{mn}",
                                            category=QACategory.NOTATION_OBJECT,
                                            check="tuplet_pairing",
                                            status=QAStatus.SAFE_REPAIR,
                                            severity="medium",
                                            part_id=part_id,
                                            measure_number=mn,
                                            voice_id=f"{part_id}-V{n_voice}",
                                            note_id=n_id,
                                            description=f"Tuplet stop without a matching start ({loc})",
                                            evidence={"tuplet_number": n_num},
                                            fix={"action": "remove_dangling_tuplet_stop"},
                                        )
                                    )
                                else:
                                    open_tuplet.pop(n_num, None)
                        elif tag == "glissando":
                            if n_type == "start":
                                open_gliss[n_num] = loc
                            elif n_type == "stop":
                                if n_num not in open_gliss:
                                    stage.issues.append(
                                        QAIssue(
                                            issue_id=f"NOT-GLISS-DANGLE-STOP-{part_id}-M{mn}",
                                            category=QACategory.NOTATION_OBJECT,
                                            check="glissando_pairing",
                                            status=QAStatus.SAFE_REPAIR,
                                            severity="medium",
                                            part_id=part_id,
                                            measure_number=mn,
                                            voice_id=f"{part_id}-V{n_voice}",
                                            note_id=n_id,
                                            description=f"Glissando stop without a matching start ({loc})",
                                            evidence={"glissando_number": n_num},
                                            fix={"action": "remove_dangling_glissando_stop"},
                                        )
                                    )
                                else:
                                    open_gliss.pop(n_num, None)
                        elif tag == "octave-shift":
                            key = f"{n_type}:{n_num}"
                            if n_type in ("up", "down"):
                                open_octave[key] = loc
                            elif n_type == "stop":
                                if key not in open_octave:
                                    stage.issues.append(
                                        QAIssue(
                                            issue_id=f"NOT-OTTAVA-DANGLE-STOP-{part_id}-M{mn}",
                                            category=QACategory.NOTATION_OBJECT,
                                            check="ottava_pairing",
                                            status=QAStatus.SAFE_REPAIR,
                                            severity="medium",
                                            part_id=part_id,
                                            measure_number=mn,
                                            voice_id=f"{part_id}-V{n_voice}",
                                            note_id=n_id,
                                            description=f"Ottava stop without a matching start ({loc})",
                                            evidence={"octave_shift_number": n_num},
                                            fix={"action": "remove_dangling_octave_stop"},
                                        )
                                    )
                                else:
                                    open_octave.pop(key, None)
                        elif tag == "wedge":
                            key = f"{n_type}:{n_num}"
                            if n_type in ("crescendo", "diminuendo"):
                                open_wedge[key] = loc
                            elif n_type == "stop":
                                stop_keys = [k for k in open_wedge if k.endswith(f":{n_num}")]
                                if not stop_keys:
                                    stage.issues.append(
                                        QAIssue(
                                            issue_id=f"NOT-HAIRPIN-DANGLE-STOP-{part_id}-M{mn}",
                                            category=QACategory.NOTATION_OBJECT,
                                            check="hairpin_pairing",
                                            status=QAStatus.SAFE_REPAIR,
                                            severity="medium",
                                            part_id=part_id,
                                            measure_number=mn,
                                            voice_id=f"{part_id}-V{n_voice}",
                                            note_id=n_id,
                                            description=f"Hairpin stop without a matching start ({loc})",
                                            evidence={"wedge_number": n_num},
                                            fix={"action": "remove_dangling_wedge_stop"},
                                        )
                                    )
                                else:
                                    for k in stop_keys:
                                        open_wedge.pop(k, None)

                    # grace note orphan: grace note as last note of measure
                    if note.find("grace") is not None and note is notes[-1]:
                        stage.issues.append(
                            QAIssue(
                                issue_id=f"NOT-GRACE-ORPHAN-{part_id}-M{mn}",
                                category=QACategory.NOTATION_OBJECT,
                                check="grace_note",
                                status=QAStatus.AI_REVIEW,
                                severity="medium",
                                part_id=part_id,
                                measure_number=mn,
                                voice_id=f"{part_id}-V{n_voice}",
                                note_id=n_id,
                                description=(
                                    f"Grace note is the last note of measure M{mn} — "
                                    f"principal note may be missing"
                                ),
                                confidence="medium",
                            )
                        )

            # End-of-part unterminated starts (only ties/slurs use Counter)
            for num, count in open_tie.items():
                if count > 0:
                    stage.issues.append(
                        QAIssue(
                            issue_id=f"NOT-TIE-UNTERMINATED-{part_id}-{num}",
                            category=QACategory.NOTATION_OBJECT,
                            check="tie_pairing",
                            status=QAStatus.AI_REVIEW,
                            severity="medium",
                            part_id=part_id,
                            description=f"Tie #{num} starts {count} time(s) but never stops — verify against source",
                            evidence={"unterminated_count": count},
                            confidence="medium",
                        )
                    )
            for num, count in open_slur.items():
                if count > 0:
                    stage.issues.append(
                        QAIssue(
                            issue_id=f"NOT-SLUR-UNTERMINATED-{part_id}-{num}",
                            category=QACategory.NOTATION_OBJECT,
                            check="slur_pairing",
                            status=QAStatus.AI_REVIEW,
                            severity="medium",
                            part_id=part_id,
                            description=f"Slur #{num} starts {count} time(s) but never stops — verify against source",
                            evidence={"unterminated_count": count},
                            confidence="medium",
                        )
                    )
            # Other objects (tuplet, gliss, octave, wedge) still use dict
            for kind, open_map, label in (
                ("tuplet", open_tuplet, "Tuplet"),
                ("glissando", open_gliss, "Glissando"),
                ("octave-shift", open_octave, "Ottava"),
                ("wedge", open_wedge, "Hairpin"),
            ):
                for key, loc in open_map.items():
                    stage.issues.append(
                        QAIssue(
                            issue_id=f"NOT-{kind.upper()}-UNTERMINATED-{part_id}-{key}",
                            category=QACategory.NOTATION_OBJECT,
                            check=f"{kind}_pairing",
                            status=QAStatus.AI_REVIEW,
                            severity="medium",
                            part_id=part_id,
                            measure_number=loc.split("-")[0].replace("M", ""),
                            description=(
                                f"{label} #{key} starts at {loc} but never stops — "
                                f"verify against source"
                            ),
                            evidence={"start_location": loc},
                            confidence="medium",
                        )
                    )

        # --- presence summary (13 object classes) ---------------------------
        stage.checks_run += 1
        summary = {
            "tie": presence.get("tied", 0),
            "slur": presence.get("slur", 0),
            "tuplet": presence.get("tuplet", 0),
            "grace_note": presence.get("grace", 0),
            "tremolo": presence.get("tremolo", 0),
            "trill": presence.get("trill-mark", 0),
            "arpeggio": presence.get("arpeggiate", 0),
            "glissando": presence.get("glissando", 0),
            "articulation": presence.get("articulations", 0),
            "dynamics": 0,  # filled below from directions
            "hairpin": presence.get("wedge", 0),
            "ottava": presence.get("octave-shift", 0),
            "fermata": presence.get("fermata", 0),
        }
        directions = root.findall(".//direction")
        for d in directions:
            dt = d.find("direction-type")
            if dt is not None and dt.find("dynamics") is not None:
                summary["dynamics"] += 1
        stage.issues.append(
            QAIssue(
                issue_id="NOT-PRESENCE-SUMMARY",
                category=QACategory.NOTATION_OBJECT,
                check="notation_presence",
                status=QAStatus.PASS,
                severity="info",
                description=f"Notation object counts: {summary}",
                evidence=summary,
            )
        )

        # --- ScoreIR consistency: ties --------------------------------------
        if score is not None:
            stage.checks_run += 1
            # Per-part tie counting from XML
            raw_tie_counts: dict[str, int] = {}
            for part_elem2 in root.findall(".//part"):
                raw_tie_counts[part_elem2.get("id", "?")] = len(
                    [t for t in part_elem2.iter("tied")]
                )
            for part in score.parts:
                ir_ties = sum(
                    len(note.ties)
                    for meas in part.measures
                    for voice in meas.voices
                    for ev in voice.events
                    for note in ([ev] if hasattr(ev, "ties") else getattr(ev, "notes", []))
                )
                raw = raw_tie_counts.get(part.id, 0)
                if ir_ties != raw:
                    stage.issues.append(
                        QAIssue(
                            issue_id=f"NOT-TIE-COUNT-MISMATCH-{part.id}",
                            category=QACategory.NOTATION_OBJECT,
                            check="tie_scoreir_consistency",
                            status=QAStatus.SAFE_REPAIR,
                            severity="medium",
                            part_id=part.id,
                            description=(
                                f"ScoreIR has {ir_ties} tie annotations but raw MusicXML "
                                f"has {raw} — importer duplicated <tie> + <tied> elements"
                            ),
                            evidence={"scoreir_ties": ir_ties, "raw_ties": raw},
                            fix={"action": "dedupe_ties"},
                        )
                    )

        # --- notation fidelity: raw vs ScoreIR-exported ----------------------
        if exported_xml and Path(exported_xml).exists():
            stage.checks_run += 1
            exp_tree = etree.parse(str(exported_xml))
            exp_presence: dict[str, int] = {}
            for part_elem in exp_tree.getroot().findall(".//part"):
                for meas in part_elem.findall("measure"):
                    for note in meas.findall("note"):
                        notations = note.find("notations")
                        if notations is not None:
                            for child in notations:
                                tag = _local(child.tag)
                                exp_presence[tag] = exp_presence.get(tag, 0) + 1
            dropped = {}
            # tags the V1 ScoreIR importer/exporter chain cannot carry at all
            not_carried = {
                "tuplet", "fermata", "arpeggiate", "glissando",
                "octave-shift", "wedge", "trill-mark", "tremolo", "grace",
            }
            # SAFE_REPAIR dangling removals are deliberate; the post-fix
            # comparison receives their counts via fidelity_dangling.
            dangling_removed: dict[str, int] = dict(fidelity_dangling or {})
            # Pre-fix fidelity compares raw vs the faithful export directly
            # (the export still mirrors raw, including invalid annotations).
            # Post-fix comparison receives the fixer's removal counts above.

            for tag, count in presence.items():
                if tag == "tie":
                    # legacy <tie> (outside <notations>) is not processed —
                    # pairing and export both use <tied>/<tie> pairing form
                    continue
                exp_tag = "tie" if tag == "tied" else tag
                exp_count = exp_presence.get(exp_tag, 0)
                if tag in not_carried:
                    if count > 0:
                        dropped[tag] = {"raw": count, "exported": 0}
                else:
                    expected = count - dangling_removed.get(tag, 0)
                    if exp_count != expected:
                        dropped[tag] = {"raw": count, "exported": exp_count}
            if dropped:
                stage.issues.append(
                    QAIssue(
                        issue_id="NOT-FIDELITY-GAP",
                        category=QACategory.NOTATION_OBJECT,
                        check="notation_fidelity",
                        status=QAStatus.HUMAN_REVIEW,
                        severity="high",
                        description=(
                            f"ScoreIR-exported MusicXML drops or changes notation "
                            f"objects present in the raw OMR: {dropped}. The V1 "
                            f"ScoreIR model does not carry these objects — extend "
                            f"the importer/exporter before delivery."
                        ),
                        evidence={"dropped": dropped},
                    )
                )
            else:
                stage.issues.append(
                    QAIssue(
                        issue_id="NOT-FIDELITY-OK",
                        category=QACategory.NOTATION_OBJECT,
                        check="notation_fidelity",
                        status=QAStatus.PASS,
                        severity="info",
                        description="Notation fidelity: exported notation matches raw OMR",
                    )
                )

        # Stage status
        if any(i.status == QAStatus.HUMAN_REVIEW for i in stage.issues):
            stage.status = "FAIL"
        elif any(i.status in (QAStatus.AI_REVIEW,) for i in stage.issues):
            stage.status = "WARN"
        else:
            stage.status = "PASS"
        return stage
