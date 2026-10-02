"""
tests/test_temporal_runtime.py - Test Suite for Deterministic Virtual Temporal Runtime Core

Verifies:
  - VirtualClock invariants (monotonicity, no rewind, zero-advance, int ms representation).
  - ScheduledEvent deterministic ordering and safe comparison.
  - Scheduler primitives (schedule_at, schedule_after, run_due, run_until, cancel).
  - Dynamic scheduling (future, same-time, self-rescheduling, zero-delay chains).
  - Clock synchronization during callback execution (clock.now() == event.timestamp).
  - Exception propagation and queue integrity.
  - Full determinism regression across multiple runs.
  - Boundary conditions and performance baseline.
"""
import unittest
from native_engine.temporal import (
    BaseClock,
    VirtualClock,
    RealTimeClock,
    ScheduledEvent,
    Scheduler,
)


class TestVirtualClock(unittest.TestCase):
    """Test VirtualClock functionality and strict invariants."""

    def test_initial_time(self):
        clock_default = VirtualClock()
        self.assertEqual(clock_default.now(), 0)

        clock_custom = VirtualClock(1000)
        self.assertEqual(clock_custom.now(), 1000)

        with self.assertRaises(ValueError):
            VirtualClock(-10)

        with self.assertRaises(TypeError):
            VirtualClock("100")  # type: ignore

    def test_advance_monotonic(self):
        clock = VirtualClock(0)
        self.assertEqual(clock.advance(100), 100)
        self.assertEqual(clock.now(), 100)
        self.assertEqual(clock.advance(50), 150)
        self.assertEqual(clock.now(), 150)

    def test_advance_zero(self):
        clock = VirtualClock(100)
        self.assertEqual(clock.advance(0), 100)
        self.assertEqual(clock.now(), 100)

    def test_advance_negative_rejected(self):
        clock = VirtualClock(100)
        with self.assertRaises(ValueError):
            clock.advance(-1)
        self.assertEqual(clock.now(), 100)

    def test_set_forward(self):
        clock = VirtualClock(100)
        self.assertEqual(clock.set(200), 200)
        self.assertEqual(clock.now(), 200)
        self.assertEqual(clock.set(200), 200)

    def test_set_backward_rejected(self):
        clock = VirtualClock(100)
        with self.assertRaises(ValueError):
            clock.set(99)
        self.assertEqual(clock.now(), 100)

    def test_type_validation(self):
        clock = VirtualClock(0)
        with self.assertRaises(TypeError):
            clock.advance(10.5)  # type: ignore
        with self.assertRaises(TypeError):
            clock.set(10.5)  # type: ignore


class TestRealTimeClock(unittest.TestCase):
    """Test RealTimeClock functionality, pacing, and temporal invariants."""

    def test_initial_time_and_scale(self):
        clock_default = RealTimeClock()
        self.assertEqual(clock_default.now(), 0)
        self.assertEqual(clock_default.current_time_ms, 0)
        self.assertAlmostEqual(clock_default.time_scale, 1.0)

        clock_scaled = RealTimeClock(initial_time_ms=500, time_scale=2.5)
        self.assertEqual(clock_scaled.now(), 500)
        self.assertAlmostEqual(clock_scaled.time_scale, 2.5)

        # Legacy start_time_ms kwarg
        clock_legacy = RealTimeClock(start_time_ms=300)
        self.assertEqual(clock_legacy.now(), 300)

        with self.assertRaises(ValueError):
            RealTimeClock(-10)

        with self.assertRaises(TypeError):
            RealTimeClock("100")  # type: ignore

    def test_advance_and_set_monotonic(self):
        clock = RealTimeClock(0, time_scale=100.0)
        self.assertEqual(clock.advance(50), 50)
        self.assertEqual(clock.now(), 50)
        self.assertEqual(clock.set(100), 100)
        self.assertEqual(clock.now(), 100)

        # Rejects backwards
        with self.assertRaises(ValueError):
            clock.advance(-1)
        with self.assertRaises(ValueError):
            clock.set(90)

    def test_scheduler_integration_with_real_time_clock(self):
        clock = RealTimeClock(0, time_scale=50.0)
        scheduler = Scheduler(clock)

        log = []
        scheduler.schedule_at(20, lambda: log.append(("EVT", clock.now())))
        scheduler.run_until(20)

        self.assertEqual(clock.now(), 20)
        self.assertEqual(log, [("EVT", 20)])


