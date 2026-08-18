"""Measure Localization + Evidence Crop V2.

Maps QA issues to precise PDF coordinates using Audiveris OMR geometry
(stack/staff coordinates) combined with MusicXML <print> layout.

Produces:
- context crop (previous + target + next measure)
- target crop (single measure, high resolution, correct staff)

Principles:
- Use Audiveris geometry, never guess measure position
- Bass Trombone: crop only its single staff
- Piano: preserve Grand Staff (RH + LH) together
- Same Part+Measure issues are deduplicated into one evidence package
"""

from __future__ import annotations

import json
import zipfile
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lxml import etree
from PIL import Image

from score_engine.score_ir.score_ir import Score


@dataclass
class MeasureLocation:
    part_id: str
    measure: str
    page: int
    system: int  # MusicXML system index (0-based)
    stack_id: int  # Audiveris stack id within system
    staff_index: int  # 0 for P1, 1 for P2 RH, 2 for P2 LH
    bbox: tuple[int, int, int, int]  # x1, y1, x2, y2
    confidence: float
    context_bbox: tuple[int, int, int, int] | None = None  # for context crop
    context_measures: list[str] = field(default_factory=list)


class MeasureLocator:
    """Map MusicXML measure numbers to PDF bboxes using Audiveris geometry."""

    def __init__(self, omr_path: str | Path, raw_xml_path: str | Path, rendered_dir: str | Path):
        self.omr_path = Path(omr_path)
        self.raw_xml_path = Path(raw_xml_path)
        self.rendered_dir = Path(rendered_dir)
        self.sheet_data: dict[int, list[dict]] = {}  # sheet_num -> systems
        self.measure_map: dict[str, dict[str, dict]] = {}  # part_id -> {measure -> {page, system, order}}
        self._load_sheets()
        self._load_measure_map()

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _load_sheets(self) -> None:
        with zipfile.ZipFile(self.omr_path) as z:
            sheet_nums = set()
            for name in z.namelist():
                m = re.match(r"sheet#(\d+)/sheet#\1\.xml", name)
                if m:
                    sheet_nums.add(int(m.group(1)))
            for sheet_num in sorted(sheet_nums):
                info = self._extract_sheet(z, sheet_num)
                if info:
                    self.sheet_data[sheet_num] = info

    def _extract_sheet(self, zf: zipfile.ZipFile, sheet_num: int) -> list[dict] | None:
        name = f"sheet#{sheet_num}/sheet#{sheet_num}.xml"
        if name not in zf.namelist():
            return None
        content = zf.read(name).decode("utf-8", errors="replace")

        systems = []
        sys_matches = re.findall(r'<system[^>]*id="(\d+)"[^>]*>(.*?)</system>', content, re.DOTALL)
        for sys_id, sys_content in sys_matches:
            system_info = {"id": int(sys_id), "stacks": [], "staffs": []}

            for sid, left, right in re.findall(
                r'<stack[^>]*id="(\d+)"[^>]*left="(\d+)"[^>]*right="(\d+)"[^>]*>', sys_content
            ):
                system_info["stacks"].append({"id": int(sid), "left": int(left), "right": int(right)})

            for sid, left, right, staff_content in re.findall(
                r'<staff[^>]*id="(\d+)"[^>]*left="(\d+)"[^>]*right="(\d+)"[^>]*>(.*?)</staff>',
                sys_content,
                re.DOTALL,
            ):
                y_coords = re.findall(r'x="\d+" y="([\d.]+)"', staff_content)
                if y_coords:
                    y_min = min(float(y) for y in y_coords)
                    y_max = max(float(y) for y in y_coords)
                    system_info["staffs"].append({
                        "id": int(sid),
                        "left": int(left),
                        "right": int(right),
                        "y_min": y_min,
                        "y_max": y_max,
                    })

            systems.append(system_info)
        return systems

    def _load_measure_map(self) -> None:
        tree = etree.parse(str(self.raw_xml_path))
        root = tree.getroot()

        for part in root.findall(".//part"):
            part_id = part.get("id", "?")
            mapping = {}
            page = 1
            system = 0
            order = 0

            # Build complete sequence: MusicXML numbers + inferred missing numbers
            # We reconstruct the intended sequence by checking for gaps in the
            # MusicXML measure numbers within each system.
            raw_measures = []
            for meas in part.findall("measure"):
                mn = meas.get("number", "0")
                new_page = False
                new_system = False
                for child in meas:
                    tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                    if tag == "print":
                        if child.get("new-page") == "yes":
                            new_page = True
                        if child.get("new-system") == "yes":
                            new_system = True
                raw_measures.append({
                    "number": mn,
                    "new_page": new_page,
                    "new_system": new_system,
                })

            # Now walk the sequence, filling gaps when MusicXML jumps over a number
            idx = 0
            while idx < len(raw_measures):
                item = raw_measures[idx]
                mn = item["number"]

                if item["new_page"]:
                    page += 1
                    system = 0
                    order = 0
                if item["new_system"]:
                    system += 1
                    order = 0

                mapping[mn] = {"page": page, "system": system, "order": order}
                order += 1

                # Check for gap to next measure in same system
                if idx + 1 < len(raw_measures):
                    next_item = raw_measures[idx + 1]
                    try:
                        cur_num = int(mn)
                        next_num = int(next_item["number"])
                        if (
                            not next_item["new_page"]
                            and not next_item["new_system"]
                            and next_num > cur_num + 1
                        ):
                            # Gap detected: fill missing numbers
                            for gap_num in range(cur_num + 1, next_num):
                                mapping[str(gap_num)] = {
                                    "page": page,
                                    "system": system,
                                    "order": order,
                                    "inferred": True,
                                }
                                order += 1
                    except ValueError:
                        pass

                idx += 1

            self.measure_map[part_id] = mapping

    # ------------------------------------------------------------------
    # Coordinate lookup
    # ------------------------------------------------------------------

    def locate(self, part_id: str, measure: str) -> MeasureLocation | None:
        """Locate a measure in the PDF. Returns None if measure is missing."""
        mapping = self.measure_map.get(part_id, {})
        info = mapping.get(measure)
        if info is None:
            # Try to infer from neighbors (for missing measures)
            return self._infer_missing(part_id, measure, mapping)

        return self._bbox_from_info(part_id, measure, info)

    def _bbox_from_info(self, part_id: str, measure: str, info: dict) -> MeasureLocation | None:
        page = info["page"]
        system_idx = info["system"]
        order = info["order"]

        sheet = self.sheet_data.get(page)
        if not sheet or system_idx >= len(sheet):
            return None

        system = sheet[system_idx]
        if order >= len(system["stacks"]):
            return None

        stack = system["stacks"][order]
        staffs = system["staffs"]

        # Staff index: P1=0 (single staff), P2=1 (RH), 2 (LH)
        if part_id == "P1":
            staff_idx = 0
        else:
            staff_idx = 1  # P2 RH

        if staff_idx >= len(staffs):
            return None

        staff = staffs[staff_idx]

        # y bounds: staff lines ± margin (3 interlines above, 3 below)
        interline = (staff["y_max"] - staff["y_min"]) / 4.0
        margin = interline * 3
        y1 = int(staff["y_min"] - margin)
        y2 = int(staff["y_max"] + margin)

        # For Piano, include both RH and LH in the same system
        if part_id == "P2" and len(staffs) >= 3:
            lh_staff = staffs[2]
            y2 = max(y2, int(lh_staff["y_max"] + margin))

        bbox = (stack["left"], y1, stack["right"], y2)

        # Context: previous + current + next measure
        context_bbox, context_measures = self._context_bbox(part_id, measure, info, system_idx, order, page)

        return MeasureLocation(
            part_id=part_id,
            measure=measure,
            page=page,
            system=system_idx,
            stack_id=stack["id"],
            staff_index=staff_idx,
            bbox=bbox,
            confidence=0.95,
            context_bbox=context_bbox,
            context_measures=context_measures,
        )

    def _context_bbox(
        self, part_id: str, measure: str, info: dict, system_idx: int, order: int, page: int
    ) -> tuple[tuple[int, int, int, int] | None, list[str]]:
        """Compute context bbox covering prev + current + next measure.

        For cross-system or cross-page contexts, we only include measures
        that are on the same page as the target.
        """
        try:
            mn = int(measure)
        except ValueError:
            return None, []

        prev_mn = str(mn - 1)
        next_mn = str(mn + 1)

        mapping = self.measure_map.get(part_id, {})
        prev_info = mapping.get(prev_mn)
        next_info = mapping.get(next_mn)

        # Get current stack info
        sheet = self.sheet_data.get(page, [])
        if system_idx >= len(sheet):
            return None, []
        system = sheet[system_idx]
        stacks = system["stacks"]
        if not stacks:
            return None, []

        x1 = stacks[min(order, len(stacks) - 1)]["left"]
        x2 = stacks[min(order, len(stacks) - 1)]["right"]

        # Extend to previous measure if on same page and same system
        if prev_info and prev_info["page"] == page and prev_info["system"] == system_idx:
            prev_order = prev_info["order"]
            if prev_order < len(stacks):
                x1 = stacks[prev_order]["left"]

        # Extend to next measure if on same page and same system
        if next_info and next_info["page"] == page and next_info["system"] == system_idx:
            next_order = next_info["order"]
            if next_order < len(stacks):
                x2 = stacks[next_order]["right"]

        # y range: cover the staff area
        staffs = system["staffs"]
        if part_id == "P1":
            staff = staffs[0]
            interline = (staff["y_max"] - staff["y_min"]) / 4.0
            margin = interline * 3
            y1 = int(staff["y_min"] - margin)
            y2 = int(staff["y_max"] + margin)
        else:
            staff = staffs[1]
            interline = (staff["y_max"] - staff["y_min"]) / 4.0
            margin = interline * 3
            y1 = int(staff["y_min"] - margin)
            y2 = int(staff["y_max"] + margin)
            if len(staffs) >= 3:
                lh_staff = staffs[2]
                y2 = max(y2, int(lh_staff["y_max"] + margin))

        context_bbox = (x1, y1, x2, y2)
        context_measures = [prev_mn, measure, next_mn]

        return context_bbox, context_measures

    def _infer_missing(self, part_id: str, measure: str, mapping: dict) -> MeasureLocation | None:
        """Infer location for a missing measure from its neighbors."""
        try:
            mn = int(measure)
        except ValueError:
            return None

        # Find nearest existing measures
        existing = sorted(int(m) for m in mapping.keys())
        if not existing:
            return None

        before = max((m for m in existing if m < mn), default=None)
        after = min((m for m in existing if m > mn), default=None)

        if before is None or after is None:
            return None

        before_info = mapping[str(before)]
        after_info = mapping[str(after)]

        # Case 1: same page, same system — infer between stacks
        if before_info["page"] == after_info["page"] and before_info["system"] == after_info["system"]:
            return self._infer_same_system(part_id, measure, before_info, after_info, before, after)

        # Case 2: same page, different system — use end of before's system
        if before_info["page"] == after_info["page"]:
            return self._infer_different_system(part_id, measure, before_info, before)

        # Case 3: cross-page — use end of before's page
        return self._infer_cross_page(part_id, measure, before_info, before)

    def _infer_same_system(
        self, part_id: str, measure: str, before_info: dict, after_info: dict, before: int, after: int
    ) -> MeasureLocation | None:
        """Infer missing measure within the same system."""
        page = before_info["page"]
        system_idx = before_info["system"]

        sheet = self.sheet_data.get(page)
        if not sheet or system_idx >= len(sheet):
            return None

        system = sheet[system_idx]
        stacks = system["stacks"]
        staffs = system["staffs"]

        before_order = before_info["order"]
        after_order = after_info["order"]

        # Estimate x range: extend from before's left to after's right
        # This handles the case where Audiveris merged the missing measure
        # with an adjacent stack, leaving zero gap between them.
        if before_order < len(stacks) and after_order < len(stacks):
            left = stacks[before_order]["left"]
            right = stacks[after_order]["right"]
            # Narrow to a plausible single-measure width if possible
            total_width = right - left
            if after_order - before_order > 1:
                # Missing measure is between them
                slot_width = total_width / (after_order - before_order + 1)
                left = stacks[before_order]["right"]
                right = left + int(slot_width)
            else:
                # No gap between adjacent stacks — expand to cover both
                left = stacks[before_order]["left"]
                right = stacks[after_order]["right"]
        else:
            left = stacks[min(before_order, len(stacks) - 1)]["left"]
            right = left + 400

        y1, y2 = self._staff_y_bounds(part_id, staffs)

        return MeasureLocation(
            part_id=part_id,
            measure=measure,
            page=page,
            system=system_idx,
            stack_id=-1,
            staff_index=0 if part_id == "P1" else 1,
            bbox=(left, y1, right, y2),
            confidence=0.5,
            context_bbox=None,
            context_measures=[str(before), measure, str(after)],
        )

    def _infer_different_system(self, part_id: str, measure: str, before_info: dict, before: int) -> MeasureLocation | None:
        """Infer missing measure that belongs to before's system but was
        skipped by the MusicXML exporter (Audiveris has the stack)."""
        page = before_info["page"]
        system_idx = before_info["system"]

        sheet = self.sheet_data.get(page)
        if not sheet or system_idx >= len(sheet):
            return None

        system = sheet[system_idx]
        stacks = system["stacks"]
        staffs = system["staffs"]

        if not stacks:
            return None

        # If Audiveris has more stacks than MusicXML measures in this system,
        # the missing measure occupies one of the trailing stacks.
        musicxml_measures_in_system = sum(
            1 for info in self.measure_map.get(part_id, {}).values()
            if info["page"] == page and info["system"] == system_idx and not info.get("inferred")
        )
        if len(stacks) > musicxml_measures_in_system:
            # The missing measure is in one of the extra stacks.
            # Use the stack at position = number of real measures before it.
            target_index = musicxml_measures_in_system
            if target_index < len(stacks):
                stack = stacks[target_index]
                y1, y2 = self._staff_y_bounds(part_id, staffs)

                # Context: include the previous measure's stack
                x1 = stack["left"]
                x2 = stack["right"]
                if target_index > 0:
                    x1 = stacks[target_index - 1]["left"]
                if target_index + 1 < len(stacks):
                    x2 = stacks[target_index + 1]["right"]
                context_bbox = (x1, y1, x2, y2)

                return MeasureLocation(
                    part_id=part_id,
                    measure=measure,
                    page=page,
                    system=system_idx,
                    stack_id=stack["id"],
                    staff_index=0 if part_id == "P1" else 1,
                    bbox=(stack["left"], y1, stack["right"], y2),
                    confidence=0.6,
                    context_bbox=context_bbox,
                    context_measures=[str(before), measure, str(before + 2)],
                )

        # Fallback: place after the last stack
        last_stack = stacks[-1]
        left = last_stack["right"]
        right = left + (last_stack["right"] - last_stack["left"])
        y1, y2 = self._staff_y_bounds(part_id, staffs)

        return MeasureLocation(
            part_id=part_id,
            measure=measure,
            page=page,
            system=system_idx,
            stack_id=-1,
            staff_index=0 if part_id == "P1" else 1,
            bbox=(left, y1, right, y2),
            confidence=0.4,
            context_bbox=None,
            context_measures=[str(before), measure, str(before + 2)],
        )

    def _infer_cross_page(self, part_id: str, measure: str, before_info: dict, before: int) -> MeasureLocation | None:
        """Infer missing measure at the end of before's page (before page break).

        If Audiveris has more stacks than MusicXML measures in the same system,
        the missing measure occupies one of the trailing stacks on this page.
        """
        page = before_info["page"]
        system_idx = before_info["system"]

        sheet = self.sheet_data.get(page)
        if not sheet or system_idx >= len(sheet):
            return None

        system = sheet[system_idx]
        stacks = system["stacks"]
        staffs = system["staffs"]

        if not stacks:
            return None

        # If Audiveris has more stacks than MusicXML measures in this system,
        # the missing measure occupies one of the trailing stacks.
        musicxml_measures_in_system = sum(
            1 for info in self.measure_map.get(part_id, {}).values()
            if info["page"] == page and info["system"] == system_idx and not info.get("inferred")
        )
        if len(stacks) > musicxml_measures_in_system:
            target_index = musicxml_measures_in_system
            if target_index < len(stacks):
                stack = stacks[target_index]
                y1, y2 = self._staff_y_bounds(part_id, staffs)

                # Context: use the missing measure's own stack as center,
                # extended to include the previous measure's stack
                x1 = stack["left"]
                x2 = stack["right"]
                if target_index > 0:
                    x1 = stacks[target_index - 1]["left"]
                if target_index + 1 < len(stacks):
                    x2 = stacks[target_index + 1]["right"]
                context_bbox = (x1, y1, x2, y2)

                return MeasureLocation(
                    part_id=part_id,
                    measure=measure,
                    page=page,
                    system=system_idx,
                    stack_id=stack["id"],
                    staff_index=0 if part_id == "P1" else 1,
                    bbox=(stack["left"], y1, stack["right"], y2),
                    confidence=0.6,
                    context_bbox=context_bbox,
                    context_measures=[str(before), measure, str(before + 2)],
                )

        # Fallback: place after the last stack
        last_stack = stacks[-1]
        left = last_stack["right"]
        right = left + (last_stack["right"] - last_stack["left"])
        y1, y2 = self._staff_y_bounds(part_id, staffs)

        return MeasureLocation(
            part_id=part_id,
            measure=measure,
            page=page,
            system=system_idx,
            stack_id=-1,
            staff_index=0 if part_id == "P1" else 1,
            bbox=(left, y1, right, y2),
            confidence=0.4,
            context_bbox=None,
            context_measures=[str(before), measure, str(before + 2)],
        )

    @staticmethod
    def _staff_y_bounds(part_id: str, staffs: list[dict]) -> tuple[int, int]:
        """Compute y bounds for the target staff."""
        if part_id == "P1":
            staff = staffs[0]
            interline = (staff["y_max"] - staff["y_min"]) / 4.0
            margin = interline * 3
            return int(staff["y_min"] - margin), int(staff["y_max"] + margin)
        else:
            staff = staffs[1]
            interline = (staff["y_max"] - staff["y_min"]) / 4.0
            margin = interline * 3
            y1 = int(staff["y_min"] - margin)
            y2 = int(staff["y_max"] + margin)
            if len(staffs) >= 3:
                lh_staff = staffs[2]
                y2 = max(y2, int(lh_staff["y_max"] + margin))
            return y1, y2


