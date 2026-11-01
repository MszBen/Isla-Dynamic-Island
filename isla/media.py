"""Now-playing via Windows System Media Transport Controls (Spotify, browsers, etc.)."""
from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass
from datetime import datetime, timezone

from PySide6.QtCore import QObject, Signal

try:
    from winrt.windows.media.control import (
        GlobalSystemMediaTransportControlsSessionManager as _Manager,
    )
    from winrt.windows.storage.streams import DataReader
    AVAILABLE = True
except Exception:  # not Windows / package missing -> feature degrades
    AVAILABLE = False

_PLAYING = 4


@dataclass
class MediaInfo:
    active: bool = False
    title: str = ""
    artist: str = ""
    playing: bool = False
    position: float = 0.0
    duration: float = 0.0
    art: bytes | None = None

    @property
    def key(self) -> tuple[str, str]:
        return (self.artist, self.title)


class MediaService(QObject):
    changed = Signal(object)  # MediaInfo

    def __init__(self) -> None:
        super().__init__()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._art_key: tuple[str, str] | None = None
        self._art: bytes | None = None

    def start(self) -> None:
        if not AVAILABLE:
            return
        threading.Thread(target=self._run, daemon=True, name="isla-media").start()

    def _run(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._loop.run_until_complete(self._poll())

    async def _poll(self) -> None:
        mgr = await _Manager.request_async()
        while True:
            try:
                self.changed.emit(await self._read(mgr.get_current_session()))
            except Exception:
                self.changed.emit(MediaInfo())
            await asyncio.sleep(1.0)

    async def _read(self, session) -> MediaInfo:
        if session is None:
            return MediaInfo()
        props = await session.try_get_media_properties_async()
        tl = session.get_timeline_properties()
        playing = int(session.get_playback_info().playback_status) == _PLAYING
        position = tl.position.total_seconds()
        if playing and tl.last_updated_time:
            position += (datetime.now(timezone.utc) - tl.last_updated_time).total_seconds()
        duration = (tl.end_time - tl.start_time).total_seconds()
        info = MediaInfo(
            True, props.title or "", props.artist or "", playing,
            max(0.0, min(position, duration) if duration > 0 else position), duration,
        )
        if info.key != self._art_key:
            self._art_key, self._art = info.key, await self._thumb(props)
        info.art = self._art
        return info

    @staticmethod
    async def _thumb(props) -> bytes | None:
        try:
            stream = await props.thumbnail.open_read_async()
            reader = DataReader(stream)
            await reader.load_async(stream.size)
            buf = bytearray(stream.size)
            reader.read_bytes(buf)
            return bytes(buf)
        except Exception:
            return None

    # -- commands (UI thread) --------------------------------------------
    def _send(self, method: str, *args) -> None:
        if not (AVAILABLE and self._loop):
            return

        async def go() -> None:
            try:
                s = (await _Manager.request_async()).get_current_session()
                if s:
                    await getattr(s, method)(*args)
            except Exception:
                pass

        asyncio.run_coroutine_threadsafe(go(), self._loop)

    def toggle(self) -> None:
        self._send("try_toggle_play_pause_async")

    def next(self) -> None:
        self._send("try_skip_next_async")

    def previous(self) -> None:
        self._send("try_skip_previous_async")

    def seek(self, seconds: float) -> None:
        self._send("try_change_playback_position_async", int(seconds * 10_000_000))
