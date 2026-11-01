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


def test_quick_break_pauses_focus_and_resumes_after():
    t = make()
    t.start(0)
    t.tick(30)                               # 70s of focus left
    assert t.can_break and t.start_break(30)
    assert t.phase == SHORT and t.label == "Quick break" and round(t.remaining) == 20
    assert t.tick(45) == [] and round(t.remaining) == 5
    assert t.tick(55) == ["work_resume"]
    assert t.phase == WORK and t.running and round(t.remaining) == 70
    assert t.done == 0                       # a quick break isn't a completed session
    t.tick(65)
    assert round(t.remaining) == 60


def test_quick_break_from_paused_focus_and_skip_resumes():
    t = make()
    t.start(0)
    t.pause(40)
    assert t.start_break(100)
    assert t.skip(105) == WORK and t.running and round(t.remaining) == 60
    assert t.interrupted is None and t.can_break  # a later quick break is allowed again


def test_no_quick_break_when_idle_or_already_on_break():
    t = make()
    assert not t.can_break and not t.start_break(0)
    t.start(0)
    t.start_break(5)
    assert not t.can_break and not t.start_break(6)


def test_reset_clears_quick_break():
    t = make()
    t.start(0)
    t.start_break(10)
    t.reset()
    assert t.interrupted is None and t.phase == WORK and not t.running


def test_adjust_length_and_limits():
    t = make()  # work = 100s -> below the 5 min floor, so +step snaps to range
    assert t.adjust(300) and t.work == 400 and t.remaining == 400
    t.start(0)
    t.tick(100)
    assert t.adjust(300) and t.work == 700 and round(t.remaining) == 600
    assert t.adjust(-3000) and t.work == 300           # clamped to the 5 min floor
    t2 = make()
    t2.configure(300, 20, 60, 2)
    t2.start(0)
    t2.tick(290)
    assert not t2.adjust(-60)                          # already at the 5 min floor
    assert t2.work == 300
    t3 = FocusTimer(work=7200)
    assert not t3.adjust(300)                          # already at max
