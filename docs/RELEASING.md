# Making a release

A release is a version of Isla (a git tag like `v0.1.0`) with `Isla.exe` attached so anyone can download and run it.
The normal way is **automatic**: push a tag and GitHub Actions builds the exe and publishes the release.

## Before you start (once)

- The repo is `MszBen/Isla-Dynamic-Island` on GitHub and your local `origin` points at it.
- In the repo on GitHub: **Settings → Actions → General → Workflow permissions** should allow Actions to run
  (the workflow asks for `contents: write` itself, which is what lets it create releases).

## Each release

1. **Pick a version** following [semver](https://semver.org): `0.1.0` for the first, `0.1.1` for fixes, `0.2.0` for new features.
2. **Note what changed** under `## [Unreleased]` in `CHANGELOG.md`, and (optionally) write `docs/release-notes/vX.Y.Z.md`, the text shown on the GitHub release.
3. **Check it works**: `python -m pytest`, then `powershell -ExecutionPolicy Bypass -File packaging\build.ps1` and click around `dist\Isla.exe`.
4. **Cut it**: this runs the tests, bumps `isla/__init__.py` (the single source of truth), stamps the changelog, commits and creates an annotated tag. It refuses on a dirty tree or off `main`, and never pushes.
   ```bash
   python packaging/release.py minor --dry-run   # preview: patch | minor | major | X.Y.Z[-pre.N]
   python packaging/release.py minor
   git push origin main vX.Y.Z                   # the command the script prints; this starts the build
   ```
5. **Watch it build**: GitHub → **Actions → Release**. After about 5-8 minutes the run finishes green.
6. **Check the release**: GitHub → **Releases**. You'll see `v0.1.0` with `Isla.exe` and `Isla.exe.sha256` attached, and
   notes generated from your commits. Edit the notes if you want to highlight things, then you're done.

The README's **Download** button always points at `releases/latest`, so it updates itself.

> The workflow refuses to publish if the tag doesn't match `__version__`. If that happens, fix the version, delete the
> tag (`git tag -d v0.1.0 && git push origin :refs/tags/v0.1.0`) and tag again.

## Doing it by hand instead

If you don't want to use Actions:

1. Build locally: `powershell -ExecutionPolicy Bypass -File packaging\build.ps1` gives `dist\Isla.exe` (about 75 MB).
2. On GitHub open **Releases → Draft a new release**.
3. **Choose a tag**: type `v0.1.0` and pick *Create new tag on publish*.
4. Give it a title (`Isla 0.1.0`), click **Generate release notes**.
5. Drag `dist\Isla.exe` into the **Attach binaries** box.
6. Press **Publish release**.

Or with the GitHub CLI: `gh release create v0.1.0 dist\Isla.exe --title "Isla 0.1.0" --generate-notes`.

## Pre-releases

Tag with a suffix, e.g. `v0.2.0-beta.1`, then tick **Set as a pre-release** on the release page. (The version check strips only the
leading `v`, so set `__version__ = "0.2.0-beta.1"` to match.)

## Testing the build without releasing

**Actions → Release → Run workflow** builds the exe and attaches it to the run as an artifact (`Isla-exe`) without creating a release.

## What the build does

`packaging/build.ps1` runs [PyInstaller](https://pyinstaller.org) twice:

1. `isla-hook`, the small relay Claude Code runs on every tool call, as a *folder* build because a one-file exe unpacks itself on each run, which would add about a second to every call.
2. `Isla.exe`, a one-file windowed build with the relay folder bundled inside. When you press **Connect**, the relay is unpacked to `%APPDATA%\Isla\isla-hook\` and registered in Claude Code's settings.

## Known caveats

- **SmartScreen / antivirus warnings.** The exe isn't code-signed, so Windows shows *"Windows protected your PC"* (More info → Run anyway) and a few antivirus tools flag PyInstaller apps. The README tells users this. To remove the warning you need a code-signing certificate (e.g. [Azure Trusted Signing](https://learn.microsoft.com/azure/trusted-signing/) or a commercial cert) and to sign `dist\Isla.exe` with `signtool` before uploading. False positives can also be reported to Microsoft and to the antivirus vendor.
- **Size.** About 75 MB because it bundles Python and Qt.
- **Windows only** (it uses the Windows media-session APIs).
