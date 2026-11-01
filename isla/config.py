"""JSON config + data directory in %APPDATA%/Isla."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path


def data_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    path = Path(base) / "Isla"
    path.mkdir(parents=True, exist_ok=True)
    return path


@dataclass
class Config:
    port: int = 47821
    collapse_delay_ms: int = 450
    approval_timeout_s: int = 110
    hide_in_fullscreen: bool = True
    lyrics_enabled: bool = True
    ghost_opacity: float = 0.22

    @classmethod
    def load(cls, path: Path | None = None) -> "Config":
        path = path or data_dir() / "config.json"
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls()
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in raw.items() if k in known})

    def save(self, path: Path | None = None) -> None:
        path = path or data_dir() / "config.json"
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
