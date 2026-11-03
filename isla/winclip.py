"""Reads Windows' own clipboard history (Win+V). Degrades to nothing if it's off, blocked or unavailable."""
from __future__ import annotations

import asyncio
import logging

try:
    from winrt.windows.applicationmodel.datatransfer import Clipboard, StandardDataFormats
    AVAILABLE = True
except Exception:  # not Windows / package missing
    AVAILABLE = False


async def _read() -> list[tuple[str, float]]:
    result = await Clipboard.get_history_items_async()
    out: list[tuple[str, float]] = []
    for item in result.items:
        content = item.content
        if content.contains(StandardDataFormats.text):
            out.append((await content.get_text_async(), item.timestamp.timestamp()))
    return out


def fetch_history() -> list[tuple[str, float]]:
    """Text items as (text, epoch seconds), newest first. Blocking: call from a worker thread."""
    if not AVAILABLE:
        return []
    try:
        return asyncio.run(_read())
    except Exception as exc:
        logging.info("Windows clipboard history unavailable: %s", exc)
        return []