class TestScheduledEvent(unittest.TestCase):
    """Test ScheduledEvent ordering and comparison safety."""

    def test_deterministic_ordering(self):
        e1 = ScheduledEvent(timestamp=100, sequence=1, callback=lambda: None)
        e2 = ScheduledEvent(timestamp=100, sequence=2, callback=lambda: None)
        e3 = ScheduledEvent(timestamp=200, sequence=1, callback=lambda: None)

        self.assertTrue(e1 < e2)
        self.assertTrue(e2 < e3)
        self.assertTrue(e1 < e3)

        # Inverted comparisons
        self.assertFalse(e2 < e1)
        self.assertFalse(e3 < e2)

    def test_callback_not_compared(self):
        # Two events with same timestamp and sequence but uncomparable callbacks
        class Uncomparable:
            pass

        cb1 = Uncomparable()
        cb2 = Uncomparable()

        e1 = ScheduledEvent(timestamp=100, sequence=1, callback=cb1)  # type: ignore
        e2 = ScheduledEvent(timestamp=100, sequence=1, callback=cb2)  # type: ignore

        # Should not raise TypeError when checking <= or >=
        self.assertTrue(e1 <= e2)
        self.assertTrue(e1 >= e2)

    def test_cancel(self):
        e = ScheduledEvent(timestamp=100, sequence=1, callback=lambda: None)
        self.assertFalse(e.cancelled)
        e.cancel()
        self.assertTrue(e.cancelled)


class TestSchedulerCore(unittest.TestCase):
    """Test core Scheduler behaviors and execution semantics."""

    def setUp(self):
        self.clock = VirtualClock(0)
        self.scheduler = Scheduler(self.clock)
        self.log = []

    def _record(self, tag):
        def _cb():
            self.log.append((tag, self.clock.now()))
        return _cb

    def test_schedule_at_and_after(self):
        self.clock.set(1000)
        e1 = self.scheduler.schedule_at(1640, self._record("A"))
        e2 = self.scheduler.schedule_after(640, self._record("B"))

        self.assertEqual(e1.timestamp, 1640)
        self.assertEqual(e2.timestamp, 1640)
        self.assertEqual(self.scheduler.pending_count(), 2)

    def test_schedule_past_rejected(self):
        self.clock.set(1000)
        with self.assertRaises(ValueError):
            self.scheduler.schedule_at(999, lambda: None)
        with self.assertRaises(ValueError):
            self.scheduler.schedule_after(-1, lambda: None)

    def test_run_due_semantics(self):
        self.clock.set(1000)
        # Schedule at 900 requires clock at 900 or schedule before clock.set
        clock = VirtualClock(0)
        sched = Scheduler(clock)
        log = []

        def rec(tag):
            return lambda: log.append((tag, clock.now()))

        sched.schedule_at(900, rec("A"))
        sched.schedule_at(1000, rec("B"))
        sched.schedule_at(1100, rec("C"))

        clock.set(1000)
        count = sched.run_due()

        self.assertEqual(count, 2)
        self.assertEqual(log, [("A", 1000), ("B", 1000)])
        self.assertEqual(sched.pending_count(), 1)
        self.assertEqual(sched.peek_next().timestamp, 1100)

    def test_run_until_advancement_and_event_timestamp(self):
        self.scheduler.schedule_at(100, self._record("A"))
        self.scheduler.schedule_at(300, self._record("B"))
        self.scheduler.schedule_at(640, self._record("C"))

        executed = self.scheduler.run_until(300)

        self.assertEqual(executed, 2)
        self.assertEqual(self.clock.now(), 300)
        self.assertEqual(self.log, [("A", 100), ("B", 300)])
        self.assertEqual(self.scheduler.pending_count(), 1)
        self.assertEqual(self.scheduler.peek_next().timestamp, 640)

    def test_run_until_target_beyond_events(self):
        self.scheduler.schedule_at(100, self._record("A"))
        self.scheduler.schedule_at(300, self._record("B"))

        executed = self.scheduler.run_until(500)

        self.assertEqual(executed, 2)
        self.assertEqual(self.clock.now(), 500)
        self.assertEqual(self.log, [("A", 100), ("B", 300)])
        self.assertEqual(self.scheduler.pending_count(), 0)

    def test_run_until_empty_queue(self):
        executed = self.scheduler.run_until(500)
        self.assertEqual(executed, 0)
        self.assertEqual(self.clock.now(), 500)

    def test_run_until_backwards_rejected(self):
        self.clock.set(500)
        with self.assertRaises(ValueError):
            self.scheduler.run_until(499)

    def test_cancellation(self):
        e1 = self.scheduler.schedule_at(100, self._record("A"))
        e2 = self.scheduler.schedule_at(200, self._record("B"))
        e3 = self.scheduler.schedule_at(300, self._record("C"))

        self.assertEqual(self.scheduler.pending_count(), 3)
        self.assertTrue(self.scheduler.cancel(e2))
        self.assertFalse(self.scheduler.cancel(e2))  # second cancel returns False
        self.assertEqual(self.scheduler.pending_count(), 2)

        executed = self.scheduler.run_until(400)
        self.assertEqual(executed, 2)
        self.assertEqual(self.log, [("A", 100), ("C", 300)])
        self.assertEqual(self.scheduler.pending_count(), 0)


