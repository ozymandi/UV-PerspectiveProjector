"""Print the release notes of one version from release/listing.md.

    python tools/release_notes.py 1.3.0

Prints the body of the "## Version notes (X.Y.Z)" section (up to the next "## " heading);
exits non-zero if the section is missing or empty, so a release cannot go out without notes.
"""

import re
import sys
from pathlib import Path

LISTING = Path(__file__).resolve().parent.parent / "release" / "listing.md"


def notes(text, version):
    m = re.search(rf"(?ms)^## Version notes \({re.escape(version)}\)\s*\n(.*?)(?=^## |\Z)", text)
    return m.group(1).strip() if m else None


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: release_notes.py X.Y.Z")
    version = sys.argv[1].lstrip("v")
    body = notes(LISTING.read_text(encoding="utf-8"), version)
    if not body:
        sys.exit(f"no '## Version notes ({version})' section in {LISTING}")
    print(body)


if __name__ == "__main__":
    main()
