from isla.focus import LONG, SHORT, WORK, FocusTimer, format_clock


def make() -> FocusTimer:
    return FocusTimer(work=100, short=20, long=60, cycles=2)


def test_idle_timer_is_not_active_and_does_not_advance():
    t = make()
    assert not t.active
    t.tick(50)
    assert t.remaining == 100


def test_work_then_short_then_waits_for_user():
    t = make()
    t.start(0)
    assert t.tick(40) == [] and round(t.remaining) == 60
    assert t.tick(105) == ["break"]
    assert t.phase == SHORT and t.running and round(t.remaining) == 15  # 5s carried into the break
    assert t.tick(130) == ["work_ready"]
    assert t.phase == WORK and not t.running and t.remaining == 100


def test_long_break_after_cycles():
    t = make()
    t.start(0)
    t.tick(100)            # work #1 -> short
    t.tick(120)            # break over, paused
    t.start(120)
    assert t.tick(220) == ["long_break"]
    assert t.phase == LONG and t.session_dots == (2, 2)


def test_pause_resume_and_active():
    t = make()
    t.start(0)
    t.pause(30)
    assert not t.running and t.active and round(t.remaining) == 70
    t.tick(500)  # paused: no change
    assert round(t.remaining) == 70
    t.start(500)
    t.tick(510)
    assert round(t.remaining) == 60


def test_skip_and_reset():
    t = make()
    t.start(0)
    assert t.skip(10) == SHORT and t.done == 0 and t.running
    assert t.skip(11) == WORK and not t.running
    t.reset()
    assert not t.active and t.phase == WORK


def test_configure_only_resets_idle_timer():
    t = make()
    t.configure(200, 20, 60, 2)
    assert t.remaining == 200
    t.start(0)
    t.tick(10)
    t.configure(300, 20, 60, 2)
    assert round(t.remaining) == 190  # running session untouched


def test_format_clock():
    assert format_clock(0) == "00:00"
    assert format_clock(1499.2) == "25:00"
    assert format_clock(65) == "01:05"
