"""Test to demonstrate reflection handling with onset windowing."""
import numpy as np
from src.Simulation.signals import AudioSource, make_chirp, simulate_room
from src.Algorithm.tdoa import estimate_tdoa, estimate_tdoa_with_onset_window
from src.Algorithm.solver import solve_position


def main():
    # Setup
    sample_rate = 16_000
    room_dimensions = (5.0, 4.0, 3.0)
    phone_positions = np.array([
        (0.5, 0.5, 0.5),
        (4.5, 0.5, 0.5),
        (0.5, 3.5, 0.5),
        (2.5, 2.0, 2.8),
    ], dtype=np.float64)
    source_position = np.array((2.3, 1.8, 1.6), dtype=np.float64)
    chirp = make_chirp(sample_rate, duration_s=0.08)
    max_phone_spacing = float(np.max(
        np.linalg.norm(phone_positions[:, None, :] - phone_positions[None, :, :], axis=2)
    ))
    max_delay_s = max_phone_spacing / 343.0

    print("=== Test WITH reverberation (RT60=0.3) ===")
    # With reverberation
    sim_reverb = simulate_room(
        room_dimensions=room_dimensions,
        microphone_positions=phone_positions,
        sources=(AudioSource(source_position, chirp),),
        sample_rate=sample_rate,
        reverberation_time_s=0.3,  # WITH reflections
        snr_db=None,
    )

    # Test 1: No windowing (full recording with reflections)
    tdoa_full = estimate_tdoa(
        sim_reverb.microphone_signals,
        sample_rate,
        max_delay_s=max_delay_s,
    )
    loc_full = solve_position(phone_positions, tdoa_full, room_dimensions=room_dimensions)
    error_full = np.linalg.norm(np.array(loc_full.position) - source_position)
    print(f"Full recording (with reflections): error = {error_full:.4f} m")
    print(f"  TDOA delays: {[f'{d*1000:.2f}' for d in tdoa_full.delays_seconds]} ms")

    # Test 2: With onset windowing (using new convenience function)
    tdoa_windowed, window = estimate_tdoa_with_onset_window(
        sim_reverb.microphone_signals,
        sample_rate,
        max_inter_mic_delay_s=max_delay_s,
    )
    loc_windowed = solve_position(phone_positions, tdoa_windowed, room_dimensions=room_dimensions)
    error_windowed = np.linalg.norm(np.array(loc_windowed.position) - source_position)
    print(f"With onset windowing (new function): error = {error_windowed:.4f} m")
    print(f"  Window: {window[0]:.4f}-{window[1]:.4f} s")
    print(f"  TDOA delays: {[f'{d*1000:.2f}' for d in tdoa_windowed.delays_seconds]} ms")

    # Test 3: Direct path only (for comparison)
    sim_direct = simulate_room(
        room_dimensions=room_dimensions,
        microphone_positions=phone_positions,
        sources=(AudioSource(source_position, chirp),),
        sample_rate=sample_rate,
        reverberation_time_s=None,  # NO reflections
        snr_db=None,
    )
    tdoa_direct = estimate_tdoa(
        sim_direct.microphone_signals,
        sample_rate,
        max_delay_s=max_delay_s,
    )
    loc_direct = solve_position(phone_positions, tdoa_direct, room_dimensions=room_dimensions)
    error_direct = np.linalg.norm(np.array(loc_direct.position) - source_position)
    print(f"Direct path only (no reflections): error = {error_direct:.4f} m")
    print(f"  TDOA delays: {[f'{d*1000:.2f}' for d in tdoa_direct.delays_seconds]} ms")


if __name__ == "__main__":
    main()