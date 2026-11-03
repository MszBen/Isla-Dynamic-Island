# Changelog

All notable changes to Isla. Format follows [Keep a Changelog](https://keepachangelog.com), versions follow [semver](https://semver.org).
Add entries under **Unreleased** as you work; `packaging/release.py` stamps them with the version and date.

## [Unreleased]

### Added
- **Clips tab**: remembers what you copy and lets you search it. Pulls in Windows' own clipboard history (Win+V) too, skips copies from password managers, and keeps history in memory only.
- **Shelf groups and multi-drag**: files dropped together stay grouped. Drag a whole group, Ctrl+click to pick several items and drag them together, or drag one at a time.
- **Display picker** in Settings, for choosing which screen the island sits on (shown when you have more than one).
- **Settings cog** on the island, and a mascot that gets her head opened and worked on by robot arms while Settings is open.

### Changed
- The island waits longer before collapsing on the Shelf tab.

### Fixed
- Project names on the Agents tab are no longer cut off when there is room to show them.

## [0.1.0]

First public release: dynamic island with mascot, media controls and synced lyrics, file shelf, focus timer,
Claude Code agent approvals, settings window and a single-file `Isla.exe`.
