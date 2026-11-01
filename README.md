# Isla — a dynamic island for Windows 11

Isla sits at the top of your screen as a small pill with a mascot. Hover over it and it opens up.

- **Music**: now playing from Spotify, your browser and more, with controls and synced lyrics (click a line to jump to it)
- **Focus timer**: a Pomodoro timer with quick breaks, adjustable right from the island
- **File shelf**: drop files on the island, drag them out into any app later
- **Claude Code**: see what it's doing, how long it's been going and approve actions (Deny / Allow always / Allow once) without switching windows
- **Little extras**: charger and headphone animations, confetti when work finishes, and a mascot that reacts to it all

## Getting started

1. Install [Python 3.12+](https://www.python.org/downloads/) (tick "Add python.exe to PATH").
2. In this folder run `pip install -r requirements.txt`.
3. Double-click **`Isla.pyw`** (or run `python -m isla`).

A short tour opens the first time. You can also reopen it from the tray icon, or from the island's right-click menu.

## Tips

| Do this | To get this |
|---|---|
| Hover over the island | It expands into tabs: Music, Focus, Shelf, Agents |
| Drop files on it | They go on the shelf |
| Double-click it | It turns see-through and clicks pass through until you move away |
| Right-click it | Settings, quick tour, quit |
| Scroll over the Focus tab | Change the timer length |
| Click the tray icon | Open settings (look under the ^ arrow if you can't see it) |

### Connecting Claude Code
Open the **Agents** tab and press **Connect** (or use Settings). Isla adds its hooks to `~/.claude/settings.json` after backing it up. Restart Claude Code sessions that were already open.
Command line: `python -m isla install-hooks [--dry-run]` and `python -m isla uninstall-hooks`.

### Start with Windows
Settings → "Start with Windows".

## Troubleshooting

- **I can't find Isla**: it may be see-through or hidden for a fullscreen app. Check the tray icon (under the ^ arrow). Starting a second copy tells you Isla is already running.
- **Claude Code isn't showing up**: make sure the Agents tab says "Connected", and restart open Claude Code sessions. If port 47821 is busy Isla tells you from the tray.
- **No lyrics**: lyrics come from lrclib.net and not every song has synced ones. Turn them off in Settings if you prefer.
- **Something broke**: errors are written to `%APPDATA%\Isla\isla.log`.

## Development

```bash
python -m pytest
```
See `CLAUDE.md` for the design and roadmap.
