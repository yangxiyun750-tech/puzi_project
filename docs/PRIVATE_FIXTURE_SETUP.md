# Optional Private Golden Fixture

The open-source ScoreRebuild baseline does not include or require a copyrighted score, private MusicXML file, MuseScore project, PDF, image, OMR project, or generated QA output.

Check the current state with:

```powershell
python -m score_rebuild private-fixture-status
```

An ordinary public installation should report:

```text
PRIVATE_FIXTURE_AVAILABLE = NO
[SKIPPED] Not configured. Set SCORE_REBUILD_PRIVATE_FIXTURE_MUSICXML to a private MusicXML file when authorized.
```

This is a successful skip, not an installation failure.

An authorized developer may configure a private MusicXML regression input outside the repository:

```powershell
$env:SCORE_REBUILD_PRIVATE_FIXTURE_MUSICXML = 'X:\private-fixtures\golden.musicxml'
$env:SCORE_REBUILD_PRIVATE_FIXTURE_OUTPUT_DIR = 'X:\private-fixtures\output'
python -m score_rebuild private-fixture-status
```

The output-directory variable is optional. Without it, developer-only round-trip output goes to an isolated directory under the system temporary directory.

Never commit the configured fixture or its PDF, MSCZ, MusicXML, MXL, OMR, PNG, or generated QA output. These environment variables are optional and are not part of the public doctor or synthetic smoke-test requirements.
