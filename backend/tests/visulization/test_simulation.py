"""Smoke tests for the Pyroomacoustics signal simulator.


Run from the backend directory with:
    python -m unittest discover -s tests -v
"""


from __future__ import annotations


import unittest


import numpy as np


from src.Algorithm.gcc_phat import estimate_delay, estimate_delay_candidates
from src.Algorithm.onset import detect_onset, shared_onset_window
from src.Algorithm.solver import solve_position
from src.Algorithm.tdoa import estimate_tdoa, estimate_tdoa_frame_consensus
from src.Simulation.signals import AudioSource, make_chirp, simulate_room




class RoomSimulationTests(unittest.TestCase):
    def test_onset_detector_uses_quiet_calibration_and_hysteresis(self) -> None:
        sample_rate = 8_000
        rng = np.random.default_rng(7)
        signal = 0.002 * rng.normal(size=sample_rate)
        event_start = int(0.25 * sample_rate)
        time = np.arange(2_000, dtype=np.float64) / sample_rate
        signal[event_start : event_start + time.size] += 0.2 * np.sin(
            2.0 * np.pi * 330.0 * time
        )


        detection = detect_onset(
            signal,
            sample_rate,
            noise_window_s=(0.0, 0.15),
            consecutive_frames=4,
        )


        self.assertAlmostEqual(detection.onset_time_s, 0.25, delta=0.01)
        self.assertGreater(detection.threshold_rms, detection.release_threshold_rms)
        self.assertGreater(detection.release_threshold_rms, detection.background_rms)


    def test_delay_and_tdoa_use_shared_time_window(self) -> None:
        sample_rate = 8_000
        rng = np.random.default_rng(42)
        chirp = rng.normal(size=256)
        signal_a = np.zeros(2_000, dtype=np.float64)
        signal_b = np.zeros(2_000, dtype=np.float64)
        signal_a[800:1_056] = chirp
        signal_b[807:1_063] = chirp
        time_window_s = (0.09, 0.14)


        pair_estimate = estimate_delay(
            signal_a,
            signal_b,
            sample_rate,
            max_delay_s=0.01,
            time_window_s=time_window_s,
        )
        tdoa = estimate_tdoa(
            (signal_a, signal_b),
            sample_rate,
            max_delay_s=0.01,
            time_window_s=time_window_s,
        )


        self.assertAlmostEqual(pair_estimate.delay_seconds, 7 / sample_rate, delta=1 / sample_rate)
        self.assertEqual(tdoa.delays_seconds[0], 0.0)
        self.assertAlmostEqual(tdoa.delays_seconds[1], 7 / sample_rate, delta=1 / sample_rate)


    def test_speech_delay_uses_partial_phat_and_band_limit(self) -> None:
        sample_rate = 8_000
        rng = np.random.default_rng(19)
        signal_a = np.zeros(2_000, dtype=np.float64)
        signal_b = np.zeros_like(signal_a)
        speech_like = rng.normal(size=512)
        signal_a[700:1_212] = speech_like
        signal_b[707:1_219] = speech_like

        estimate = estimate_delay(
            signal_a,
            signal_b,
            sample_rate,
            max_delay_s=0.01,
            phat_beta=0.7,
            frequency_band_hz=(300.0, 3_400.0),
        )

        self.assertAlmostEqual(
            estimate.delay_seconds,
            7 / sample_rate,
            delta=1 / sample_rate,
        )


    def test_delay_rejects_invalid_phat_beta(self) -> None:
        signal = np.arange(100, dtype=np.float64)
        with self.assertRaises(ValueError):
            estimate_delay(signal, signal, 8_000, phat_beta=0.0)


    def test_gcc_phat_returns_multiple_physical_peak_candidates(self) -> None:
        rng = np.random.default_rng(23)
        signal_a = rng.normal(size=4_000)
        signal_b = np.zeros_like(signal_a)
        signal_b[7:] = signal_a[:-7]

        candidates = estimate_delay_candidates(
            signal_a,
            signal_b,
            8_000,
            max_delay_s=0.01,
            candidate_count=4,
        )

        self.assertGreaterEqual(len(candidates), 2)
        self.assertAlmostEqual(candidates[0].delay_seconds, 7 / 8_000, delta=1 / 8_000)


    def test_frame_consensus_recovers_delay_across_speech_frames(self) -> None:
        rng = np.random.default_rng(31)
        signal_a = rng.normal(size=8_000)
        signal_b = np.zeros_like(signal_a)
        signal_b[8:] = signal_a[:-8]

        result = estimate_tdoa_frame_consensus(
            (signal_a, signal_b),
            8_000,
            max_delay_s=0.01,
            time_window_s=(0.1, 0.8),
            frame_duration_s=0.1,
            frame_hop_s=0.05,
            frequency_band_hz=None,
        )

        self.assertAlmostEqual(result.delays_seconds[1], 8 / 8_000, delta=1 / 8_000)


    def test_delay_rejects_invalid_time_window(self) -> None:
        signal = np.ones(100, dtype=np.float64)
        with self.assertRaises(ValueError):
            estimate_delay(signal, signal, 8_000, time_window_s=(0.02, 0.01))


    def test_onset_window_is_shared_and_preserves_arrival_delay(self) -> None:
        sample_rate = 8_000
        chirp = make_chirp(sample_rate, duration_s=0.08)
        onset_sample = 2_000
        delay_samples = 16
        signal_a = np.zeros(8_000, dtype=np.float64)
        signal_b = np.zeros_like(signal_a)
        signal_a[onset_sample : onset_sample + chirp.size] = chirp
        signal_b[
            onset_sample + delay_samples : onset_sample + delay_samples + chirp.size
        ] = chirp


        time_window_s, detections = shared_onset_window(
            (signal_a, signal_b),
            sample_rate,
            max_inter_mic_delay_s=0.01,
            pre_roll_s=0.01,
            event_duration_s=0.1,
            noise_window_s=(0.0, 0.1),
        )


        self.assertEqual(len(detections), 2)
        self.assertLessEqual(time_window_s[0], onset_sample / sample_rate)
        self.assertGreater(
            time_window_s[1],
            (onset_sample + delay_samples + chirp.size) / sample_rate,
        )
        tdoa = estimate_delay(
            signal_a,
            signal_b,
            sample_rate,
            max_delay_s=0.01,
            time_window_s=time_window_s,
        )
        self.assertAlmostEqual(
            tdoa.delay_seconds,
            delay_samples / sample_rate,
            delta=1 / sample_rate,
        )

    def test_shared_onset_window_ignores_single_false_early_trigger(self) -> None:
        sample_rate = 8_000
        signals = [np.zeros(8_000, dtype=np.float64) for _ in range(4)]
        time = np.arange(400, dtype=np.float64) / sample_rate
        burst = 0.3 * np.sin(2.0 * np.pi * 440.0 * time)
        signals[0][800:1_200] = burst
        for signal in signals[1:]:
            signal[3_360:3_760] = burst

        window, detections = shared_onset_window(
            tuple(signals),
            sample_rate,
            max_inter_mic_delay_s=0.02,
            pre_roll_s=0.005,
            event_duration_s=0.03,
        )

        self.assertLess(detections[0].onset_time_s, 0.15)
        self.assertTrue(all(d.onset_time_s > 0.4 for d in detections[1:]))
        self.assertGreater(window[0], 0.37)
        self.assertGreater(window[1], 0.42)


    def test_simulates_multiple_speakers_at_four_phones(self) -> None:
        sample_rate = 16_000
        chirp = make_chirp(sample_rate, duration_s=0.08)
        tone_time = np.arange(4_000, dtype=np.float64) / sample_rate
        tone = 0.3 * np.sin(2.0 * np.pi * 440.0 * tone_time)


        room_dimensions = (5.0, 4.0, 3.0)
        phone_positions = (
            (1.0, 1.0, 1.2),
            (4.0, 1.0, 1.2),
            (4.0, 3.0, 1.2),
            (1.0, 3.0, 1.2),
            (1.5, 2.0, 1.2),
        )
        speakers = (
            AudioSource(position=(1.5, 2.0, 1.5), signal=chirp),
            AudioSource(position=(3.5, 2.0, 1.5), signal=tone, delay_s=0.2),
        )


        result = simulate_room(
            room_dimensions=room_dimensions,
            microphone_positions=phone_positions,
            sources=speakers,
            sample_rate=sample_rate,
            # Begin with direct sound so the known geometric delays provide a
            # clean baseline for validating the localization algorithms.
            reverberation_time_s=None,
            snr_db=None,
        )


        self.assertEqual(result.sample_rate, sample_rate)
        self.assertEqual(result.microphone_signals.ndim, 2)
        self.assertEqual(result.microphone_signals.shape[0], len(phone_positions))
        self.assertEqual(result.source_contributions.shape[0], 2)
        self.assertEqual(result.source_contributions.shape[1], len(phone_positions))
        self.assertEqual(result.microphone_positions.shape, (len(phone_positions), 3))
        self.assertEqual(result.source_positions.shape, (2, 3))
        self.assertTrue(np.isfinite(result.microphone_signals).all())


        # With no added noise, the mixed phone recording is the sum of all
        # independently simulated speaker contributions.
        np.testing.assert_allclose(
            result.microphone_signals,
            result.source_contributions.sum(axis=0),
            rtol=1e-10,
            atol=1e-10,
        )


        # The overall recording contains two speakers, so use the simulator's
        # isolated chirp contribution for this single-source localization check.
        chirp_at_phones = result.source_contributions[0]
        max_phone_spacing = np.max(
            np.linalg.norm(
                result.microphone_positions[:, None, :]
                - result.microphone_positions[None, :, :],
                axis=2,
            )
        )
        max_delay_s = max_phone_spacing / 343.0


        pair_estimate = estimate_delay(
            chirp_at_phones[0],
            chirp_at_phones[1],
            sample_rate,
            max_delay_s=max_delay_s,
        )
        tdoa = estimate_tdoa(
            chirp_at_phones,
            sample_rate,
            max_delay_s=max_delay_s,
        )


        # Positive means mic 1 is farther from this chirp source than mic 0.
        source_position = result.source_positions[0]
        ranges = np.linalg.norm(
            result.microphone_positions - source_position,
            axis=1,
        )
        expected_delays = (ranges - ranges[0]) / 343.0
        tolerance_s = 1.0 / sample_rate
        self.assertGreater(pair_estimate.peak_value, 0.0)
        self.assertAlmostEqual(
            pair_estimate.delay_seconds,
            expected_delays[1],
            delta=tolerance_s,
        )
        self.assertEqual(tdoa.reference_index, 0)
        self.assertEqual(tdoa.delays_seconds[0], 0.0)
        np.testing.assert_allclose(
            tdoa.delays_seconds,
            expected_delays,
            atol=tolerance_s,
            rtol=0.0,
        )


        print("\nSimulation test results")
        print("=" * 72)
        print(f"Room dimensions: {room_dimensions} m")
        print(f"Sample rate: {sample_rate:,} Hz")
        print(f"Recording duration: {result.microphone_signals.shape[1] / sample_rate:.3f} s")
        print(f"Phones: {len(phone_positions)}; speakers: {len(speakers)}")
        print(f"Mixed recordings shape: {result.microphone_signals.shape} (phones, samples)")
        print(
            "Source contributions shape: "
            f"{result.source_contributions.shape} (sources, phones, samples)"
        )
        print(
            "Chirp source position: "
            f"{tuple(float(value) for value in source_position)} m"
        )
        print(
            "\nTDOA relative to phone 0 "
            "(positive means arrival later than the reference):"
        )
        print("Phone | Position (m)                    | Expected (ms) | Estimated (ms) | Error (samples)")
        print("-" * 88)
        for index, (position, expected, estimated) in enumerate(
            zip(result.microphone_positions, expected_delays, tdoa.delays_seconds)
        ):
            error_samples = (estimated - expected) * sample_rate
            position_tuple = tuple(float(value) for value in position)
            print(
                f"{index:5d} | {str(position_tuple):31s} | "
                f"{expected * 1_000:12.4f} | {estimated * 1_000:14.4f} | "
                f"{error_samples:14.3f}"
            )
        print("\nGCC-PHAT check: phone 0 vs phone 1")
        print(f"  Estimated delay: {pair_estimate.delay_seconds * 1_000:.4f} ms")
        print(f"  Expected delay:  {expected_delays[1] * 1_000:.4f} ms")
        print(f"  Peak magnitude:  {pair_estimate.peak_value:.6g}")
        print(f"  Peak/sidelobe:   {pair_estimate.peak_to_sidelobe_ratio:.2f}")
        maximum_error_samples = np.max(
            np.abs(np.asarray(tdoa.delays_seconds) - expected_delays)
        ) * sample_rate
        print(f"  Maximum TDOA error: {maximum_error_samples:.3f} samples")


    def test_solver_recovers_simulated_3d_source_position(self) -> None:
        sample_rate = 16_000
        room_dimensions = (5.0, 4.0, 3.0)
        phone_positions = np.array(
            (
                (0.5, 0.5, 0.5),
                (4.5, 0.5, 0.5),
                (0.5, 3.5, 0.5),
                (2.5, 2.0, 2.8),
            ),
            dtype=np.float64,
        )
        known_source_position = np.array((2.3, 1.8, 1.6), dtype=np.float64)
        chirp = make_chirp(sample_rate, duration_s=0.08)


        simulation = simulate_room(
            room_dimensions=room_dimensions,
            microphone_positions=phone_positions,
            sources=(AudioSource(tuple(known_source_position), chirp),),
            sample_rate=sample_rate,
            reverberation_time_s=None,
            snr_db=None,
        )
        tdoa = estimate_tdoa(
            simulation.source_contributions[0],
            sample_rate,
            max_delay_s=0.02,
        )
        localization = solve_position(
            simulation.microphone_positions,
            tdoa,
            room_dimensions=room_dimensions,
        )


        position_error_m = float(
            np.linalg.norm(np.asarray(localization.position) - known_source_position)
        )
        self.assertTrue(localization.success, localization.message)
        self.assertLess(position_error_m, 0.01)


        print("\n3D localization solver test")
        print(
            "  Known source position:    "
            f"{tuple(float(value) for value in known_source_position)} m"
        )
        print(f"  Estimated source position: {localization.position} m")
        print(f"  Position error: {position_error_m:.4f} m")
        print(f"  TDOA RMS residual: {localization.rms_error_seconds * 1_000_000:.4f} us")




if __name__ == "__main__":
    unittest.main(verbosity=2)



