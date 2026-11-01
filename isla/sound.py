"""A small generated chime (no bundled audio asset)."""
from __future__ import annotations

import math
import struct
import sys
import wave
from pathlib import Path

RATE = 22050


def make_chime(path: Path) -> None:
    """Two soft bell notes (E6 then A6) with exponential decay."""
    frames = bytearray()
    for start, freq in ((0.0, 1318.5), (0.22, 1760.0)):
        n0 = int(start * RATE)
        for i in range(int(0.75 * RATE)):
            t = i / RATE
            v = math.sin(2 * math.pi * freq * t) * math.exp(-t * 5.5) * 0.45
            v += math.sin(2 * math.pi * freq * 2.0 * t) * math.exp(-t * 9) * 0.12  # overtone
            idx = (n0 + i) * 2
            if idx + 2 > len(frames):
                frames.extend(b"\x00\x00" * ((idx + 2 - len(frames)) // 2 + 1))
            cur = struct.unpack_from("<h", frames, idx)[0]
            struct.pack_into("<h", frames, idx, max(-32767, min(32767, cur + int(v * 32767))))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(bytes(frames))


def play_chime(cache_dir: Path) -> None:
    if sys.platform != "win32":
        return
    import winsound

    path = cache_dir / "chime.wav"
    try:
        if not path.exists():
            make_chime(path)
        winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC)
    except (OSError, RuntimeError):
        pass
