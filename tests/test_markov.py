"""Unit tests for AdaptiveMarkov: fallback, resolution, confidence, phases."""
from __future__ import annotations

import threading
import time

import pytest

from riff.ai.responder import (
    AdaptiveMarkov,
    NOTE_NAMES,
    RESOLUTION_DEGREES,
    _detect_scale,
)

C_MAJOR = {0, 2, 4, 5, 7, 9, 11}


def _learn_scale(m: AdaptiveMarkov, pcs: list[int], n: int) -> None:
    """Feed a repeating pitch class sequence into the model."""
    prev = None
    for i in range(n):
        pc = pcs[i % len(pcs)]
        m.learn(pc, prev)
        prev = pc


# ── Phase progression ────────────────────────────────────────────────────────

class TestPhases:
    def test_phase_1_initial(self):
        m = AdaptiveMarkov()
        assert m.phase == 1
        assert m.current_order == 4
        assert m.notes_learned == 0

    def test_phase_2_at_50(self):
        m = AdaptiveMarkov()
        _learn_scale(m, [0, 2, 4, 5, 7], 50)
        assert m.phase == 2
        assert m.current_order == 8

    def test_phase_3_at_150(self):
        m = AdaptiveMarkov()
        _learn_scale(m, [0, 2, 4, 5, 7], 150)
        assert m.phase == 3
        assert m.current_order == 12

    def test_phase_4_at_300(self):
        m = AdaptiveMarkov()
        _learn_scale(m, [0, 2, 4, 5, 7], 300)
        assert m.phase == 4
        assert m.current_order == 16


# ── Fallback chain ───────────────────────────────────────────────────────────

class TestFallback:
    def test_empty_model_falls_back_to_scale(self):
        """With zero learned notes, generate must still return an in-scale interval."""
        m = AdaptiveMarkov()
        for _ in range(50):
            interval = m.generate(C_MAJOR, 0)
            assert (0 + interval) % 12 in C_MAJOR

    def test_sparse_model_never_out_of_scale(self):
        """With just a few notes, all generated intervals stay in scale."""
        m = AdaptiveMarkov()
        _learn_scale(m, [0, 4, 7], 5)
        for _ in range(100):
            interval = m.generate(C_MAJOR, 0)
            assert (0 + interval) % 12 in C_MAJOR

    def test_fallback_from_high_order(self):
        """Phase 4 model with a novel context must degrade gracefully."""
        m = AdaptiveMarkov()
        # Learn a pattern long enough for phase 4
        _learn_scale(m, [0, 2, 4, 5, 7, 9, 11], 310)
        assert m.phase == 4

        # Force a context the model hasn't seen by injecting alien intervals
        # The generate call should still succeed (fallback chain)
        for _ in range(50):
            interval = m.generate(C_MAJOR, 3)  # root = D#, unusual
            assert (3 + interval) % 12 in C_MAJOR

    def test_never_silence(self):
        """generate() must always return an int, never None."""
        m = AdaptiveMarkov()
        for _ in range(20):
            result = m.generate(C_MAJOR, 0)
            assert isinstance(result, int)


# ── Resolution ───────────────────────────────────────────────────────────────

class TestResolution:
    def test_resolution_degrees_are_in_c_major(self):
        """Sanity: I(0), III(4), V(7) are all in C major."""
        for degree in RESOLUTION_DEGREES:
            assert degree in C_MAJOR

    def test_resolution_candidates_always_exist(self):
        """For any root in C major, at least one resolution degree is in scale."""
        for root in C_MAJOR:
            candidates = [i for i in RESOLUTION_DEGREES if (root + i) % 12 in C_MAJOR]
            assert len(candidates) > 0, f"No resolution for root={root}"


# ── Confidence tracking ──────────────────────────────────────────────────────

class TestConfidence:
    def test_confidence_zero_before_generate(self):
        m = AdaptiveMarkov()
        assert m.confidence == 0.0

    def test_confidence_increases_with_known_patterns(self):
        m = AdaptiveMarkov()
        # Learn a very regular pattern
        _learn_scale(m, [0, 2, 4, 5, 7], 100)
        # Generate many notes — the model has seen these sequences
        for _ in range(50):
            m.generate(C_MAJOR, 0)
        assert m.confidence > 0.5, f"Expected high confidence, got {m.confidence:.2f}"

    def test_confidence_bounded_0_to_1(self):
        m = AdaptiveMarkov()
        _learn_scale(m, [0, 4, 7], 30)
        for _ in range(100):
            m.generate(C_MAJOR, 0)
        assert 0.0 <= m.confidence <= 1.0


# ── Thread safety ────────────────────────────────────────────────────────────

class TestThreadSafety:
    def test_concurrent_learn_and_generate(self):
        """learn() and generate() running in parallel must not crash."""
        m = AdaptiveMarkov()
        errors = []

        def learner():
            try:
                prev = None
                for i in range(500):
                    pc = i % 12
                    m.learn(pc, prev)
                    prev = pc
            except Exception as e:
                errors.append(e)

        def generator():
            try:
                for _ in range(500):
                    m.generate(C_MAJOR, 0)
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=learner)
        t2 = threading.Thread(target=generator)
        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)

        assert not errors, f"Thread errors: {errors}"
        assert m.notes_learned == 500


# ── Latency ──────────────────────────────────────────────────────────────────

class TestLatency:
    def test_generate_under_20ms(self):
        """generate() must complete in < 20ms even at phase 4."""
        m = AdaptiveMarkov()
        _learn_scale(m, [0, 2, 4, 5, 7, 9, 11], 350)
        assert m.phase == 4

        times = []
        for _ in range(100):
            start = time.perf_counter()
            m.generate(C_MAJOR, 0)
            elapsed_ms = (time.perf_counter() - start) * 1000
            times.append(elapsed_ms)

        avg = sum(times) / len(times)
        worst = max(times)
        assert worst < 20.0, f"Worst: {worst:.2f}ms, Avg: {avg:.2f}ms"
