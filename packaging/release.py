"""Cut a release: bump the version, commit, tag. Never pushes (you do that last, on purpose).

    python packaging/release.py patch|minor|major|X.Y.Z[-pre.N] [--dry-run]

Single source of truth is isla/__init__.py; the Release workflow refuses a tag that disagrees with it.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INIT = ROOT / "isla" / "__init__.py"
NOTES = ROOT / "docs" / "release-notes"
CHANGELOG = ROOT / "CHANGELOG.md"
SEMVER = re.compile(r"^\d+\.\d+\.\d+(-[0-9A-Za-z.]+)?$")


def next_version(current: str, spec: str) -> str:
    """Resolve 'patch' / 'minor' / 'major' or an explicit X.Y.Z[-pre] against the current version."""
    if SEMVER.match(spec):
        return spec
    major, minor, patch = (int(p) for p in current.split("-")[0].split("."))
    if spec == "major":
        return f"{major + 1}.0.0"
    if spec == "minor":
        return f"{major}.{minor + 1}.0"
    if spec == "patch":
        return f"{major}.{minor}.{patch + 1}"
    raise ValueError(f"expected patch|minor|major|X.Y.Z, got {spec!r}")


def current_version() -> str:
    m = re.search(r'__version__ = "(.+)"', INIT.read_text(encoding="utf-8"))
    if not m:
        raise SystemExit("no __version__ in isla/__init__.py")
    return m.group(1)


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()


def main(argv: list[str]) -> int:
    dry = "--dry-run" in argv
    args = [a for a in argv if not a.startswith("--")]
    if len(args) != 1:
        print(__doc__)
        return 2
    old = current_version()
    new = next_version(old, args[0])
    tag = f"v{new}"

    problems = []
    if git("status", "--porcelain", "--untracked-files=no"):
        problems.append("working tree has uncommitted changes")
    if git("rev-parse", "--abbrev-ref", "HEAD") != "main":
        problems.append("not on main")
    if git("tag", "-l", tag):
        problems.append(f"tag {tag} already exists")
    if not (NOTES / f"{tag}.md").exists():
        print(f"note: docs/release-notes/{tag}.md missing; the release will use the generic description")
    if problems and not dry:
        print("Cannot release: " + "; ".join(problems))
        return 1

    print(f"{old} -> {new} (tag {tag}){'  [dry run]' if dry else ''}")
    if dry:
        for p in problems:
            print(f"  would be blocked: {p}")
        return 0

    tests = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=ROOT)
    if tests.returncode:
        print("Tests failed; nothing was changed.")
        return 1

    INIT.write_text(re.sub(r'__version__ = ".+"', f'__version__ = "{new}"', INIT.read_text(encoding="utf-8")),
                    encoding="utf-8")
    if CHANGELOG.exists():
        text = CHANGELOG.read_text(encoding="utf-8")
        from datetime import date
        text = text.replace("## [Unreleased]", f"## [Unreleased]\n\n## [{new}] - {date.today().isoformat()}", 1)
        CHANGELOG.write_text(text, encoding="utf-8")
    git("add", "-A", "isla/__init__.py", "CHANGELOG.md")
    git("commit", "-m", f"Release {new}")
    git("tag", "-a", tag, "-m", f"Isla {new}")
    print(f"Done. Review with 'git show {tag}', then publish:\n  git push origin main {tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
