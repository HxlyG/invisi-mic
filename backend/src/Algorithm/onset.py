"""Detect the start of a new audio event from a microphone recording."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike


@dataclass(frozen=True)
class OnsetDetection:
    """Energy-based onset estimate and threshold diagnostics.

    The thresholds are useful diagnostics, not calibrated detection
    probabilities. The onset time is a frame-level estimate, typically within
    one hop of the true energy rise.
    """

    onset_time_s: float
    threshold_rms: float
    peak_rms: float
    background_rms: float
    release_threshold_rms: float


def detect_onset(
    signal: ArrayLike,
    sample_rate: int,
    *,
    frame_ms: float = 5.0,
    hop_ms: float = 1.0,
    relative_threshold: float = 0.15,
    consecutive_frames: int = 3,
    release_threshold_ratio: float = 0.6,
    noise_window_s: tuple[float, float] | None = None,
    background_sigma: float = 6.0,
) -> OnsetDetection:
    """Find the first sustained rise in short-time RMS energy.

    This is a lightweight event trigger, not a direct-path detector. Use its
    result to select one shared crop for all synchronized microphones; do not
    independently align/crop each mic at its own detected onset, since that
    would remove the inter-microphone delay information.

    A high threshold opens an event, while a lower hysteresis threshold keeps
    it active during small level dips. The candidate must remain above the lower
    threshold for ``consecutive_frames`` frames, rejecting isolated clicks.

    If ``noise_window_s`` is provided, it identifies a known quiet recording
    interval for background calibration. Otherwise, a robust low-energy subset
    of the recording estimates the background; this fallback can be inaccurate
    when speech occupies most of the recording.

    Args:
        signal: One-dimensional microphone recording.
        sample_rate: Samples per second.
        frame_ms: RMS analysis-frame length in milliseconds.
        hop_ms: Step between consecutive RMS frames in milliseconds.
        relative_threshold: Peak-RMS fraction used as one threshold floor.
        consecutive_frames: Number of active frames in a row required.
        release_threshold_ratio: Lower hysteresis threshold as a fraction of the
            start threshold. Must be strictly between zero and one.
        noise_window_s: Optional known quiet ``(start, end)`` interval in seconds.
        background_sigma: Robust-deviation multiplier used for the start
            threshold above estimated background energy.

    Returns:
        The detected onset time in seconds and RMS threshold diagnostics.

    Raises:
        ValueError: If arguments or signal are invalid, or no sustained onset
            is detected.
    """
    # Convert supported array-like inputs to a consistent numeric format before
    # doing sample-rate-based calculations.
    samples = np.asarray(signal, dtype=np.float64)
    if samples.ndim != 1 or samples.size == 0:
        raise ValueError("signal must be a non-empty one-dimensional array")
    if not np.all(np.isfinite(samples)):
        raise ValueError("signal must contain only finite samples")
    if isinstance(sample_rate, bool) or not isinstance(sample_rate, (int, np.integer)) or sample_rate <= 0:
        raise ValueError("sample_rate must be a positive integer")
    if not np.isfinite(frame_ms) or frame_ms <= 0:
        raise ValueError("frame_ms must be positive and finite")
    if not np.isfinite(hop_ms) or hop_ms <= 0:
        raise ValueError("hop_ms must be positive and finite")
    if not np.isfinite(relative_threshold) or not 0 < relative_threshold < 1:
        raise ValueError("relative_threshold must be between zero and one")
    if isinstance(consecutive_frames, bool) or not isinstance(consecutive_frames, int) or consecutive_frames < 1:
        raise ValueError("consecutive_frames must be a positive integer")
    if not np.isfinite(release_threshold_ratio) or not 0 < release_threshold_ratio < 1:
        raise ValueError("release_threshold_ratio must be between zero and one")
    if not np.isfinite(background_sigma) or background_sigma < 0:
        raise ValueError("background_sigma must be non-negative and finite")
    if noise_window_s is not None:
        if len(noise_window_s) != 2:
            raise ValueError("noise_window_s must be a (start, end) pair")
        noise_start_s, noise_end_s = noise_window_s
        if (
            not np.isfinite(noise_start_s)
            or not np.isfinite(noise_end_s)
            or noise_start_s < 0
            or noise_end_s <= noise_start_s
        ):
            raise ValueError("noise_window_s must satisfy 0 <= start < end")

    # RMS is measured over short frames rather than individual samples: this
    # smooths the waveform enough to detect a rise in sound level. The hop is
    # how far the analysis window advances each time.
    frame_length = max(1, int(round(frame_ms * sample_rate / 1_000.0)))
    hop_length = max(1, int(round(hop_ms * sample_rate / 1_000.0)))
    if samples.size < frame_length:
        raise ValueError("signal is shorter than one analysis frame")

    frame_starts = np.arange(0, samples.size - frame_length + 1, hop_length)
    frame_rms = np.array(
        [np.sqrt(np.mean(samples[start : start + frame_length] ** 2)) for start in frame_starts],
        dtype=np.float64,
    )
    # The signal's largest frame gives a rough scale for the event. An all-zero
    # signal has no onset to report.
    peak_rms = float(np.max(frame_rms))
    if peak_rms <= np.finfo(float).eps:
        raise ValueError("no non-silent audio was detected")

    # Prefer a caller-specified quiet lead-in when available. Otherwise, use the
    # lower-energy frames as an automatic fallback; this is less reliable if the
    # event fills most of the capture.
    if noise_window_s is not None:
        noise_start_s, noise_end_s = noise_window_s
        noise_start_sample = int(round(noise_start_s * sample_rate))
        noise_end_sample = int(round(noise_end_s * sample_rate))
        if noise_end_sample > samples.size:
            raise ValueError("noise_window_s extends beyond the signal")
        quiet_frame_mask = (
            (frame_starts >= noise_start_sample)
            & (frame_starts + frame_length <= noise_end_sample)
        )
        low_energy = frame_rms[quiet_frame_mask]
        if low_energy.size < 3:
            raise ValueError("noise_window_s must contain at least three complete analysis frames")
    else:
        low_energy = frame_rms[frame_rms <= np.percentile(frame_rms, 40)]
    background_rms = float(np.median(low_energy))
    robust_deviation = float(
        1.4826 * np.median(np.abs(low_energy - background_rms))
    )
    if peak_rms < background_rms * 1.25:
        raise ValueError("recording has no clear energy rise above its background")

    # Some captures begin so close to the source event that most frames contain
    # sound. In that case the lower-percentile estimate is not a true noise
    # floor; cap it so a valid onset is not assigned a threshold above the peak.
    estimated_background_threshold = min(
        background_rms + background_sigma * robust_deviation,
        peak_rms * 0.75,
    )
    # Require activity to clear both a relative-to-peak floor and a background
    # floor. Capping the background-based floor prevents it exceeding the
    # observed peak in short recordings that start near the sound.
    threshold = max(
        peak_rms * relative_threshold,
        estimated_background_threshold,
    )
    release_threshold = max(
        background_rms + 2.0 * robust_deviation,
        threshold * release_threshold_ratio,
    )
    release_threshold = min(release_threshold, threshold)

    # Hysteresis starts only when energy clears the upper threshold. To confirm
    # that crossing is sustained, subsequent frames need only remain above the
    # lower release threshold. This tolerates small speech-envelope dips without
    # accepting one-frame clicks.
    last_candidate = frame_rms.size - consecutive_frames + 1
    for frame_index in range(max(0, last_candidate)):
        if frame_rms[frame_index] < threshold:
            continue
        confirmation = frame_rms[frame_index + 1 : frame_index + consecutive_frames]
        if np.all(confirmation >= release_threshold):
            onset_time_s = float(frame_starts[frame_index] / sample_rate)
            return OnsetDetection(
                onset_time_s=onset_time_s,
                threshold_rms=threshold,
                peak_rms=peak_rms,
                background_rms=background_rms,
                release_threshold_rms=release_threshold,
            )

    raise ValueError("no sustained audio onset was detected")


def shared_onset_window(
    signals: tuple[ArrayLike, ...] | list[ArrayLike],
    sample_rate: int,
    max_inter_mic_delay_s: float,
    *,
    pre_roll_s: float = 0.005,
    event_duration_s: float = 0.15,
    noise_window_s: tuple[float, float] | None = None,
) -> tuple[tuple[float, float], tuple[OnsetDetection, ...]]:
    """Detect channel onsets and make one shared recording-time crop.

    The crop begins shortly before the earliest detected onset and continues
    through the expected propagation spread plus ``event_duration_s``. Every
    channel uses identical sample-time boundaries, preserving TDOA.

    ``noise_window_s`` is an optional shared recording interval known to be
    quiet. It is used only to calibrate each channel's energy threshold.
    """
    if len(signals) < 2:
        raise ValueError("at least two microphone signals are required")
    if not np.isfinite(max_inter_mic_delay_s) or max_inter_mic_delay_s < 0:
        raise ValueError("max_inter_mic_delay_s must be non-negative and finite")
    if not np.isfinite(pre_roll_s) or pre_roll_s < 0:
        raise ValueError("pre_roll_s must be non-negative and finite")
    if not np.isfinite(event_duration_s) or event_duration_s <= 0:
        raise ValueError("event_duration_s must be positive and finite")

    arrays = [np.asarray(signal, dtype=np.float64) for signal in signals]
    if any(array.ndim != 1 or array.size == 0 for array in arrays):
        raise ValueError("each microphone signal must be a non-empty 1D array")
    if len({array.size for array in arrays}) != 1:
        raise ValueError("all recordings must have equal length for a shared-time crop")

    # Detect every channel to diagnose which phone saw activity when. These
    # per-phone detections are NOT used to shift channels independently.
    detections = tuple(
        detect_onset(signal, sample_rate, noise_window_s=noise_window_s)
        for signal in arrays
    )
    earliest_onset = min(detection.onset_time_s for detection in detections)
    recording_duration_s = arrays[0].size / sample_rate

    # Choose one common crop: preserve a little audio before the earliest
    # trigger, then allow for propagation to the farthest mic plus the event
    # duration. Identical crop boundaries preserve inter-mic arrival offsets.
    start_s = max(0.0, earliest_onset - pre_roll_s)
    end_s = min(
        recording_duration_s,
        earliest_onset + max_inter_mic_delay_s + event_duration_s,
    )
    if end_s <= start_s:
        raise ValueError("detected onset does not leave a usable shared window")

    return (start_s, end_s), detections
