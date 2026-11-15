import numpy as np
import pytest

from src.Algorithm.calibration import estimate_chirp_arrival, estimate_chirp_tdoa


def test_selects_first_arrival_when_later_echo_is_louder():
    sample_rate = 16_000
    rng = np.random.default_rng(42)
    chirp = rng.normal(size=320)
    recording = rng.normal(scale=0.0001, size=sample_rate)
    direct_start = 3_200
    echo_start = 4_000
    recording[direct_start : direct_start + chirp.size] += chirp * 0.35
    recording[echo_start : echo_start + chirp.size] += chirp * 1.5

    result = estimate_chirp_arrival(
        recording,
        chirp,
        sample_rate,
        search_window_s=(0.1, 0.4),
        noise_window_s=(0.0, 0.08),
    )

    assert result.arrival_time_s == pytest.approx(direct_start / sample_rate, abs=1 / sample_rate)
    assert result.arrival_time_s < echo_start / sample_rate
    assert result.peak_value == pytest.approx(0.35 * np.dot(chirp, chirp), rel=0.02)


def test_estimates_relative_arrivals_for_multiple_microphones():
    sample_rate = 16_000
    rng = np.random.default_rng(7)
    chirp = rng.normal(size=256)
    starts = (2_000, 2_037, 1_981)
    recordings = []
    for start in starts:
        signal = rng.normal(scale=0.0001, size=sample_rate // 2)
        signal[start : start + chirp.size] += chirp
        recordings.append(signal)

    delays, arrivals = estimate_chirp_tdoa(
        recordings,
        chirp,
        sample_rate,
        search_window_s=(0.05, 0.2),
        noise_window_s=(0.0, 0.04),
    )

    assert delays[0] == pytest.approx(0.0, abs=1 / sample_rate)
    assert delays[1] == pytest.approx((starts[1] - starts[0]) / sample_rate, abs=1 / sample_rate)
    assert delays[2] == pytest.approx((starts[2] - starts[0]) / sample_rate, abs=1 / sample_rate)
    assert len(arrivals) == len(recordings)


def test_raises_when_no_peak_clears_the_noise_threshold():
    sample_rate = 8_000
    rng = np.random.default_rng(1)
    chirp = rng.normal(size=128)
    recording = rng.normal(scale=0.001, size=sample_rate)

    with pytest.raises(ValueError, match="no chirp arrival"):
        estimate_chirp_arrival(
            recording,
            chirp,
            sample_rate,
            search_window_s=(0.2, 0.4),
            noise_window_s=(0.0, 0.1),
        )