class TestDynamicScheduling(unittest.TestCase):
    """Test dynamic scheduling from within event callbacks."""

    def setUp(self):
        self.clock = VirtualClock(0)
        self.scheduler = Scheduler(self.clock)
        self.log = []

    def test_dynamic_future_event(self):
        def cb_a():
            self.log.append(("A", self.clock.now()))
            self.scheduler.schedule_at(150, lambda: self.log.append(("B", self.clock.now())))

        self.scheduler.schedule_at(100, cb_a)
        self.scheduler.run_until(200)

        self.assertEqual(self.log, [("A", 100), ("B", 150)])
        self.assertEqual(self.clock.now(), 200)

    def test_dynamic_future_beyond_target_stays_queued(self):
        def cb_a():
            self.log.append(("A", self.clock.now()))
            self.scheduler.schedule_at(250, lambda: self.log.append(("C", self.clock.now())))

        self.scheduler.schedule_at(100, cb_a)
        self.scheduler.run_until(200)

        self.assertEqual(self.log, [("A", 100)])
        self.assertEqual(self.clock.now(), 200)
        self.assertEqual(self.scheduler.pending_count(), 1)
        self.assertEqual(self.scheduler.peek_next().timestamp, 250)

    def test_same_time_dynamic_event(self):
        def cb_a():
            self.log.append(("A", self.clock.now()))
            # Schedule at same virtual time (delay 0)
            self.scheduler.schedule_after(0, lambda: self.log.append(("B", self.clock.now())))

        self.scheduler.schedule_at(100, cb_a)
        self.scheduler.run_until(100)

        self.assertEqual(self.log, [("A", 100), ("B", 100)])
        self.assertEqual(self.clock.now(), 100)

    def test_zero_delay_chain(self):
        # A @ 100 -> B @ 100 -> C @ 100
        def cb_c():
            self.log.append(("C", self.clock.now()))

        def cb_b():
            self.log.append(("B", self.clock.now()))
            self.scheduler.schedule_after(0, cb_c)

        def cb_a():
            self.log.append(("A", self.clock.now()))
            self.scheduler.schedule_after(0, cb_b)

        self.scheduler.schedule_at(100, cb_a)
        self.scheduler.run_until(100)

        self.assertEqual(self.log, [("A", 100), ("B", 100), ("C", 100)])
        self.assertEqual(self.clock.now(), 100)

    def test_self_rescheduling(self):
        # A @ 100 repeats every 100ms up to 500ms
        count = [0]

        def repeating():
            count[0] += 1
            self.log.append((f"A{count[0]}", self.clock.now()))
            self.scheduler.schedule_after(100, repeating)

        self.scheduler.schedule_at(100, repeating)
        self.scheduler.run_until(500)

        expected = [
            ("A1", 100),
            ("A2", 200),
            ("A3", 300),
            ("A4", 400),
            ("A5", 500),
        ]
        self.assertEqual(self.log, expected)
        self.assertEqual(self.clock.now(), 500)
        # Event for 600ms is still pending in queue
        self.assertEqual(self.scheduler.pending_count(), 1)
        self.assertEqual(self.scheduler.peek_next().timestamp, 600)


