"""Estimate microphone arrival-time differences from a group of recordings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
from numpy.typing import ArrayLike

from .gcc_phat import DelayEstimate, estimate_delay, estimate_delay_candidates
from .onset import shared_onset_window


@dataclass(frozen=True)
class TDOAResult:
    """Arrival delays relative to one reference microphone.

    ``delays_seconds`` and ``estimates`` are in the same order as the input
    signals. The reference microphone has a delay of zero and no estimate.
    Positive delays mean that microphone received the sound later than the
    reference microphone.
    """

    reference_index: int
    delays_seconds: tuple[float, ...]
    estimates: tuple[DelayEstimate | None, ...]
    consensus_fraction: tuple[float, ...] | None = None


def estimate_tdoa(
	signals: Sequence[ArrayLike],
	sample_rate: float,
	*,
	reference_index: int = 0,
	max_delay_s: float | None = None,
	interpolation: int = 16,
	time_window_s: tuple[float, float] | None = None,
        phat_beta: float = 1.0,
        frequency_band_hz: tuple[float, float] | None = None,
) -> TDOAResult:
	"""Estimate each microphone's arrival delay relative to a reference.

	The recordings should contain the same isolated event (for example, the
	session chirp) and already be aligned to a common sample-rate basis.
	Inter-device clock offsets and audio-pipeline latency must be calibrated
	separately; this function cannot distinguish those from acoustic delay.

	Args:
		signals: One one-dimensional recording per microphone.
		sample_rate: Shared sample rate in samples per second.
		reference_index: Index of the microphone used as the timing reference.
		max_delay_s: Optional maximum physical delay to search, in seconds.
		interpolation: Frequency-domain interpolation factor passed to
			:func:`estimate_delay`.
		time_window_s: Optional shared ``(start, end)`` recording interval in
			seconds, passed unchanged to every pairwise delay estimate.
        phat_beta: GCC-PHAT whitening exponent passed to :func:`estimate_delay`.
        frequency_band_hz: Optional frequency band passed to :func:`estimate_delay`.

	Returns:
		A result with delays ordered to match ``signals``.

	Raises:
		ValueError: If fewer than two recordings are given or the reference
			index is out of range. Invalid signals are rejected by
			:func:`estimate_delay`.
	"""
	if len(signals) < 2:
		raise ValueError("at least two microphone signals are required")
	if isinstance(reference_index, bool) or not isinstance(reference_index, int):
		raise ValueError("reference_index must be an integer")
	if not 0 <= reference_index < len(signals):
		raise ValueError("reference_index is outside the signals sequence")

	reference_signal = signals[reference_index]
	delays = [0.0] * len(signals)
	estimates: list[DelayEstimate | None] = [None] * len(signals)

	for microphone_index, signal in enumerate(signals):
		if microphone_index == reference_index:
			continue
		estimate = estimate_delay(
			reference_signal,
			signal,
			sample_rate,
			max_delay_s=max_delay_s,
			interpolation=interpolation,
			time_window_s=time_window_s,
            phat_beta=phat_beta,
            frequency_band_hz=frequency_band_hz,
		)
		delays[microphone_index] = estimate.delay_seconds
		estimates[microphone_index] = estimate

	return TDOAResult(
		reference_index=reference_index,
		delays_seconds=tuple(delays),
		estimates=tuple(estimates),
	)


def estimate_tdoa_with_onset_window(
    signals: Sequence[ArrayLike],
    sample_rate: float,
    max_inter_mic_delay_s: float,
    *,
    reference_index: int = 0,
    max_delay_s: float | None = None,
    interpolation: int = 16,
    pre_roll_s: float = 0.005,
    event_duration_s: float = 0.03,
    noise_window_s: tuple[float, float] | None = None,
    phat_beta: float = 0.7,
    frequency_band_hz: tuple[float, float] | None = (300.0, 3_400.0),
) -> tuple[TDOAResult, tuple[float, float]]:
    """Estimate TDOA with automatic onset-based windowing for reflection robustness.

    This function detects sustained energy onsets across microphones, takes one
    shared short crop, then runs physically bounded GCC-PHAT with optional
    partial whitening and band-pass filtering. The crop can reduce late-reverb
    influence but does not guarantee that the selected peak is the direct path.

    Use this for real hardware recordings in reverberant environments where the
    direct path must be isolated from reflections.

    Args:
        signals: One one-dimensional recording per microphone. All must have
            equal length and shared sample rate.
        sample_rate: Shared sample rate in samples per second.
        max_inter_mic_delay_s: Maximum propagation delay between any two
            microphones (room diagonal / speed of sound). Used to size the
            analysis window.
        reference_index: Index of the microphone used as the timing reference.
        max_delay_s: Optional maximum physical delay to search, in seconds.
            Defaults to ``max_inter_mic_delay_s`` if not provided.
        interpolation: Frequency-domain interpolation factor for sub-sample
            delay estimates. Larger values increase computation.
        pre_roll_s: Seconds to include before the earliest detected onset.
            Captures the direct-path arrival at the reference microphone.
        event_duration_s: Duration of the acoustic event (e.g., chirp length).
            Added to the window to capture the full direct-path signal at
            the farthest microphone.
        noise_window_s: Optional known quiet ``(start, end)`` interval in seconds
            for background energy calibration. Improves onset detection in noise.
        phat_beta: Partial-whitening exponent; 0.7 is a speech-oriented starting
            point, not a universally optimal value.
        frequency_band_hz: Optional speech band-pass limits. Set to ``None`` to
            disable filtering.

    Returns:
        A tuple of ``(TDOAResult, analysis_window_s)`` where the second element
        is the ``(start, end)`` window in seconds that was used for the TDOA
        estimation. This window captures the direct-path arrivals at all mics.

    Raises:
        ValueError: If fewer than two recordings are given, the reference index
            is out of range, or no sustained onset is detected.
    """
    if max_delay_s is None:
        max_delay_s = max_inter_mic_delay_s

    # Detect onsets and create a shared window capturing the direct path
    analysis_window, _detections = shared_onset_window(
        tuple(signals),
        int(round(sample_rate)),
        max_inter_mic_delay_s,
        pre_roll_s=pre_roll_s,
        event_duration_s=event_duration_s,
        noise_window_s=noise_window_s,
    )

    # Run TDOA on the windowed signals
    tdoa = estimate_tdoa(
        signals,
        sample_rate,
        reference_index=reference_index,
        max_delay_s=max_delay_s,
        interpolation=interpolation,
        time_window_s=analysis_window,
        phat_beta=phat_beta,
        frequency_band_hz=frequency_band_hz,
    )

    return tdoa, analysis_window


def estimate_tdoa_frame_consensus(
    signals: Sequence[ArrayLike],
    sample_rate: float,
    *,
    max_delay_s: float,
    time_window_s: tuple[float, float],
    reference_index: int = 0,
    frame_duration_s: float = 0.08,
    frame_hop_s: float = 0.04,
    candidate_count: int = 5,
    consensus_tolerance_s: float = 0.001,
    interpolation: int = 16,
    phat_beta: float = 0.7,
    frequency_band_hz: tuple[float, float] | None = (300.0, 3_400.0),
) -> TDOAResult:
    """Estimate speech TDOA from lag peaks recurring across overlapping frames.

    Each frame retains several physically bounded GCC-PHAT peaks. For each
    microphone pair, the selected delay is the median of the densest cluster of
    peaks recurring across distinct frames, rather than the strongest peak in a
    single crop. This is a practical reflection-robust heuristic, not a guarantee
    of direct-path recovery; stable reflections can also recur across frames.
    """
    if len(signals) < 2:
        raise ValueError("at least two microphone signals are required")
    if not 0 <= reference_index < len(signals):
        raise ValueError("reference_index is outside the signals sequence")
    if not np.isfinite(sample_rate) or sample_rate <= 0:
        raise ValueError("sample_rate must be a positive finite number")
    if not np.isfinite(max_delay_s) or max_delay_s < 0:
        raise ValueError("max_delay_s must be non-negative and finite")
    if not np.isfinite(frame_duration_s) or frame_duration_s <= 0:
        raise ValueError("frame_duration_s must be positive and finite")
    if not np.isfinite(frame_hop_s) or frame_hop_s <= 0:
        raise ValueError("frame_hop_s must be positive and finite")
    if not np.isfinite(consensus_tolerance_s) or consensus_tolerance_s <= 0:
        raise ValueError("consensus_tolerance_s must be positive and finite")
    start_s, end_s = time_window_s
    if start_s < 0 or end_s <= start_s or not np.isfinite(end_s):
        raise ValueError("time_window_s must satisfy 0 <= start < end")
    if end_s - start_s < frame_duration_s:
        raise ValueError("analysis window must contain at least one complete frame")
    frame_starts = np.arange(start_s, end_s - frame_duration_s + 1e-12, frame_hop_s)
    if frame_starts.size == 0:
        raise ValueError("analysis window must contain at least one complete frame")
    delays = [0.0] * len(signals)
    estimates: list[DelayEstimate | None] = [None] * len(signals)
    consensus = [1.0 if index == reference_index else 0.0 for index in range(len(signals))]
    for mic_index, signal in enumerate(signals):
        if mic_index == reference_index:
            continue
        frame_candidates: list[tuple[int, DelayEstimate]] = []
        for frame_index, frame_start in enumerate(frame_starts):
            try:
                candidates = estimate_delay_candidates(
                    signals[reference_index], signal, sample_rate,
                    max_delay_s=max_delay_s,
                    interpolation=interpolation,
                    time_window_s=(float(frame_start), float(frame_start + frame_duration_s)),
                    phat_beta=phat_beta,
                    frequency_band_hz=frequency_band_hz,
                    candidate_count=candidate_count,
                )
            except ValueError:
                continue
            frame_candidates.extend((frame_index, item) for item in candidates)
        if not frame_candidates:
            raise ValueError(f"no usable GCC-PHAT frames for microphone {mic_index}")
        best_cluster: list[tuple[int, DelayEstimate]] = []
        for _frame, anchor in frame_candidates:
            cluster: list[tuple[int, DelayEstimate]] = []
            for frame_index in range(len(frame_starts)):
                within_tolerance = [
                    item
                    for item_frame, item in frame_candidates
                    if item_frame == frame_index
                    and abs(item.delay_seconds - anchor.delay_seconds) <= consensus_tolerance_s
                ]
                if within_tolerance:
                    cluster.append(
                        (
                            frame_index,
                            min(
                                within_tolerance,
                                key=lambda item: abs(item.delay_seconds - anchor.delay_seconds),
                            ),
                        )
                    )
            unique_frames = {item_frame for item_frame, _item in cluster}
            best_frames = {item_frame for item_frame, _item in best_cluster}
            cluster_quality = sum(item.peak_to_sidelobe_ratio for _i, item in cluster) / len(cluster)
            best_quality = (
                sum(item.peak_to_sidelobe_ratio for _i, item in best_cluster) / len(best_cluster)
                if best_cluster else -1.0
            )
            if len(unique_frames) > len(best_frames) or (
                len(unique_frames) == len(best_frames) and cluster_quality > best_quality
            ):
                best_cluster = cluster
        selected_delays = np.asarray([item.delay_seconds for _i, item in best_cluster])
        delays[mic_index] = float(np.median(selected_delays))
        consensus[mic_index] = len({frame for frame, _item in best_cluster}) / len(frame_starts)
        best_peak = max(item.peak_value for _i, item in best_cluster)
        best_ratio = float(np.median([item.peak_to_sidelobe_ratio for _i, item in best_cluster]))
        estimates[mic_index] = DelayEstimate(delays[mic_index], best_peak, best_ratio)
    return TDOAResult(
        reference_index,
        tuple(delays),
        tuple(estimates),
        tuple(consensus),
    )
