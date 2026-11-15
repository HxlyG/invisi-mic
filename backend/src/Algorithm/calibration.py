"""Matched-filter calibration for locating the first credible chirp arrival."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
from numpy.typing import ArrayLike
from scipy.signal import correlate, find_peaks

from .solver import LocalizationResult, solve_position
from .tdoa import TDOAResult


@dataclass(frozen=True)
class ChirpArrival:
    """Detected chirp start and matched-filter diagnostics."""

    arrival_time_s: float
    peak_value: float
    threshold: float
    peak_to_noise_ratio: float


@dataclass(frozen=True)
class ChirpLocalization:
    """Chirp arrivals, their relative delays, and the estimated source position."""

    arrivals: tuple[ChirpArrival, ...]
    delays_seconds: tuple[float, ...]
    localization: LocalizationResult


def estimate_chirp_arrival(
    recording: ArrayLike,
    chirp: ArrayLike,
    sample_rate: float,
    *,
    search_window_s: tuple[float, float],
    noise_window_s: tuple[float, float],
    noise_sigma: float = 8.0,
    min_peak_ratio: float = 0.1,
    min_peak_distance_s: float = 0.001,
) -> ChirpArrival:
    """Find the earliest threshold-crossing matched-filter peak.

    ``search_window_s`` bounds possible chirp start times in the recording.
    ``noise_window_s`` must identify quiet recording before the emitted chirp;
    each returned matched-filter value corresponds to a time at which the whole
    reference chirp fits in that quiet interval.

    This is appropriate for a known calibration waveform, not arbitrary speech.
    Playback/recording latency must be calibrated separately before interpreting
    the result as an absolute acoustic travel time.
    """
    samples = _as_signal(recording, "recording")
    template = _as_signal(chirp, "chirp")
    if not np.isfinite(sample_rate) or sample_rate <= 0:
        raise ValueError("sample_rate must be a positive finite number")
    if template.size > samples.size:
        raise ValueError("chirp must not be longer than recording")
    if not np.isfinite(noise_sigma) or noise_sigma <= 0:
        raise ValueError("noise_sigma must be a positive finite number")
    if not np.isfinite(min_peak_ratio) or not 0 < min_peak_ratio <= 1:
        raise ValueError("min_peak_ratio must be in the interval (0, 1]")
    if not np.isfinite(min_peak_distance_s) or min_peak_distance_s < 0:
        raise ValueError("min_peak_distance_s must be non-negative and finite")
    search_start, search_end = _validate_window(search_window_s, "search_window_s")
    noise_start, noise_end = _validate_window(noise_window_s, "noise_window_s")

    template_energy = float(np.dot(template, template))
    if template_energy <= np.finfo(float).eps:
        raise ValueError("chirp must contain non-silent audio")

    # Valid mode indexes every possible chirp start, avoiding partial overlaps.
    matched = np.abs(correlate(samples, template, mode="valid", method="fft"))
    starts = np.arange(matched.size, dtype=np.float64) / sample_rate
    noise_mask = (
        (starts >= noise_start)
        & (starts + template.size / sample_rate <= noise_end)
    )
    noise_values = matched[noise_mask]
    if noise_values.size < 3:
        raise ValueError("noise_window_s must contain at least three complete chirp windows")

    noise_median = float(np.median(noise_values))
    noise_mad = float(np.median(np.abs(noise_values - noise_median)))
    robust_noise = 1.4826 * noise_mad
    # The epsilon term also handles an exactly silent noise interval.
    start_index = max(0, int(np.ceil(search_start * sample_rate)))
    end_index = min(matched.size, int(np.floor(search_end * sample_rate)) + 1)
    if end_index <= start_index:
        raise ValueError("search_window_s contains no valid chirp start samples")
    candidates = matched[start_index:end_index]
    if candidates.size < 3:
        raise ValueError("search_window_s must contain at least three samples")
    threshold = max(
        noise_median + noise_sigma * max(robust_noise, np.finfo(float).eps),
        float(np.max(candidates)) * min_peak_ratio,
    )

    minimum_distance = max(1, int(round(min_peak_distance_s * sample_rate)))
    peaks, _ = find_peaks(
        candidates,
        height=threshold,
        prominence=max(threshold - noise_median, np.finfo(float).eps),
        distance=minimum_distance,
    )
    # scipy excludes endpoints from local maxima; admit a qualifying boundary peak.
    boundary_peaks = []
    if candidates[0] >= threshold and candidates[0] > candidates[1]:
        boundary_peaks.append(0)
    if candidates[-1] >= threshold and candidates[-1] > candidates[-2]:
        boundary_peaks.append(candidates.size - 1)
    if boundary_peaks:
        peaks = np.sort(np.concatenate((peaks, np.asarray(boundary_peaks, dtype=int))))
    if peaks.size == 0:
        raise ValueError("no chirp arrival crossed the noise-floor threshold")

    peak_index = int(peaks[0])
    # Parabolic peak interpolation provides sub-sample timing when possible.
    fractional_offset = 0.0
    if 0 < peak_index < candidates.size - 1:
        left, center, right = candidates[peak_index - 1 : peak_index + 2]
        denominator = left - 2.0 * center + right
        if abs(denominator) > np.finfo(float).eps:
            fractional_offset = float(np.clip(0.5 * (left - right) / denominator, -0.5, 0.5))

    peak_value = float(candidates[peak_index])
    arrival_sample = start_index + peak_index + fractional_offset
    return ChirpArrival(
        arrival_time_s=float(arrival_sample / sample_rate),
        peak_value=peak_value,
        threshold=threshold,
        peak_to_noise_ratio=peak_value / max(noise_median, np.finfo(float).eps),
    )


def estimate_chirp_tdoa(
    recordings: Sequence[ArrayLike],
    chirp: ArrayLike,
    sample_rate: float,
    *,
    reference_index: int = 0,
    search_window_s: tuple[float, float],
    noise_window_s: tuple[float, float],
    noise_sigma: float = 8.0,
    min_peak_ratio: float = 0.1,
    min_peak_distance_s: float = 0.001,
) -> tuple[tuple[float, ...], tuple[ChirpArrival, ...]]:
    """Detect each mic's chirp arrival and return delays from one reference mic."""
    if len(recordings) < 2:
        raise ValueError("at least two microphone recordings are required")
    if isinstance(reference_index, bool) or not isinstance(reference_index, int):
        raise ValueError("reference_index must be an integer")
    if not 0 <= reference_index < len(recordings):
        raise ValueError("reference_index is outside the recordings sequence")

    arrivals = tuple(
        estimate_chirp_arrival(
            recording,
            chirp,
            sample_rate,
            search_window_s=search_window_s,
            noise_window_s=noise_window_s,
            noise_sigma=noise_sigma,
            min_peak_ratio=min_peak_ratio,
            min_peak_distance_s=min_peak_distance_s,
        )
        for recording in recordings
    )
    reference_time = arrivals[reference_index].arrival_time_s
    delays = tuple(arrival.arrival_time_s - reference_time for arrival in arrivals)
    return delays, arrivals


