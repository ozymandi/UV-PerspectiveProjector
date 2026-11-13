"""Build the extension, install it into an isolated Blender user folder, run tests/blender.

Usage (system Python):
    python tests/run_blender.py [--blender PATH] [-k substring]

The isolated user folder (build/blender_user) keeps the developer's own Blender
preferences untouched. Each tests/blender/test_*.py file runs in a fresh
background Blender; a file passes when Blender exits with code 0. Files named
test_ui_*.py open a real Blender window (needed for undo and gizmos).
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
USER = BUILD / "blender_user"
DEFAULT_BLENDER = r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"


def run(cmd, env):
    return subprocess.run(cmd, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")


def build_and_install(blender, env, user):
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
    zips = sorted(BUILD.glob("perspective_projector-*windows*.zip")) or sorted(BUILD.glob("perspective_projector-*.zip"))
    if not zips:
        sys.exit("no extension zip produced")
    res = run([blender, "--factory-startup", "--command", "extension", "install-file",
               "-r", "user_default", "-e", str(zips[-1])], env)
    # 4.2 prints only "Preferences saved"; check the installed package on disk instead of the message
    installed = user / "extensions" / "user_default" / "perspective_projector" / "__init__.py"
    if res.returncode != 0 or not installed.is_file():
        sys.exit(f"install failed:\n{res.stdout}\n{res.stderr}")
    return zips[-1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--blender", default=os.environ.get("BLENDER", DEFAULT_BLENDER))
    parser.add_argument("-k", default="")
    parser.add_argument("--user", default=str(USER), help="isolated Blender user folder")
    args = parser.parse_args()

    env = dict(os.environ)
    user = Path(args.user)
    user.mkdir(parents=True, exist_ok=True)
    env["BLENDER_USER_RESOURCES"] = str(user)

    zip_path = build_and_install(args.blender, env, user)
    print(f"installed {zip_path.name}")

    failed = []
    tests = sorted((ROOT / "tests" / "blender").glob("test_*.py"))
    for test in tests:
        if args.k and args.k not in test.name:
            continue
        # test_ui_* need a window (undo, gizmos): run without --background; they exit via os._exit
        mode = ["--background"]
        if test.name.startswith("test_ui_"):
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
