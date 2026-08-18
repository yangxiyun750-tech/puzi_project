# Third-Party Libraries and Licenses

This file documents all third-party libraries used by the Score Engine project,
along with their licenses. This information is required for compliance,
enterprise licensing, and potential sale of the codebase.

---

## Runtime Dependencies

| Library | Version | License | Purpose |
|---|---|---|---|
| Pillow | 12.3.0 | HPND | Image processing for PDF crops and visual evidence |
| numpy | 2.5.2 | BSD-3-Clause | Numerical operations for image analysis (blur/skew) |
| pypdf | 6.16.0 | BSD-3-Clause | PDF text extraction and page counting |
| lxml | 6.1.1 | BSD-3-Clause | Fast XML parsing for MusicXML processing |

---

## Development / Tool Dependencies

| Tool | Version | License | Purpose |
|---|---|---|---|
| Audiveris | 5.11.0 | AGPL-3.0 | Optical Music Recognition (OMR) |
| MuseScore Studio | 4.7.4 | GPL-3.0 | Score rendering and MusicXML validation |
| Poppler | (system) | GPL-2.0 | PDF to PNG rendering (pdftoppm) |

---

## License Compatibility Notes

- **AGPL-3.0 (Audiveris):** If the Score Engine is distributed as a network
  service, the AGPL requires that the source code be made available to users.
  For enterprise licensing or sale, a commercial license or replacement OMR
  engine may be required.

- **GPL-3.0 (MuseScore):** MuseScore is used as an external CLI tool for
  validation and rendering. It is not linked into the Score Engine binary.
  The Score Engine itself does not need to be GPL, but users must have
  MuseScore installed separately.

- **GPL-2.0 (Poppler):** Poppler is used as an external CLI tool (pdftoppm).
  It is not linked into the Score Engine binary.

- **HPND / BSD-3-Clause:** These are permissive licenses and do not impose
  copyleft requirements.

---

## Recommendation for Commercial Use

For enterprise licensing or sale:
1. Consider replacing Audiveris with a commercial OMR solution, or
   obtain a commercial license from the Audiveris project.
2. MuseScore and Poppler can remain as external tool dependencies
   (users install them separately).
3. All Python runtime dependencies (Pillow, numpy, pypdf, lxml) are
   permissively licensed and safe for commercial use.

---

*Last updated: 2026-08-15*
