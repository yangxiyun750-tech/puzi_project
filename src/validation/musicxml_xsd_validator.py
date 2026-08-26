"""MusicXML 4.0 XSD validation gate.

Validates MusicXML documents against the official W3C MusicXML 4.0 XSD,
using a locally pinned copy of the schema under
``third_party/musicxml_4_0/schema/``.  No network access is performed at
runtime.

This gate is designed to run on three kinds of inputs (today only (1) is
wired up):

1. raw OMR provider output
2. normalized output (Phase 3A+)
3. Score Engine modified output (Phase 3B+)

IMPORTANT: XSD validity is a *structural* property, NOT musical accuracy.
A document can be schema-valid and musically wrong.  Never surface
``xsd_valid`` as an accuracy metric.
"""
from __future__ import annotations

import os
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from lxml import etree

_DEFAULT_SCHEMA_DIR = Path(__file__).resolve().parent.parent.parent / "third_party" / "musicxml_4_0" / "schema"
SCHEMA_DIR = Path(os.environ.get("MUSICXML_SCHEMA_DIR", str(_DEFAULT_SCHEMA_DIR))).expanduser().resolve()
SCHEMA_VERSION = "4.0"

# URIs that must resolve to the local pinned schema copy.
_LOCAL_URI_PREFIXES = (
    "http://www.musicxml.org/xsd/",
    "https://www.musicxml.org/xsd/",
)
_LOCAL_XSD_NAMES = {"musicxml.xsd", "xlink.xsd", "xml.xsd", "container.xsd", "opus.xsd", "sounds.xsd"}


@dataclass
class ValidationError:
    """A single validation issue with source location when available."""

    line: Optional[int]
    column: Optional[int]
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {"line": self.line, "column": self.column, "message": self.message}


@dataclass
class MusicXMLValidationResult:
    """Unified result of the MusicXML 4.0 XSD validation gate."""

    xml_well_formed: bool
    xsd_valid: bool
    schema_version: str = SCHEMA_VERSION
    errors: list[ValidationError] = field(default_factory=list)
    document_path: str | None = None
    document_format: str | None = None  # "musicxml" or "mxl"

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_path": self.document_path,
            "document_format": self.document_format,
            "xml_well_formed": self.xml_well_formed,
            "xsd_valid": self.xsd_valid,
            "schema_version": self.schema_version,
            "errors": [e.to_dict() for e in self.errors],
        }


class _LocalSchemaResolver(etree.Resolver):
    """Resolve remote MusicXML schema URIs against the local pinned copy."""

    def resolve(self, url: str, pubid: str | None, context: Any):  # noqa: D102
        for prefix in _LOCAL_URI_PREFIXES:
            if url.startswith(prefix):
                name = url[len(prefix):]
                if name in _LOCAL_XSD_NAMES:
                    local_path = SCHEMA_DIR / name
                    if local_path.exists():
                        return self.resolve_filename(str(local_path), context)
        # Block anything else from hitting the network: return empty doc.
        return self.resolve_string("<?xml version='1.0'?><xs:schema xmlns:xs='http://www.w3.org/2001/XMLSchema'/>", context)


def _log_to_errors(error_log) -> list[ValidationError]:
    errors: list[ValidationError] = []
    for entry in error_log:
        errors.append(
            ValidationError(
                line=getattr(entry, "line", None),
                column=getattr(entry, "column", None),
                message=str(entry.message),
            )
        )
    return errors


class MusicXML4Validator:
    """Validates MusicXML text/bytes or .mxl containers against XSD 4.0.

    The schema is compiled once from the local pinned copy.  ``xs:import``
    schemaLocations pointing at ``http://www.musicxml.org/xsd/*.xsd`` are
    rewritten to local relative paths before compilation so startup never
    requires network access.
    """

    def __init__(self, schema_dir: Path | None = None) -> None:
        self.schema_dir = Path(schema_dir) if schema_dir else SCHEMA_DIR
        required_files = ("musicxml.xsd", "xlink.xsd", "xml.xsd")
        missing_files = [name for name in required_files if not (self.schema_dir / name).is_file()]
        if missing_files:
            missing = ", ".join(missing_files)
            raise FileNotFoundError(
                f"MusicXML 4.0 schema unavailable at {self.schema_dir}; missing: {missing}. "
                "Run `python -m score_rebuild schema-install` or set MUSICXML_SCHEMA_DIR. "
                "See docs/MUSICXML_SCHEMA_SETUP.md."
            )

        schema_text = (self.schema_dir / "musicxml.xsd").read_text(encoding="utf-8")
        for name in _LOCAL_XSD_NAMES:
            for prefix in _LOCAL_URI_PREFIXES:
                schema_text = schema_text.replace(f"{prefix}{name}", name)
        parser = etree.XMLParser(no_network=True)
        schema_doc = etree.fromstring(
            schema_text.encode("utf-8"),
            parser,
            base_url=str(self.schema_dir / "musicxml.xsd"),
        )
        self._schema = etree.XMLSchema(etree.ElementTree(schema_doc))

    @staticmethod
    def _extract_from_mxl(path: Path) -> tuple[bytes, str | None]:
        """Return (document_bytes, rootfile_name) from an .mxl container."""
        with zipfile.ZipFile(path, "r") as zf:
            container = zf.read("META-INF/container.xml").decode("utf-8")
            match = re.search(r'<rootfile[^>]*full-path="([^"]+)"', container)
            if not match:
                raise ValueError("Cannot find rootfile in MXL container")
            rootfile = match.group(1)
            return zf.read(rootfile), rootfile

    def validate_bytes(
        self,
        xml_bytes: bytes,
        document_path: str | None = None,
        document_format: str = "musicxml",
    ) -> MusicXMLValidationResult:
        """Validate raw MusicXML document bytes."""
        result = MusicXMLValidationResult(
            xml_well_formed=False,
            xsd_valid=False,
            document_path=document_path,
            document_format=document_format,
        )

        parser = etree.XMLParser(
            recover=False,
            no_network=True,
            resolve_entities=False,
            load_dtd=False,
            huge_tree=True,
        )
        parser.resolvers.add(_LocalSchemaResolver())

        try:
            tree = etree.fromstring(xml_bytes, parser)
        except etree.XMLSyntaxError as exc:
            result.xml_well_formed = False
            result.errors = _log_to_errors(exc.error_log)
            return result

        result.xml_well_formed = True

        root = tree.getroottree()
        valid = self._schema.validate(root)
        result.xsd_valid = bool(valid)
        if not valid:
            result.errors = _log_to_errors(self._schema.error_log)

        return result

    def validate_file(self, path: str | Path) -> MusicXMLValidationResult:
        """Validate a .musicxml / .xml / .mxl file on disk."""
        path = Path(path)
        if path.suffix.lower() == ".mxl":
            xml_bytes, rootfile = self._extract_from_mxl(path)
            return self.validate_bytes(
                xml_bytes,
                document_path=f"{path}::{rootfile}",
                document_format="mxl",
            )
        return self.validate_bytes(
            path.read_bytes(),
            document_path=str(path),
            document_format="musicxml",
        )


def validate_musicxml_file(path: str | Path, schema_dir: Path | None = None) -> dict[str, Any]:
    """Convenience function: validate one file and return a plain dict."""
    return MusicXML4Validator(schema_dir).validate_file(path).to_dict()
