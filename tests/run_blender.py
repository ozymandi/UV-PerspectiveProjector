"""Build the extension, install it into an isolated Blender user folder, run tests/blender.

Usage (system Python):
    python tests/run_blender.py [--blender PATH] [-k substring] [--zip PATH] [--ui include|exclude|only]

Blender: --blender, else the BLENDER environment variable, else (Windows) the newest
"Blender X.Y" under C:\\Program Files\\Blender Foundation.
--zip installs that extension zip instead of building one (the release workflow tests the
exact zip it uploads). --ui filters the window tests (test_ui_*) so CI can run them separately.

The isolated user folder (build/blender_user) keeps the developer's own Blender
preferences untouched. Each tests/blender/test_*.py file runs in a fresh
background Blender; a file passes when Blender exits with code 0. Files named
test_ui_*.py open a real Blender window (needed for undo and gizmos).
"""

import argparse
import os
import platform
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
USER = BUILD / "blender_user"
WINDOWS_BLENDER_DIR = Path(r"C:\Program Files\Blender Foundation")


def find_blender(explicit=None):
    """Blender executable: explicit path, then $BLENDER, then the newest installed one on Windows."""
    for candidate in (explicit, os.environ.get("BLENDER")):
        if candidate:
            return candidate
    if sys.platform == "win32" and WINDOWS_BLENDER_DIR.is_dir():
        found = []
        for d in WINDOWS_BLENDER_DIR.glob("Blender *"):
            m = re.fullmatch(r"Blender (\d+)\.(\d+)", d.name)
            exe = d / "blender.exe"
            if m and exe.is_file():
                found.append(((int(m[1]), int(m[2])), exe))
        if found:
            return str(max(found)[1])
    sys.exit("Blender not found: pass --blender PATH or set the BLENDER environment variable")


def host_platform():
    """Blender extension platform tag of this machine (as in the split zip names)."""
    machine = platform.machine().lower()
    arch = "arm64" if machine in ("arm64", "aarch64") else "x64"
    if sys.platform == "win32":
        return f"windows_{arch}"
    if sys.platform == "darwin":
        return f"macos_{arch}"
    return f"linux_{arch}"


def run(cmd, env):
    return subprocess.run(cmd, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")


def build(blender, env):
    BUILD.mkdir(exist_ok=True)
    for old in BUILD.glob("perspective_projector-*.zip"):
        old.unlink()
    cmd = [blender, "--factory-startup", "--command", "extension", "build",
           "--source-dir", str(ROOT / "perspective_projector"), "--output-dir", str(BUILD)]
    manifest = (ROOT / "perspective_projector" / "blender_manifest.toml").read_text(encoding="utf-8")
    if "\nplatforms" in manifest:
        cmd.append("--split-platforms")
    res = run(cmd, env)
    if res.returncode != 0:
        sys.exit(f"build failed:\n{res.stdout}\n{res.stderr}")
    zips = (sorted(BUILD.glob(f"perspective_projector-*{host_platform()}*.zip"))
            or sorted(BUILD.glob("perspective_projector-*.zip")))
    if not zips:
        sys.exit("no extension zip produced")
    return zips[-1]


def install(blender, env, user, zip_path):
    res = run([blender, "--factory-startup", "--command", "extension", "install-file",
               "-r", "user_default", "-e", str(zip_path)], env)
    # 4.2 prints only "Preferences saved"; check the installed package on disk instead of the message
    installed = user / "extensions" / "user_default" / "perspective_projector" / "__init__.py"
    if res.returncode != 0 or not installed.is_file():
        sys.exit(f"install failed:\n{res.stdout}\n{res.stderr}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--blender", default=None, help="Blender executable (default: $BLENDER or the newest installed)")
    parser.add_argument("-k", default="")
    parser.add_argument("--user", default=str(USER), help="isolated Blender user folder")
    parser.add_argument("--zip", default=None, help="install this extension zip instead of building one")
    parser.add_argument("--ui", choices=("include", "exclude", "only"), default="include",
                        help="window tests (test_ui_*): run them too, skip them, or run only them")
    args = parser.parse_args()
    args.blender = find_blender(args.blender)

    env = dict(os.environ)
    user = Path(args.user)
    user.mkdir(parents=True, exist_ok=True)
    env["BLENDER_USER_RESOURCES"] = str(user)

    zip_path = Path(args.zip) if args.zip else build(args.blender, env)
    if not zip_path.is_file():
        sys.exit(f"no such zip: {zip_path}")
    install(args.blender, env, user, zip_path)
    print(f"installed {zip_path.name} into {args.blender}")

    failed = []
    tests = sorted((ROOT / "tests" / "blender").glob("test_*.py"))
    for test in tests:
        if args.k and args.k not in test.name:
            continue
        is_ui = test.name.startswith("test_ui_")
        if (args.ui == "exclude" and is_ui) or (args.ui == "only" and not is_ui):
            continue
        # test_ui_* need a window (undo, gizmos): run without --background; they exit via os._exit
        mode = ["--background"]
        if is_ui:
            mode = ["--enable-event-simulate"] if "drag" in test.name else []
        res = run([args.blender, *mode, "--python-exit-code", "1", "--python", str(test)], env)
        ok = res.returncode == 0
        print(f"{'PASS' if ok else 'FAIL'} {test.name}")
        if not ok:
            failed.append(test.name)
            print(res.stdout[-4000:])
            print(res.stderr[-4000:])
    if failed:
        sys.exit(f"{len(failed)} failed: {', '.join(failed)}")
    print("all passed")


if __name__ == "__main__":
    main()
