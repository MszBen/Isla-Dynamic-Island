"""Pomodoro focus timer. Pure logic: time is passed in, so it is easy to test."""
from __future__ import annotations

WORK, SHORT, LONG = "work", "short", "long"
LABEL = {WORK: "Focus", SHORT: "Break", LONG: "Long break"}


class FocusTimer:
    def __init__(self, work: float = 25 * 60, short: float = 5 * 60, long: float = 15 * 60, cycles: int = 4):
        self.work, self.short, self.long, self.cycles = work, short, long, cycles
        self.phase = WORK
        self.remaining = work
        self.running = False
        self.done = 0  # work sessions completed since reset
        self._last: float | None = None

    # -- derived -------------------------------------------------------
    @property
    def total(self) -> float:
        return {WORK: self.work, SHORT: self.short, LONG: self.long}[self.phase]

    @property
    def progress(self) -> float:
        return 0.0 if self.total <= 0 else min(1.0, max(0.0, 1 - self.remaining / self.total))

    @property
    def active(self) -> bool:
        """Running, or paused part-way through a phase."""
        return self.running or self.remaining < self.total

    @property
    def session_dots(self) -> tuple[int, int]:
        """(filled, total) pips for the current cycle."""
        filled = self.cycles if self.phase == LONG else self.done % self.cycles
        return filled, self.cycles

    # -- control -------------------------------------------------------
    def configure(self, work: float, short: float, long: float, cycles: int = 4) -> None:
        idle = not self.active  # judged against the old durations
        self.work, self.short, self.long, self.cycles = work, short, long, max(1, cycles)
        if idle:
            self.remaining = self.total

    def start(self, now: float) -> None:
        self.running, self._last = True, now

    def pause(self, now: float) -> None:
        self.tick(now)
        self.running = False

    def toggle(self, now: float) -> None:
        self.pause(now) if self.running else self.start(now)

    def reset(self) -> None:
        self.phase, self.running, self.done, self._last = WORK, False, 0, None
        self.remaining = self.work

    def skip(self, now: float) -> str:
        """Jump to the next phase (a skipped work session doesn't count as completed)."""
        self.tick(now)
        was_running = self.running
        if self.phase == WORK:
            self.phase = SHORT
            self.running = was_running
        else:
            self.phase, self.running = WORK, False
        self.remaining = self.total
        self._last = now
        return self.phase

    def tick(self, now: float) -> list[str]:
        """Advance the clock. Returns phase-change events: 'break', 'long_break', 'work_ready'."""
        events: list[str] = []
        if not self.running:
            self._last = now
            return events
        dt = 0.0 if self._last is None else max(0.0, now - self._last)
        self._last = now
        self.remaining -= dt
        while self.running and self.remaining <= 0:
            carry = -self.remaining
            if self.phase == WORK:
                self.done += 1
                long_break = self.done % self.cycles == 0
                self.phase = LONG if long_break else SHORT
                self.remaining = max(0.0, self.total - carry)
                events.append("long_break" if long_break else "break")
            else:  # break over: wait for the user to start the next focus session
                self.phase, self.running = WORK, False
                self.remaining = self.total
                events.append("work_ready")
        return events


def format_clock(seconds: float) -> str:
    s = max(0, int(seconds + 0.999))
    return f"{s // 60:02d}:{s % 60:02d}"
