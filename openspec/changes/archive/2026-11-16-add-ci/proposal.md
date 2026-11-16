# Proposal

## Why

The repository has no CI. Every check so far ran on one Windows laptop with Blender 5.3: Blender 4.2 LTS (the declared minimum) and Linux were never run, and a timing test failed only because the laptop was busy. Releases are built by a manual recipe (fetch and hash-check wheels, split-platform build, zip checks, full Blender test run, `gh release create`) that was repeated four times in one day for 1.1.0 to 1.3.0. Both are exactly what CI is for.

## What Changes

- **CI workflow** (`.github/workflows/ci.yml`):
  - every push and pull request: core tests (`python -m pytest tests/core`) on Linux;
  - pull requests into `main` and manual runs: Blender tests (`tests/run_blender.py`) on Linux against Blender 4.2 LTS and 5.3, with the OpenCV wheels fetched and cached; window-based UI tests run under a virtual display as a separate, initially non-blocking step.
- **Release workflow** (`.github/workflows/release.yml`) on a `v*` tag:
  - stops unless the tag equals the manifest version;
  - fetches the four wheels and checks their SHA-256 against PyPI;
  - builds the four platform zips, checks each one (version, only its own wheel, no `__pycache__`, intact archive);
  - runs the Blender tests on the built Linux zip;
  - creates a **draft** GitHub release with the four zips and the notes from `release/listing.md`; publishing stays a manual click.
- **Test runner portability**: `tests/run_blender.py` takes the Blender path from `--blender` or the `BLENDER` variable instead of a hard-coded Windows path to 5.2, and can test an already built zip.
- **Timing test**: the 10 s limit in `tests/core/test_detect.py` is scaled by an environment factor so shared CI runners do not fail it; locally it stays 10 s.
- README: a short CI / release section.

## Capabilities

### New Capabilities

### Modified Capabilities

No add-on behaviour changes; this change only adds tooling, so it carries no spec deltas (`skip_specs: true`).

## Impact

- New: `.github/workflows/ci.yml`, `.github/workflows/release.yml`, possibly a small helper script under `tools/` for the zip checks and release notes extraction.
- Changed: `tests/run_blender.py` (Blender path, testing a given zip), `tests/core/test_detect.py` (timing factor), README.
- GitHub Actions minutes: Linux only; Blender downloads cached per version.
- No change to the add-on code or its install.
