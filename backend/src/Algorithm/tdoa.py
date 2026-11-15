"""Estimate microphone arrival-time differences from a group of recordings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from numpy.typing import ArrayLike

from .gcc_phat import DelayEstimate, estimate_delay
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


def estimate_tdoa(
	signals: Sequence[ArrayLike],
	sample_rate: float,
	*,
	reference_index: int = 0,
	max_delay_s: float | None = None,
	interpolation: int = 16,
	time_window_s: tuple[float, float] | None = None,
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
    event_duration_s: float = 0.15,
    noise_window_s: tuple[float, float] | None = None,
) -> tuple[TDOAResult, tuple[float, float]]:
    """Estimate TDOA with automatic onset-based windowing for reflection robustness.

    This function first detects the onset (direct-path arrival) across all microphones
    using :func:`shared_onset_window`, then crops all signals to a shared window
    around that onset before running GCC-PHAT. This rejects late reflections and
    reverberation that would otherwise corrupt the delay estimate.

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
        signals,
        sample_rate,
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
    )

    return tdoa, analysis_window