class TestExceptionsAndQueueIntegrity(unittest.TestCase):
    """Test exception propagation and queue state retention."""

    def test_exception_propagates_and_preserves_queue(self):
        clock = VirtualClock(0)
        scheduler = Scheduler(clock)
        log = []

        scheduler.schedule_at(100, lambda: log.append("A"))
        def faulty():
            raise RuntimeError("Simulation error in event callback")
        scheduler.schedule_at(200, faulty)
        scheduler.schedule_at(300, lambda: log.append("C"))

        with self.assertRaises(RuntimeError) as ctx:
            scheduler.run_until(400)

        self.assertIn("Simulation error", str(ctx.exception))
        # Clock was advanced to faulty event timestamp (200)
        self.assertEqual(clock.now(), 200)
        self.assertEqual(log, ["A"])
        # Event at 300 is still pending and queue remains valid
        self.assertEqual(scheduler.pending_count(), 1)
        self.assertEqual(scheduler.peek_next().timestamp, 300)

        # Resuming execution succeeds cleanly
        executed = scheduler.run_until(400)
        self.assertEqual(executed, 1)
        self.assertEqual(log, ["A", "C"])
        self.assertEqual(clock.now(), 400)


class TestDeterminismAndPerformance(unittest.TestCase):
    """Test reproducibility across runs and high volume execution."""

    def test_determinism_regression(self):
        # Run identical sequence twice and verify exact match
        def run_simulation():
            clock = VirtualClock(0)
            scheduler = Scheduler(clock)
            log = []

            # Multi-event batch at same and distinct timestamps
            scheduler.schedule_at(640, lambda: log.append(("PC_MOVE_1", clock.now())))
            scheduler.schedule_at(640, lambda: log.append(("MON_MOVE_1", clock.now())))
            scheduler.schedule_at(880, lambda: log.append(("PC_SPELL", clock.now())))
            scheduler.schedule_at(1000, lambda: log.append(("FALLBACK", clock.now())))
            scheduler.schedule_after(920, lambda: log.append(("PC_ATTACK", clock.now())))

            # Dynamic addition during run
            def mid_event():
                log.append(("MID", clock.now()))
                scheduler.schedule_after(120, lambda: log.append(("MID_SUB", clock.now())))

            scheduler.schedule_at(700, mid_event)
            scheduler.run_until(1500)
            return log

        run1 = run_simulation()
        run2 = run_simulation()

        self.assertEqual(run1, run2)
        expected_sequence = [
            ("PC_MOVE_1", 640),
            ("MON_MOVE_1", 640),
            ("MID", 700),
            ("MID_SUB", 820),
            ("PC_SPELL", 880),
            ("PC_ATTACK", 920),
            ("FALLBACK", 1000),
        ]
        self.assertEqual(run1, expected_sequence)

    def test_high_volume_events_performance(self):
        # 100,000 scheduled events test
        clock = VirtualClock(0)
        scheduler = Scheduler(clock)
        counter = [0]

        def inc():
            counter[0] += 1

        n_events = 100000
        # Schedule in non-sequential order to exercise heap
        for i in range(n_events):
            scheduler.schedule_at(i % 1000, inc)

        self.assertEqual(scheduler.pending_count(), n_events)
        executed = scheduler.run_until(1000)

        self.assertEqual(executed, n_events)
        self.assertEqual(counter[0], n_events)
        self.assertEqual(scheduler.pending_count(), 0)
        self.assertEqual(clock.now(), 1000)


if __name__ == "__main__":
    unittest.main()
