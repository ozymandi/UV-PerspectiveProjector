# Design

## Context

See proposal.md for motivation. What exists:

- `tests/run_blender.py` builds the extension with Blender, installs it into an isolated user folder (`BLENDER_USER_RESOURCES`), runs each `tests/blender/test_*.py` in its own Blender process; `test_ui_*` files run with a window, and files with `drag` in the name also get `--enable-event-simulate`. It already accepts `--blender`, but `DEFAULT_BLENDER` is a hard-coded Windows path to Blender 5.2.
- `tools/fetch_wheels.py` downloads the four pinned `opencv-python-headless` 4.11.0.86 wheels with pip (pip verifies hashes against PyPI); the wheels are not in git.
- The manual release recipe used for 1.1.0 to 1.3.0: fetch wheels and compare SHA-256 with the PyPI JSON API, `blender --command extension build --split-platforms`, check each zip (manifest version, only its own wheel, no `__pycache__`, `testzip`), run the full Blender tests on the Windows zip, `gh release create` with the notes written from `release/listing.md`.
- `tests/core/test_detect.py` asserts detection finishes in under 10 s.

## Goals / Non-Goals

**Goals:**
- Core tests on every push / PR; Blender tests on Blender 4.2 LTS and 5.3 on Linux for PRs into `main` and on demand.
- A tag-driven release that reproduces the manual recipe and ends in a draft release.

**Non-Goals:**
- macOS and Windows runners (later, if Linux results justify the extra minutes).
- Publishing to extensions.blender.org.
- Changing the add-on.

## Decisions

### 1. Blender from download.blender.org, cached per version
A matrix over exact versions (the newest 4.2 LTS patch and 5.3.x, pinned in the workflow) downloads `blender-<ver>-linux-x64.tar.xz` from `https://download.blender.org/release/Blender<major.minor>/` and caches the unpacked folder with `actions/cache`, key = version. Alternative considered: a Blender snap / apt package; rejected because neither offers exact pinned LTS versions on the runner image.

### 2. Rendering and UI tests under a virtual display with Mesa
EEVEE needs OpenGL 4.3; GitHub's Linux runners have no GPU, so Mesa's llvmpipe (software OpenGL 4.5) provides it. Every Blender test step runs under `xvfb-run` with Mesa installed, which also gives the `test_ui_*` tests a window. UI tests (window, simulated mouse, undo) are the most likely to be flaky in CI, so they run as a separate step with `continue-on-error: true` until a few runs show them stable; the background tests are blocking from day one.

### 3. Test runner changes
- Blender path: `--blender`, else the `BLENDER` environment variable, else the newest `Blender X.Y` folder under `C:\Program Files\Blender Foundation` on Windows; a clear error if none is found.
- `--zip PATH`: install this already built zip instead of building (the release workflow tests exactly the zip it uploads).
- `--ui {include,exclude,only}` (default include) so CI can split background and window tests into separate steps.

### 4. Timing factor
`test_detect.py` multiplies its 10 s limit by `float(os.environ.get("PP_TIME_FACTOR", "1"))`; CI sets 3. The test still catches an order-of-magnitude regression without failing on a loaded or slower machine.

### 5. Wheels cached by manifest hash
`tools/fetch_wheels.py` runs in both workflows; `perspective_projector/wheels` is cached with key `hashFiles('perspective_projector/blender_manifest.toml')`, so a manifest change (new OpenCV pin) refetches. pip checks hashes on download; the release workflow additionally compares each file with the PyPI JSON digest, as in the manual recipe.

### 6. Release workflow ends in a draft
On a `v*` tag: fail fast unless `v` + manifest `version` equals the tag; fetch and verify wheels; build; check zips with a new `tools/check_zips.py` (the checks from the manual recipe); run the Blender tests on 5.3 with `--zip` pointing at the Linux zip; extract the notes for this version from `release/listing.md` ("## Version notes (X.Y.Z)" section) with a new `tools/release_notes.py`; `gh release create --draft` with the four zips (permission `contents: write`, `GITHUB_TOKEN`). The user reviews and publishes. Alternative considered: publish directly; rejected to keep the last outward step a human decision, as it is today.

## Risks / Trade-offs

- [llvmpipe EEVEE renders are slow; the full Blender suite may take 15-30 min per version] -> PR-to-main and manual triggers only; per-job timeout 60 min; renders already use 25 % resolution in tests.
- [Blender 4.2 ships numpy 1.26; never run so far] -> that is the point of the matrix; failures there are real findings, fixed in their own changes.
- [download.blender.org outage or moved file] -> cache hit keeps working; the URL pattern lives in one place in the workflow.
- [UI tests flaky under xvfb] -> non-blocking step at first; make blocking once stable.
- [Draft releases pile up if a tag is pushed twice] -> the workflow fails if a release for the tag already exists.
