"""Synced lyrics: LRC parsing, LRCLIB lookup, disk cache."""
from __future__ import annotations

import bisect
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

import requests

_TIME = re.compile(r"\[(\d+):(\d+(?:\.\d+)?)\]")
LRCLIB = "https://lrclib.net/api"
_HEADERS = {"User-Agent": "Isla-Dynamic-Island/0.1 (https://github.com/)"}


@dataclass(frozen=True)
class Line:
    time: float
    text: str


def parse_lrc(text: str) -> list[Line]:
    """Parse LRC text. Lines may carry several timestamps; result is time-sorted."""
    out: list[Line] = []
    for raw in text.splitlines():
        stamps = _TIME.findall(raw)
        if not stamps:
            continue
        body = _TIME.sub("", raw).strip()
        for mm, ss in stamps:
            out.append(Line(int(mm) * 60 + float(ss), body))
    out.sort(key=lambda l: l.time)
    return out


def current_index(lines: list[Line], position: float) -> int:
    """Index of the line active at `position` seconds, or -1 before the first line."""
    times = [l.time for l in lines]
    return bisect.bisect_right(times, position) - 1


def _cache_path(cache_dir: Path, artist: str, title: str) -> Path:
    key = hashlib.sha1(f"{artist}\0{title}".lower().encode()).hexdigest()[:20]
    return cache_dir / f"{key}.json"


def fetch_lyrics(artist: str, title: str, duration: float, cache_dir: Path) -> list[Line]:
    """Return synced lines (empty if none). Network errors yield []. Misses are cached too."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached = _cache_path(cache_dir, artist, title)
    if cached.exists():
        try:
            return [Line(t, s) for t, s in json.loads(cached.read_text(encoding="utf-8"))]
        except (OSError, ValueError):
            pass
    lrc = _query(artist, title, duration)
    lines = parse_lrc(lrc) if lrc else []
    if lrc is not None:  # only cache real answers, not network failures
        cached.write_text(json.dumps([[l.time, l.text] for l in lines]), encoding="utf-8")
    return lines


def _query(artist: str, title: str, duration: float) -> str | None:
    """LRC text, '' when LRCLIB has nothing, None on network failure."""
    try:
        r = requests.get(
            f"{LRCLIB}/get",
            params={"artist_name": artist, "track_name": title, "duration": int(duration)},
            headers=_HEADERS,
            timeout=6,
        )
        if r.status_code == 200 and r.json().get("syncedLyrics"):
            return r.json()["syncedLyrics"]
        r = requests.get(
            f"{LRCLIB}/search", params={"q": f"{artist} {title}"}, headers=_HEADERS, timeout=6
        )
        if r.status_code == 200:
            for hit in r.json():
                if hit.get("syncedLyrics"):
                    return hit["syncedLyrics"]
        return ""
    except (requests.RequestException, ValueError):
        return None
