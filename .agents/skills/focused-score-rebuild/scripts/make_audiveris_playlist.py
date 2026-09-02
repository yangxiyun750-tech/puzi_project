#!/usr/bin/env python3
"""Create an ordered Audiveris compound-book playlist from page images."""

from __future__ import annotations

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def natural_key(path: Path) -> list[object]:
    return [
        int(token) if token.isdigit() else token.casefold()
        for token in re.split(r"(\d+)", path.name)
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create an Audiveris playlist from ordered page images."
    )
    parser.add_argument("input_dir", type=Path, help="Directory containing page images")
    parser.add_argument(
        "--pattern", default="*.png", help="Image glob within input_dir (default: *.png)"
    )
    parser.add_argument("--output", required=True, type=Path, help="Playlist XML to write")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing output file")
    return parser.parse_args()


def build_playlist(input_dir: Path, pattern: str) -> tuple[ET.ElementTree, list[Path]]:
    if not input_dir.is_dir():
        raise ValueError(f"Input directory does not exist: {input_dir}")

    pages = sorted(
        (page.resolve() for page in input_dir.glob(pattern) if page.is_file()),
        key=natural_key,
    )
    if not pages:
        raise ValueError(f"No files matched {pattern!r} in {input_dir}")

    root = ET.Element("play-list")
    for page in pages:
        excerpt = ET.SubElement(root, "excerpt")
        ET.SubElement(excerpt, "path").text = str(page)
        ET.SubElement(excerpt, "sheets-selection").text = "1"

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    return tree, pages


def main() -> int:
    args = parse_args()
    output = args.output.resolve()
    if output.exists() and not args.force:
        print(f"Refusing to overwrite existing playlist: {output}", file=sys.stderr)
        return 2

    try:
        tree, pages = build_playlist(args.input_dir.resolve(), args.pattern)
        output.parent.mkdir(parents=True, exist_ok=True)
        tree.write(output, encoding="utf-8", xml_declaration=True)
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print(f"Wrote {output} with {len(pages)} pages")
    for index, page in enumerate(pages, start=1):
        print(f"{index:04d}  {page}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
