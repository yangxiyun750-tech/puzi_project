"""Divisions detector for raw OMR MusicXML.

Tracks <divisions> values across measures and reports changes. A change
in divisions is not inherently an error, but frequent or large changes
in a single part are flagged for review because they can mask OMR
rhythm misreadings.
"""

from __future__ import annotations

from lxml import etree

from omr_normalization.detectors.base import OMRDetector, _local
from omr_normalization.issue_model import OMRCategory, OMREditSafety, OMRIssue, OMRStatus


class DivisionsDetector(OMRDetector):
    """Detect divisions-related patterns in raw OMR MusicXML."""

    name = "divisions"

    def detect(self, tree: etree._ElementTree, input_path: str = "") -> list[OMRIssue]:
        issues: list[OMRIssue] = []
        root = tree.getroot()

        for part_elem in root.findall(".//part"):
            part_id = part_elem.get("id", "P?")
            cur_divisions: int | None = None
            divisions_seen: list[int] = []
            last_change_measure = ""

            for meas in part_elem.findall("measure"):
                mn = meas.get("number", "?")
                attrs = meas.find("attributes")
                div_val: int | None = None
                if attrs is not None:
                    div_elem = attrs.find("divisions")
                    if div_elem is not None and div_elem.text:
                        div_val = int(div_elem.text)

                if div_val is not None:
                    divisions_seen.append(div_val)
                    if cur_divisions is not None and div_val != cur_divisions:
                        issues.append(
                            self._make_issue(
                                issue_id=f"DIV-CHANGE-{part_id}-M{mn}",
                                category=OMRCategory.DIVISIONS,
                                check="divisions_change",
                                status=OMRStatus.INFO,
                                severity="info",
                                edit_safety=OMREditSafety.INFORMATIONAL,
                                part_id=part_id,
                                measure_number=mn,
                                description=(
                                    f"Divisions changes from {cur_divisions} to {div_val}"
                                ),
                                evidence={
                                    "previous": cur_divisions,
                                    "current": div_val,
                                },
                            )
                        )
                        last_change_measure = mn
                    cur_divisions = div_val
                else:
                    # Inherit previous divisions for tracking
                    if cur_divisions is not None:
                        divisions_seen.append(cur_divisions)

            unique = sorted(set(divisions_seen))
            if len(unique) > 1:
                issues.append(
                    self._make_issue(
                        issue_id=f"DIV-VARY-{part_id}",
                        category=OMRCategory.DIVISIONS,
                        check="divisions_variety",
                        status=OMRStatus.INFO,
                        severity="info",
                        edit_safety=OMREditSafety.INFORMATIONAL,
                        part_id=part_id,
                        description=(
                            f"Part uses multiple divisions values: {unique}"
                        ),
                        evidence={"divisions_seen": unique},
                    )
                )

        return issues
