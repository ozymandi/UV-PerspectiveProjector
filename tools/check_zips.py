"""Check the platform zips of a release build before they are published.

    python tools/check_zips.py build/release-X.Y.Z [--version X.Y.Z]

For every perspective_projector-*.zip in the folder: the archive is intact, its manifest has the
expected version (default: the version in perspective_projector/blender_manifest.toml), it holds
exactly one wheel and that wheel is for the zip's own platform, and it contains no __pycache__ or
.pyc files. Exits non-zero on the first folder with any problem, after listing all of them.
"""

import argparse
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLATFORMS = ("windows_x64", "macos_arm64", "macos_x64", "linux_x64")
WHEEL_TAGS = {  # zip platform -> pattern the wheel's platform tag must match
    "windows_x64": r"win_amd64",
    "macos_arm64": r"macosx_\d+_\d+_arm64",
    "macos_x64": r"macosx_\d+_\d+_x86_64",
    "linux_x64": r"manylinux\w*_x86_64",
}


def manifest_version(text):
    m = re.search(r'(?m)^version\s*=\s*"([^"]+)"', text)
    return m.group(1) if m else None


def check_zip(path, version):
    problems = []
    m = re.fullmatch(r"perspective_projector-(.+)-(windows_x64|macos_arm64|macos_x64|linux_x64)\.zip", path.name)
    if not m:
        return [f"{path.name}: unexpected file name"]
    name_version, plat = m.group(1), m.group(2)
    if name_version != version:
        problems.append(f"{path.name}: file name version {name_version} != {version}")
    try:
        zf = zipfile.ZipFile(path)
    except zipfile.BadZipFile as exc:
        return problems + [f"{path.name}: not a zip ({exc})"]
    with zf:
        bad = zf.testzip()
        if bad is not None:
            problems.append(f"{path.name}: corrupt member {bad}")
        names = zf.namelist()
        try:
            got = manifest_version(zf.read("blender_manifest.toml").decode("utf-8"))
        except KeyError:
            got = None
        if got != version:
            problems.append(f"{path.name}: manifest version {got} != {version}")
        wheels = [n for n in names if n.endswith(".whl")]
        if len(wheels) != 1:
            problems.append(f"{path.name}: {len(wheels)} wheels, expected 1: {wheels}")
        elif not re.search(WHEEL_TAGS[plat], wheels[0]):
            problems.append(f"{path.name}: wheel {wheels[0]} is not for {plat}")
        junk = [n for n in names if "__pycache__" in n or n.endswith(".pyc")]
        if junk:
            problems.append(f"{path.name}: {len(junk)} __pycache__/.pyc entries")
    return problems


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("folder")
    parser.add_argument("--version", default=None)
    args = parser.parse_args()
    version = args.version or manifest_version(
        (ROOT / "perspective_projector" / "blender_manifest.toml").read_text(encoding="utf-8"))
    folder = Path(args.folder)
    zips = sorted(folder.glob("perspective_projector-*.zip"))
    problems = []
    found = {p.name.rsplit("-", 1)[-1][:-4] for p in zips}
    for plat in PLATFORMS:
        if plat not in found:
            problems.append(f"missing zip for {plat}")
    for z in zips:
        issues = check_zip(z, version)
        print(f"{'FAIL' if issues else 'ok  '} {z.name} ({z.stat().st_size} bytes)")
        problems += issues
    if problems:
        print("\n".join(problems), file=sys.stderr)
        sys.exit(1)
    print(f"all {len(zips)} zips ok for version {version}")


if __name__ == "__main__":
    main()
