"""Test with source_contributions (clean per-source signals)."""
import numpy as np
from src.Simulation.signals import AudioSource, make_chirp, simulate_room
from src.Algorithm.tdoa import estimate_tdoa
from src.Algorithm.onset import detect_onset
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
    max_phone_spacing = float(np.max(
        np.linalg.norm(phone_positions[:, None, :] - phone_positions[None, :, :], axis=2)
    ))
    max_delay_s = max_phone_spacing / 343.0

    # Simulate with reverberation
    sim = simulate_room(
        room_dimensions=room_dimensions,
        microphone_positions=phone_positions,
        sources=(AudioSource(source_position, chirp),),
        sample_rate=sample_rate,
        reverberation_time_s=0.3,
        snr_db=None,
    )

    print("microphone_signals shape:", sim.microphone_signals.shape)
    print("source_contributions shape:", sim.source_contributions.shape)
    print("source_contributions[0] shape:", sim.source_contributions[0].shape)

    # Test onset on source_contributions (clean per-source per-mic)
    print("\n--- Onset on source_contributions[0] ---")
    for i in range(4):
        sig = sim.source_contributions[0, i]
        det = detect_onset(sig, sample_rate, noise_window_s=(0.0, 0.02))
        print("Mic {}: onset = {:.1f} ms".format(i, det.onset_time_s * 1000))

    # Test TDOA on source_contributions[0] (clean signals)
    window, detections = shared_onset_window(
        tuple(sim.source_contributions[0]),
        sample_rate,
        max_delay_s,
        pre_roll_s=0.005,
        event_duration_s=0.15,
    )
    print("\nWindow from source_contributions: {:.4f}-{:.4f} s".format(window[0], window[1]))
    print("Detections: {}".format([f"M{i}={d.onset_time_s:.4f}s" for i, d in enumerate(detections)]))

    tdoa = estimate_tdoa(sim.source_contributions[0], sample_rate, max_delay_s=max_delay_s, time_window_s=window)
    loc = solve_position(phone_positions, tdoa, room_dimensions=room_dimensions)
    error = np.linalg.norm(np.array(loc.position) - source_position)
    tdoa_str = ", ".join("{:.2f}".format(d * 1000) for d in tdoa.delays_seconds)
    print("source_contributions TDOA: error = {:.4f} m, TDOA = [{}] ms".format(error, tdoa_str))

    # Also test full source_contributions without window
    tdoa_full = estimate_tdoa(sim.source_contributions[0], sample_rate, max_delay_s=max_delay_s)
    loc_full = solve_position(phone_positions, tdoa_full, room_dimensions=room_dimensions)
    error_full = np.linalg.norm(np.array(loc_full.position) - source_position)
    tdoa_str = ", ".join("{:.2f}".format(d * 1000) for d in tdoa_full.delays_seconds)
    print("source_contributions full: error = {:.4f} m, TDOA = [{}] ms".format(error_full, tdoa_str))


if __name__ == "__main__":
    main()