def localize_chirp_source(
    recordings: Sequence[ArrayLike],
    chirp: ArrayLike,
    sample_rate: float,
    microphone_positions: ArrayLike,
    *,
    room_dimensions: Sequence[float] | None = None,
    reference_index: int = 0,
    search_window_s: tuple[float, float],
    noise_window_s: tuple[float, float],
    noise_sigma: float = 8.0,
    min_peak_ratio: float = 0.1,
    min_peak_distance_s: float = 0.001,
    speed_of_sound: float = 343.0,
) -> ChirpLocalization:
    """Estimate a known calibration chirp's source position end-to-end.

    This expects simultaneous, sample-aligned recordings and known microphone
    coordinates. Inter-device clock and audio-pipeline offsets must be calibrated
    separately; otherwise they are indistinguishable from acoustic delays.
    """
    delays, arrivals = estimate_chirp_tdoa(
        recordings,
        chirp,
        sample_rate,
        reference_index=reference_index,
        search_window_s=search_window_s,
        noise_window_s=noise_window_s,
        noise_sigma=noise_sigma,
        min_peak_ratio=min_peak_ratio,
        min_peak_distance_s=min_peak_distance_s,
    )
    tdoa = TDOAResult(
        reference_index=reference_index,
        delays_seconds=delays,
        estimates=(None,) * len(delays),
    )
    localization = solve_position(
        microphone_positions,
        tdoa,
        speed_of_sound=speed_of_sound,
        room_dimensions=room_dimensions,
    )
    return ChirpLocalization(arrivals, delays, localization)


def _as_signal(signal: ArrayLike, name: str) -> np.ndarray:
    result = np.asarray(signal, dtype=np.float64)
    if result.ndim != 1 or result.size == 0:
        raise ValueError(f"{name} must be a non-empty one-dimensional signal")
    if not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must contain only finite samples")
    return result


def _validate_window(window: tuple[float, float], name: str) -> tuple[float, float]:
    if len(window) != 2:
        raise ValueError(f"{name} must be a (start, end) pair")
    start, end = window
    if not np.isfinite(start) or not np.isfinite(end) or start < 0 or end <= start:
        raise ValueError(f"{name} must satisfy 0 <= start < end")
    return float(start), float(end)
