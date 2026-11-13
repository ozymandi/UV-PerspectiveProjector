"""Download the OpenCV wheels the extension bundles (they are not stored in git).

    python tools/fetch_wheels.py

Puts the four pinned opencv-python-headless wheels listed in perspective_projector/blender_manifest.toml
into perspective_projector/wheels/. pip checks each file's hash against PyPI.
OpenCV 4.11.0.86 is pinned because 4.12+ require numpy 2 and Blender 4.2 ships numpy 1.x.
"""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "perspective_projector"
WHEELS = PKG / "wheels"


def main():
    manifest = (PKG / "blender_manifest.toml").read_text(encoding="utf-8")
    names = re.findall(r'"\./wheels/([^"]+\.whl)"', manifest)
    if not names:
        sys.exit("no wheels listed in blender_manifest.toml")
    WHEELS.mkdir(exist_ok=True)
    for name in names:
        if (WHEELS / name).is_file():
            print(f"have  {name}")
            continue
        m = re.match(r"(?P<dist>[^-]+)-(?P<ver>[^-]+)-[^-]+-[^-]+-(?P<plat>.+)\.whl$", name)
        if not m:
            sys.exit(f"cannot parse wheel name {name}")
        dist = m["dist"].replace("_", "-")
        # a wheel tag like manylinux_2_17_x86_64.manylinux2014_x86_64 lists several platforms; any one works
        platform = m["plat"].split(".")[0]
        cmd = [sys.executable, "-m", "pip", "download", f"{dist}=={m['ver']}", "--no-deps",
               "--only-binary=:all:", "--platform", platform, "--python-version", "3.11",
               "-d", str(WHEELS), "-q"]
        subprocess.run(cmd, check=True)
        if not (WHEELS / name).is_file():
            sys.exit(f"pip did not produce {name}")
        print(f"got   {name}")


if __name__ == "__main__":
    main()