# ---------------------------------------------------------------------------
# Evidence cropper
# ---------------------------------------------------------------------------


class EvidenceCropper:
    """Generate context and target crops from PDF page images."""

    def __init__(self, rendered_dir: str | Path, output_dir: str | Path):
        self.rendered_dir = Path(rendered_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def crop(self, loc: MeasureLocation, scale: float = 2.0) -> dict:
        """Crop target and context images for a measure location."""
        result = {
            "part_id": loc.part_id,
            "measure": loc.measure,
            "page": loc.page,
            "system": loc.system,
            "stack_id": loc.stack_id,
            "confidence": loc.confidence,
            "bbox": list(loc.bbox),
            "context_bbox": list(loc.context_bbox) if loc.context_bbox else None,
            "context_measures": loc.context_measures,
        }

        page_img_path = self.rendered_dir / f"page-{loc.page:02d}.png"
        if not page_img_path.exists():
            result["error"] = f"Page image not found: {page_img_path}"
            return result

        try:
            img = Image.open(page_img_path)
        except Exception as e:
            result["error"] = f"Cannot open page image: {e}"
            return result

        pkg_name = f"{loc.part_id}-M{loc.measure}"
        pkg_dir = self.output_dir / pkg_name
        pkg_dir.mkdir(parents=True, exist_ok=True)

        # Target crop (single measure, high resolution)
        x1, y1, x2, y2 = loc.bbox
        target_crop = img.crop((x1, y1, x2, y2))
        target_path = pkg_dir / "target_crop.png"
        target_crop.save(target_path)
        result["target_crop"] = str(target_path)

        # Context crop (prev + target + next)
        if loc.context_bbox:
            cx1, cy1, cx2, cy2 = loc.context_bbox
            context_crop = img.crop((cx1, cy1, cx2, cy2))
            context_path = pkg_dir / "context_crop.png"
            context_crop.save(context_path)
            result["context_crop"] = str(context_path)

        # Save metadata
        meta_path = pkg_dir / "metadata.json"
        meta_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        return result


# ---------------------------------------------------------------------------
# CLI / standalone test
# ---------------------------------------------------------------------------


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--omr", required=True, help="Audiveris .omr file")
    parser.add_argument("--raw", required=True, help="Raw MusicXML")
    parser.add_argument("--rendered", required=True, help="Rendered PNG directory")
    parser.add_argument("--output", required=True, help="Output directory for crops")
    parser.add_argument("--part", required=True, help="Part ID (e.g. P1)")
    parser.add_argument("--measure", required=True, help="Measure number")
    args = parser.parse_args()

    locator = MeasureLocator(args.omr, args.raw, args.rendered)
    loc = locator.locate(args.part, args.measure)
    if loc is None:
        print(f"Cannot locate {args.part} M{args.measure}")
        return

    print(f"Located: page={loc.page}, system={loc.system}, stack={loc.stack_id}, bbox={loc.bbox}")
    print(f"Confidence: {loc.confidence}")

    cropper = EvidenceCropper(args.rendered, args.output)
    result = cropper.crop(loc)
    print(f"Saved to {result.get('target_crop', 'ERROR')}")


if __name__ == "__main__":
    main()
