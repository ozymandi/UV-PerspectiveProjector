# Tasks

## 1. Test runner and timing test

- [x] 1.1 `tests/run_blender.py`: Blender path from `--blender`, `BLENDER`, or the newest installed `Blender X.Y` on Windows (clear error otherwise); verify locally that `python tests/run_blender.py -k smoke` finds Blender 5.3 with no argument
- [x] 1.2 `tests/run_blender.py`: `--zip PATH` installs a given zip instead of building, and `--ui {include,exclude,only}` filters the window tests; verify locally by running `--ui exclude` and `--ui only` (counts add up to the full suite) and `--zip` with a zip from `build/`
- [x] 1.3 `tests/core/test_detect.py`: scale the 10 s limit by `PP_TIME_FACTOR` (default 1); verify the core tests pass locally with and without the variable

## 2. Release helpers

- [x] 2.1 `tools/check_zips.py`: for each platform zip check manifest version, exactly its own wheel, no `__pycache__`/`.pyc`, `testzip`; non-zero exit on any failure; verify on `build/release-1.3.0` (passes) and on a zip with a wrong version (fails)
- [x] 2.2 `tools/release_notes.py`: print the "## Version notes (X.Y.Z)" section of `release/listing.md` for a given version, error if missing; verify for 1.3.0 and for a missing version

## 3. Workflows

- [ ] 3.1 `.github/workflows/ci.yml`: core tests on push / PR; Blender tests on PRs into `main` and `workflow_dispatch`, matrix Blender 4.2 LTS + 5.3 on ubuntu, cached Blender and wheels, `xvfb-run` with Mesa, background tests blocking and UI tests as a `continue-on-error` step, `PP_TIME_FACTOR=3`; verify with a manual run on a branch: core job green, both Blender jobs reach the end and their logs show every test file
- [ ] 3.2 `.github/workflows/release.yml`: on `v*` tags, tag/manifest check, wheels with PyPI digest check, split build, `tools/check_zips.py`, Blender tests on the Linux zip with `--zip`, draft release via `gh` with the four zips and `tools/release_notes.py` notes; verify by pushing a test tag (e.g. `v0.0.0-ci-test` on a branch with a matching manifest) and checking the draft release, then deleting the test tag and draft
- [ ] 3.3 Record what the first Blender 4.2 LTS run shows; if it fails for real reasons, list the failures in this change's notes and open a separate change for the fixes (do not fix the add-on here)

## 4. Docs

- [x] 4.1 README: CI section (what runs when) and the release steps (bump version + listing notes, tag, review and publish the draft); verify the steps match the workflows

## Workflow follow-up

- Archive the change after review. Consider making the UI test step blocking after several green runs, and macOS / Windows runners if needed.
