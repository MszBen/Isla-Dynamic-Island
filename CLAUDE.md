# Isla — Dynamic Island for Windows 11

Isla is a Python desktop app: a pill-shaped "dynamic island" docked at the top-centre of the
primary screen. It idles as a small pill with a mascot, and expands on hover/drag/events.

## What we're combining (researched from the three source sites)

| Source | What it actually is | What we take |
|---|---|---|
| **Nusa** (rama2555.github.io/nusa) | Native Windows notch: media controls, **synced lyrics** (click a line to seek), pomodoro, to-do, system overlays, **file shelf** (drop files on the notch, drag them back out), idle eyes, hides for fullscreen apps, no CPU when idle | File shelf, synced lyrics, media controls, hover-to-expand, fullscreen hiding, "draw only while animating" |
| **TwoCode** (twocode.nl) | Windows island showing Claude Code / Codex activity, allow/deny from the island, completion alerts, and the mascot **Robo** with emotion states (happy, curious, focused, wink, in love, dizzy when poked). *It has no music/lyrics — those come from Nusa.* | Mascot + emotion states, poke -> dizzy, completion/attention alerts |
| **Coucou** (github.com/Louis-CFM/coucou) | Open-source (MIT) notch companion for AI agents. Hook relay programs forward agent events to the app over a local pipe/socket; relay **never blocks the agent if the app isn't running**; installer backs up agent config and merges hooks; Tauri/Rust on Windows | Agent management architecture: hook relay -> local server -> session model, approvals, non-blocking failure mode, safe hook installer |

## Decisions

- **Language/UI: Python 3.12 + PySide6 (Qt 6).** Frameless, translucent, always-on-top windows, `QVariantAnimation`
  for the morphing pill, and `QPainter` for the vector mascot. Alternatives rejected: Tkinter (no per-pixel alpha / smooth
  animation), WebView/Electron (heavy, not Python), Tauri (not Python).
- **Media + lyrics:** Windows System Media Transport Controls via `winrt-Windows.Media.Control` (works with Spotify,
  browsers, Apple Music, anything using SMTC). Lyrics from the free keyless **LRCLIB** API, cached on disk.
- **Agents:** the "Coucou model". `hooks/isla_hook.py` (stdlib only) is registered as a Claude Code hook. It POSTs the
  hook payload to `127.0.0.1:47821`. For `PermissionRequest` it waits for the island's Allow/Deny and prints the hook
  decision JSON. If Isla isn't running, or the user doesn't answer in time, it exits 0 silently so Claude Code
  falls back to its normal prompt. **Never block the agent.**
- **Hook installation:** `python -m isla install-hooks` backs up `~/.claude/settings.json`, merges (never overwrites)
  our entries, and is idempotent. Hook commands use forward-slash paths because Claude Code runs hooks through a
  POSIX shell on Windows.
- **Single process, one window.** The island is one frameless widget whose geometry is animated; its content is
  swapped by a small mode state machine. Services live in worker threads and talk to the UI only through Qt signals.

## Layout

```
isla/
  __main__.py     CLI: run (default) | install-hooks [--dry-run] | uninstall-hooks
  app.py          wires services <-> island, tray icon
  config.py       JSON config in %APPDATA%/Isla
  island.py       the window, mode state machine, all views
  mascot.py       Isla the mascot (QPainter), emotions
  media.py        SMTC poller + commands (own thread / asyncio loop)
  lyrics.py       LRC parse + LRCLIB fetch + disk cache (pure logic is unit-tested)
  shelf.py        shelf store (JSON of paths)
  agents.py       session model + localhost hook server
  hooks_install.py  safe settings.json merge
  system.py       fullscreen detection, click-through, autostart
  settings.py     separate settings window (scrolls; autosaves)
  welcome.py      first-run quick tour
  focus.py        pomodoro logic (pure)
  confetti.py     click-through confetti overlay
  power.py, devices.py, sound.py   charger / headphone peeks, chime
hooks/isla_hook.py  relay executed by Claude Code
tests/              pytest, no Qt display or network required
```

## UX principles (keep these when adding features)

- **Discoverable without docs**: every painted button has a hover hint in `TIPS` (island.py) and a pointer cursor; a test enforces it.
- **No dead ends**: every tab has an empty state that says what to do next, ideally with a button (e.g. Agents -> Connect).
- **No terminal for normal use**: anything the CLI can do (connect Claude Code, quit, settings) is also reachable from the island's right-click menu, the tray, or Settings.
- **Never trap the user**: Quit is in three places; a second launch says Isla is already running; double-click makes it see-through.
- **Respect the system**: clock follows the Windows 12/24h setting; hides for fullscreen apps; never steals focus.
- **Settings**: plain words, a hint under every option, changes apply and save immediately, window scrolls on small screens.
- **Failures are visible**: windowless runs log to `%APPDATA%\Isla\isla.log`; problems the user can act on show from the tray.

## Licence

PolyForm Noncommercial 1.0.0 (`LICENSE`). Keep the `Required Notice:` line at the top intact, and add new bundled dependencies to `THIRD_PARTY.md`.

## Rules for working here

- Keep logic that can be pure (LRC parsing, hook merge, session reducer, shelf store) free of Qt so it is testable.
- UI only touches widgets on the Qt thread. Threads emit signals.
- Idle must be cheap: animations run only while something is moving; media is polled at 1 Hz; a 30 fps repaint timer
  exists only while the mascot/expand animation needs it.
- Failure of any service (no SMTC, no network, port in use) must degrade the feature, never crash the island.
- Match the existing style: type hints, small modules, comments only for non-obvious "why".
- Run `python -m pytest` before finishing a change; smoke-test the UI with `python -m isla`.

## Roadmap (not built yet)

Codex hook support, "ask about my screen" drag-the-mascot feature (TwoCode), chat with LLMs (Coucou),
pomodoro/to-do/water modules (Nusa), volume/battery/Wi-Fi peeks, settings window, installer/autostart.
