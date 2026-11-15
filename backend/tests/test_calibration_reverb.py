import numpy as np
import pytest

from src.Algorithm.calibration import localize_chirp_source
from src.Simulation.signals import AudioSource, make_chirp, simulate_room


def test_first_arrival_tdoa_matches_direct_path_in_reverberant_room():
    sample_rate = 16_000
    room_dimensions = (5.0, 4.0, 3.0)
    microphone_positions = np.array(
        [
            (0.5, 0.5, 0.5),
            (4.5, 0.5, 0.5),
            (0.5, 3.5, 0.5),
            (2.5, 2.0, 2.8),
        ],
        dtype=np.float64,
    )
    source_position = np.array((2.3, 1.8, 1.6), dtype=np.float64)
    chirp = make_chirp(
        sample_rate,
        duration_s=0.02,
        start_hz=1_500,
        end_hz=7_000,
    )
    emission_delay_s = 0.1
    simulation = simulate_room(
        room_dimensions,
        microphone_positions,
        (AudioSource(source_position, chirp, delay_s=emission_delay_s),),
        sample_rate=sample_rate,
        reverberation_time_s=0.45,
        snr_db=35,
        noise_seed=42,
    )

    result = localize_chirp_source(
        list(simulation.microphone_signals),
        chirp,
        sample_rate,
        microphone_positions,
        room_dimensions=room_dimensions,
        search_window_s=(0.1, 0.2),
        noise_window_s=(0.0, 0.07),
        min_peak_ratio=0.05,
    )

    direct_arrivals = emission_delay_s + np.linalg.norm(
        microphone_positions - source_position, axis=1
    ) / 343.0
    expected_delays = direct_arrivals - direct_arrivals[0]

    assert len(result.arrivals) == len(microphone_positions)
    assert result.delays_seconds == pytest.approx(expected_delays, abs=0.003)
    assert np.linalg.norm(np.asarray(result.localization.position) - source_position) < 0.75
