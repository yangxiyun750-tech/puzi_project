# Windows Toolchain Bootstrap

Use this reference only when the user asks the Agent to prepare, download, install, or repair the ScoreRebuild environment. It does not change score reconstruction behavior.

## Security contract

- `Plan` and `Verify` are read-only except when `Verify -WriteLocalConfig` is explicitly requested.
- `Download` requires `-ApproveDownload` after the user approves network access and writes.
- `Install` requires `-ApproveInstall`; Windows may separately request elevation.
- Download only a filename and URL listed in the pinned manifest. Never substitute a search result, proxy site, forum, or cloud-drive link.
- Every package must have a fixed SHA-256. A mismatch is a security failure: delete the partial file and stop.
- Official fallback is disabled by default and must be explicitly enabled.
- `pending_mirror` is a deliberate blocker, not permission to improvise a source.

The canonical manifest is `assets/windows-toolchain-manifest.json`. It records provenance and license/source links separately from executable packages. Do not mark a package `ready` until its exact binary, license obligations, source availability, filename, direct domestic URL, and SHA-256 have been reviewed.

## Agent interaction

Start with:

```powershell
& ".agents\skills\focused-score-rebuild\scripts\bootstrap_tools.ps1" -Action Plan
```

Summarize found, version-mismatched, and `PENDING_MIRROR` tools. Before downloading, show the user each package version, source host, filename, hash, size when known, license, destination, and whether installation needs elevation. Ask one explicit approval question.

After approval:

```powershell
& ".agents\skills\focused-score-rebuild\scripts\bootstrap_tools.ps1" -Action Download -ApproveDownload
& ".agents\skills\focused-score-rebuild\scripts\bootstrap_tools.ps1" -Action Install -ApproveInstall
& ".agents\skills\focused-score-rebuild\scripts\bootstrap_tools.ps1" -Action Verify -WriteLocalConfig
```

Then create the Python virtual environment, install `requirements.txt` from the documented mainland mirror or wheelhouse, install the offline MusicXML schema, and run `score-rebuild.cmd doctor`, `capability-doctor`, and `smoke-test`.

## Offline bundle

The safest no-VPN delivery is a separately distributed directory containing the exact filenames pinned in the manifest:

```powershell
& ".agents\skills\focused-score-rebuild\scripts\bootstrap_tools.ps1" -Action Download -OfflineBundle D:\ScoreRebuildOffline -ApproveDownload
```

The script copies only matching filenames and still verifies SHA-256 before accepting them. The offline directory may contain other files; they are ignored.

## Local path record

Successful install/verification can write `.score-rebuild/toolchain-paths.json`. This file is machine-specific and ignored by Git. The environment doctor may use these paths after explicit environment variables and before searching `PATH` and common locations.

## Stop conditions

Stop and report the exact tool when:

- a domestic mirror or fixed hash is not configured;
- a hash differs;
- the source license/build provenance is unresolved;
- an existing portable install target would be overwritten;
- elevation is required but unavailable;
- the executable cannot start or its version does not match the manifest.

Do not claim automatic mainland installation is ready until all four production manifest entries are `ready` and the complete flow passes on a separate clean mainland Windows machine without VPN or proxy.
