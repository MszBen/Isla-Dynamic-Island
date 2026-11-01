# Isla — Dynamic Island for Windows 11

A Python/PySide6 dynamic island that combines:
- **Nusa**: hover-to-expand pill, media controls, synced lyrics (click a line to seek), a **file shelf** (drop files in, drag them back out), hides for fullscreen apps
- **TwoCode**: the **mascot** (emotions: happy, curious, focused, wink, dizzy when poked...)
- **Coucou**: **AI agent management** — Claude Code activity and Allow/Deny approvals via hooks

```bash
pip install -r requirements.txt
python -m isla                      # run
python -m isla install-hooks        # connect Claude Code (backs up ~/.claude/settings.json)
python -m isla install-hooks --dry-run
python -m pytest
```

See `CLAUDE.md` for the design and roadmap.
