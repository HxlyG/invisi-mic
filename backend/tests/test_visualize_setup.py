"""Test to debug visualization script onset windowing with reverberation."""
import numpy as np
from src.Simulation.signals import AudioSource, make_chirp, simulate_room
from src.Algorithm.tdoa import estimate_tdoa, estimate_tdoa_with_onset_window
from src.Algorithm.onset import shared_onset_window
from src.Algorithm.solver import solve_position


def main():
    # Setup - matching visualize_localization.py
    sample_rate = 16_000
    room_dimensions = (5.0, 4.0, 3.0)
    phone_positions = np.array([
        (0.5, 0.5, 0.5),
        (4.5, 0.5, 0.5),
        (0.5, 3.5, 0.5),
        (2.5, 2.0, 2.8),
    ], dtype=np.float64)
    
    # Test target 0 from visualization
    source_position = np.array((1.0, 1.0, 1.5), dtype=np.float64)
    chirp = make_chirp(sample_rate, duration_s=0.08)
    max_phone_spacing = float(np.max(
        np.linalg.norm(phone_positions[:, None, :] - phone_positions[None, :, :], axis=2)
    ))
    max_delay_s = max_phone_spacing / 343.0

    print(f"Max phone spacing: {max_phone_spacing:.3f} m")
    print(f"Max delay: {max_delay_s*1000:.2f} ms")
    print(f"Source: {source_position}")
    print(f"Mics: {phone_positions}")

    # Compute expected TDOAs
    for i, mic in enumerate(phone_positions):
        dist = np.linalg.norm(source_position - mic)
        print(f"  Mic {i} at {mic}: dist = {dist:.3f} m")
    ref_dist = np.linalg.norm(source_position - phone_positions[0])
    for i, mic in enumerate(phone_positions):
        dist = np.linalg.norm(source_position - mic)
        tdoa = (dist - ref_dist) / 343.0
        print(f"  Expected TDOA mic {i}: {tdoa*1000:.2f} ms")

    # Simulate with reverberation
    sim = simulate_room(
        room_dimensions=room_dimensions,
        microphone_positions=phone_positions,
        sources=(AudioSource(source_position, chirp),),
        sample_rate=sample_rate,
        reverberation_time_s=0.3,
        snr_db=None,
    )

    # Test 1: Full recording
    tdoa_full = estimate_tdoa(sim.microphone_signals, sample_rate, max_delay_s=max_delay_s)
    loc_full = solve_position(phone_positions, tdoa_full, room_dimensions=room_dimensions)
    error_full = np.linalg.norm(np.array(loc_full.position) - source_position)
    print(f"\nFull recording: error = {error_full:.4f} m")
    print(f"  TDOA: {[f'{d*1000:.2f}' for d in tdoa_full.delays_seconds]} ms")

    # Test 2: Onset windowing (default params like visualize script)
    window, detections = shared_onset_window(
        tuple(sim.microphone_signals),
        sample_rate,
        max_delay_s,
        pre_roll_s=0.005,
        event_duration_s=0.15,
    )
    print(f"\nOnset window: {window[0]:.4f}-{window[1]:.4f} s")
    print(f"Detections: {[f'M{i}={d.onset_time_s:.4f}s' for i, d in enumerate(detections)]}")
    
    tdoa_windowed = estimate_tdoa(sim.microphone_signals, sample_rate, max_delay_s=max_delay_s, time_window_s=window)
    loc_windowed = solve_position(phone_positions, tdoa_windowed, room_dimensions=room_dimensions)
    error_windowed = np.linalg.norm(np.array(loc_windowed.position) - source_position)
    print(f"With onset windowing: error = {error_windowed:.4f} m")
    print(f"  TDOA: {[f'{d*1000:.2f}' for d in tdoa_windowed.delays_seconds]} ms")

    # Test 3: New convenience function
    tdoa_new, window_new = estimate_tdoa_with_onset_window(
        sim.microphone_signals,
        sample_rate,
        max_inter_mic_delay_s=max_delay_s,
        pre_roll_s=0.005,
        event_duration_s=0.15,
    )
    loc_new = solve_position(phone_positions, tdoa_new, room_dimensions=room_dimensions)
    error_new = np.linalg.norm(np.array(loc_new.position) - source_position)
    print(f"\nNew function: error = {error_new:.4f} m")
    print(f"  Window: {window_new[0]:.4f}-{window_new[1]:.4f} s")
    print(f"  TDOA: {[f'{d*1000:.2f}' for d in tdoa_new.delays_seconds]} ms")

    # Test 4: Direct path only
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
    print(f"\nDirect path only: error = {error_direct:.4f} m")
    print(f"  TDOA: {[f'{d*1000:.2f}' for d in tdoa_direct.delays_seconds]} ms")


if __name__ == "__main__":
    main()