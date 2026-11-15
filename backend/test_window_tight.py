"""Test tighter onset windowing."""
import numpy as np
from src.Simulation.signals import AudioSource, make_chirp, simulate_room
from src.Algorithm.tdoa import estimate_tdoa
from src.Algorithm.onset import shared_onset_window, detect_onset
from src.Algorithm.solver import solve_position


def main():
    sample_rate = 16_000
    room_dimensions = (5.0, 4.0, 3.0)
    phone_positions = np.array([
        (0.5, 0.5, 0.5),
        (4.5, 0.5, 0.5),
        (0.5, 3.5, 0.5),
        (2.5, 2.0, 2.8),
    ], dtype=np.float64)
    source_position = np.array((1.0, 1.0, 1.5), dtype=np.float64)
    chirp = make_chirp(sample_rate, duration_s=0.08)
    chirp_duration = 0.08
    max_phone_spacing = float(np.max(
        np.linalg.norm(phone_positions[:, None, :] - phone_positions[None, :, :], axis=2)
    ))
    max_delay_s = max_phone_spacing / 343.0

    sim = simulate_room(
        room_dimensions=room_dimensions,
        microphone_positions=phone_positions,
        sources=(AudioSource(source_position, chirp),),
        sample_rate=sample_rate,
        reverberation_time_s=0.3,
        snr_db=None,
    )

    # Individual onset detection
    for i, sig in enumerate(sim.microphone_signals):
        det = detect_onset(sig, sample_rate, noise_window_s=(0.0, 0.02))
        print("Mic {}: onset = {:.1f} ms".format(i, det.onset_time_s * 1000))

    window, detections = shared_onset_window(
        tuple(sim.microphone_signals),
        sample_rate,
        max_delay_s,
        pre_roll_s=0.005,
        event_duration_s=0.15,
    )
    print("Default window: {:.4f}-{:.4f} s ({:.1f} ms)".format(
        window[0], window[1], (window[1] - window[0]) * 1000))

    # Tight window
    earliest = min(d.onset_time_s for d in detections)
    tight_window = (
        max(0.0, earliest - 0.005),
        earliest + max_delay_s + chirp_duration + 0.005
    )
    print("Tight window: {:.4f}-{:.4f} s ({:.1f} ms)".format(
        tight_window[0], tight_window[1], (tight_window[1] - tight_window[0]) * 1000))

    # Even tighter
    tighter_window = (
        max(0.0, earliest - 0.005),
        earliest + max_delay_s + 0.01
    )
    print("Tighter window: {:.4f}-{:.4f} s ({:.1f} ms)".format(
        tighter_window[0], tighter_window[1], (tighter_window[1] - tighter_window[0]) * 1000))

    for name, w in [("default", window), ("tight", tight_window), ("tighter", tighter_window)]:
        tdoa = estimate_tdoa(sim.microphone_signals, sample_rate, max_delay_s=max_delay_s, time_window_s=w)
        loc = solve_position(phone_positions, tdoa, room_dimensions=room_dimensions)
        error = np.linalg.norm(np.array(loc.position) - source_position)
        tdoa_str = ", ".join("{:.2f}".format(d * 1000) for d in tdoa.delays_seconds)
        print("{}: error = {:.4f} m, TDOA = [{}] ms".format(name, error, tdoa_str))

    # Direct path only
    sim_direct = simulate_room(
        room_dimensions=room_dimensions,
        microphone_positions=phone_positions,
        sources=(AudioSource(source_position, chirp),),
        sample_rate=sample_rate,
        reverberation_time_s=None,
        snr_db=None,
    )
    tdoa_direct = estimate_tdoa(sim_direct.microphone_signals, sample_rate, max_delay_s=max_delay_s)
    loc_direct = solve_position(phone_positions, tdoa_direct, room_dimensions=room_dimensions)
    error_direct = np.linalg.norm(np.array(loc_direct.position) - source_position)
    tdoa_str = ", ".join("{:.2f}".format(d * 1000) for d in tdoa_direct.delays_seconds)
    print("Direct path only: error = {:.4f} m, TDOA = [{}] ms".format(error_direct, tdoa_str))


if __name__ == "__main__":
    main()