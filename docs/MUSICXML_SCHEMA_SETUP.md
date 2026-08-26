# MusicXML 4.0 Schema Setup

ScoreRebuild validates MusicXML structurally with the MusicXML 4.0 XSD. XSD validity is not musical accuracy.

## Resolution chosen for V0.1 candidate

The schema is **not bundled or committed**. The five existing untracked local files were compared with the raw bytes served from the pinned official v4.0 commit and all five matched byte-for-byte. A Windows Git checkout may normalize line endings, so release hashes are deliberately calculated from the official raw download bytes, not from an `autocrlf` working tree.

Instead, the repository pins the W3C Music Notation Community Group repository:

- repository: `https://github.com/w3c-cg/musicxml.git`
- tag: `v4.0`
- commit: `799e2defb2ece0ae7bafe08dcbcac25b2c631d53`
- publication: `https://www.w3.org/2021/06/musicxml40/`
- governing notice in the schema: W3C Community Final Specification Agreement (FSA)
- human-readable FSA summary: `https://www.w3.org/community/about/process/fsa-deed/`

MusicXML 4.0 is a Final Community Group Report, not a W3C Standard. Because the FSA is not a conventional software license and the repository tag contains no standalone LICENSE file, V0.1 takes the conservative approach: download the files from the pinned official revision and verify them locally instead of redistributing them.

## Install

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m score_rebuild schema-install
```

If a different schema directory is required:

```powershell
$env:MUSICXML_SCHEMA_DIR = Join-Path $env:LOCALAPPDATA 'ScoreRebuild\musicxml_4_0\schema'
.\.venv\Scripts\python.exe -m score_rebuild schema-install
```

The installer uses only the Python standard library. It downloads from `raw.githubusercontent.com/w3c-cg/musicxml` at the pinned commit, verifies every SHA-256 value, and writes a local `SOURCE.json` record. Runtime validation performs no network access.

## Pinned files

| File | SHA-256 |
|---|---|
| `musicxml.xsd` | `bfe37ed25a9ec00e6f2591d53df260b84efe12aed209ba3ac0a76f9287665a99` |
| `xlink.xsd` | `6e601f8eeb41618b50e4c7f944dff754e57ea43b602755470dda24c9c2f6df92` |
| `xml.xsd` | `616a3077df5cfc954ac74a75abe9697b95eef7a85dbe09367d995a483e840eb5` |
| `container.xsd` | `deddcc2f51e856de21397bbe25e2cf304ca9e3253b0d25dcc6349c390bc22fa6` |
| `catalog.xml` | `c65df54cbf1c6bd73a335d47c0ec292c4c1d7ecca20dbb6e36388bb169c71245` |

## Verify only

```powershell
.\.venv\Scripts\python.exe -m score_rebuild schema-install --verify-only
```

The environment doctor performs the same hash check.

## Existing files

The installer accepts existing files only when every pinned SHA-256 value matches. It refuses to overwrite mismatched files by default. Back up or remove mismatched files after review, then rerun. `--force` is available only when the user deliberately accepts replacement by the pinned official revision:

```powershell
.\.venv\Scripts\python.exe -m score_rebuild schema-install --force
```

## Failure behavior

On a clean clone, schema validation must not silently download, skip XSD validation, or fall back to network imports. The validator/doctor fails with the missing directory/file names and points to this setup command. This is intentional.
