"""Smoke tests for the session timer (run: python -m pytest host/tests)."""
import time

from nimbusseat_host.session_timer import SessionTimer


def test_full_cycle_fast():
    events = []
    t = SessionTimer(
        max_duration_minutes=0,           # expires immediately
        warn_at_minutes_left=[1],
        grace_period_seconds=1,
        cooldown_minutes=0,
        on_warning=lambda m: events.append(("warn", m)),
        on_expired=lambda: events.append(("expired",)),
        on_terminate=lambda: events.append(("terminate",)),
    )
    assert t.start("192.168.1.50")
    time.sleep(3)
    assert ("expired",) in events
    assert ("terminate",) in events


def test_reject_second_session():
    t = SessionTimer(max_duration_minutes=360)
    assert t.start("192.168.1.50")
    assert not t.start("192.168.1.51")
    t.stop()
