"""GCC-PHAT time-delay estimation for a pair of microphone signals."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike
from scipy.signal import butter, find_peaks, sosfiltfilt


@dataclass(frozen=True)
class DelayEstimate:
	"""A measured delay and basic peak diagnostics.

	``delay_seconds`` is positive when ``signal_b`` arrives later than
	``signal_a``. The peak-to-sidelobe ratio is a diagnostic, not a calibrated
	probability or confidence score.
	"""

	delay_seconds: float
	peak_value: float
	peak_to_sidelobe_ratio: float


def estimate_delay(
	signal_a: ArrayLike,
	signal_b: ArrayLike,
	sample_rate: float,
	*,
	max_delay_s: float | None = None,
	interpolation: int = 16,
	time_window_s: tuple[float, float] | None = None,
		phat_beta: float = 1.0,
		frequency_band_hz: tuple[float, float] | None = None,
) -> DelayEstimate:
	"""Estimate the relative arrival delay using GCC-PHAT.

	Args:
		signal_a: The reference microphone's one-dimensional audio samples.
		signal_b: The second microphone's one-dimensional audio samples.
		sample_rate: Sample rate in samples per second.
		max_delay_s: Optional maximum absolute delay to search, in seconds.
			Set this from the maximum physical microphone spacing when known.
		interpolation: Frequency-domain interpolation factor for sub-sample
			delay estimates. Larger values increase computation.
		phat_beta: Whitening exponent in ``|G_ab| ** beta``. One is standard
			PHAT; values below one retain more spectral magnitude information.
		frequency_band_hz: Optional ``(low, high)`` band-pass limits in Hz.
		time_window_s: Optional ``(start, end)`` crop in seconds from the
			shared recording start. The same interval is applied to both signals;
			this preserves their relative arrival offset. It does not by itself
			separate direct sound from echoes.

	Returns:
		The signed delay in seconds and correlation-peak diagnostics.

	Raises:
		ValueError: If an input is invalid or either signal has no varying
			content from which to estimate a delay.
	"""
	a = _as_signal(signal_a, "signal_a")
	b = _as_signal(signal_b, "signal_b")

	if not np.isfinite(sample_rate) or sample_rate <= 0:
		raise ValueError("sample_rate must be a positive finite number")
	if isinstance(interpolation, bool) or not isinstance(interpolation, int):
		raise ValueError("interpolation must be a positive integer")
	if interpolation < 1:
		raise ValueError("interpolation must be a positive integer")
	if not np.isfinite(phat_beta) or not 0 < phat_beta <= 1:
		raise ValueError("phat_beta must be in the interval (0, 1]")
	if frequency_band_hz is not None:
		if len(frequency_band_hz) != 2:
			raise ValueError("frequency_band_hz must be a (low, high) pair")
		low_hz, high_hz = frequency_band_hz
		if (
			not np.isfinite(low_hz)
			or not np.isfinite(high_hz)
			or low_hz <= 0
			or high_hz <= low_hz
			or high_hz >= sample_rate / 2
		):
			raise ValueError("frequency_band_hz must satisfy 0 < low < high < Nyquist")
	if max_delay_s is not None and (
		not np.isfinite(max_delay_s) or max_delay_s < 0
	):
		raise ValueError("max_delay_s must be a non-negative finite number")
	if time_window_s is not None:
		if len(time_window_s) != 2:
			raise ValueError("time_window_s must be a (start, end) pair")
		window_start_s, window_end_s = time_window_s
		if not np.isfinite(window_start_s) or not np.isfinite(window_end_s):
			raise ValueError("time_window_s values must be finite")
		if window_start_s < 0 or window_end_s <= window_start_s:
			raise ValueError("time_window_s must satisfy 0 <= start < end")

		start_sample = int(round(window_start_s * sample_rate))
		end_sample = int(round(window_end_s * sample_rate))
		if end_sample - start_sample < 2:
			raise ValueError("time_window_s must include at least two samples")
		if end_sample > min(a.size, b.size):
			raise ValueError("time_window_s extends beyond the shorter signal")
		a = a[start_sample:end_sample]
		b = b[start_sample:end_sample]
	if frequency_band_hz is not None:
		sos = butter(4, frequency_band_hz, btype="bandpass", fs=sample_rate, output="sos")
		try:
			a = sosfiltfilt(sos, a)
			b = sosfiltfilt(sos, b)
		except ValueError as error:
			raise ValueError("signals are too short for the requested band-pass filter") from error

	# Remove DC so it cannot dominate the phase-weighted correlation.
	a = a - np.mean(a)
	b = b - np.mean(b)
	if not np.any(a) or not np.any(b):
		raise ValueError("signals must contain non-constant audio")

	# Padding to at least the combined signal length avoids circular overlap.
	required_length = a.size + b.size
	fft_length = 1 << (required_length - 1).bit_length()

	cross_spectrum = np.fft.rfft(b, n=fft_length) * np.conj(
		np.fft.rfft(a, n=fft_length)
	)
	magnitude = np.abs(cross_spectrum)
	nonzero_bins = magnitude > np.finfo(float).eps * magnitude.max()
	if not np.any(nonzero_bins):
		raise ValueError("signals do not contain enough information to correlate")
	weighting = np.power(magnitude, phat_beta)
	cross_spectrum = np.divide(
		cross_spectrum,
		weighting,
		out=np.zeros_like(cross_spectrum),
		where=nonzero_bins & (weighting > 0),
	)

	# A longer inverse transform zero-pads the cross-spectrum, interpolating
	# the correlation curve to 1 / interpolation-sample resolution.
	correlation = np.fft.irfft(
		cross_spectrum, n=fft_length * interpolation
	)

	# A linear correlation cannot have a useful lag larger than the shorter
	# recording. Restricting the search further can reject impossible delays.
	max_lag_samples = min(a.size, b.size) - 1
	if max_delay_s is not None:
		max_lag_samples = min(
			max_lag_samples, int(np.ceil(max_delay_s * sample_rate))
		)
	max_shift = max_lag_samples * interpolation
	if max_shift == 0:
		searched_correlation = correlation[:1]
		lags = np.array([0], dtype=np.int64)
	else:
		searched_correlation = np.concatenate(
			(correlation[-max_shift:], correlation[: max_shift + 1])
		)
		lags = np.arange(-max_shift, max_shift + 1, dtype=np.int64)

	absolute_correlation = np.abs(searched_correlation)
	peak_index = int(np.argmax(absolute_correlation))
	peak_lag = int(lags[peak_index])
	peak_value = float(absolute_correlation[peak_index])

	# Ignore the peak's immediate lobe when estimating the sidelobe baseline.
	outside_peak_lobe = np.abs(lags - peak_lag) > interpolation
	if np.any(outside_peak_lobe):
		sidelobe_level = float(np.median(absolute_correlation[outside_peak_lobe]))
		ratio = peak_value / max(sidelobe_level, np.finfo(float).eps)
	else:
		ratio = float("inf")

	return DelayEstimate(
		delay_seconds=peak_lag / (interpolation * sample_rate),
		peak_value=peak_value,
		peak_to_sidelobe_ratio=ratio,
	)

def estimate_delay_candidates(
	signal_a: ArrayLike,
	signal_b: ArrayLike,
	sample_rate: float,
	*,
	max_delay_s: float,
	interpolation: int = 16,
	time_window_s: tuple[float, float] | None = None,
	phat_beta: float = 0.7,
	frequency_band_hz: tuple[float, float] | None = None,
	candidate_count: int = 5,
) -> tuple[DelayEstimate, ...]:
	"""Return several strong local GCC-PHAT peaks within a physical lag bound.

	Unlike :func:`estimate_delay`, this does not assume the global maximum is
	the direct arrival. Candidate peak values and peak-to-sidelobe ratios are
	diagnostics, not calibrated probabilities.
	"""
	if isinstance(candidate_count, bool) or not isinstance(candidate_count, int) or candidate_count < 1:
		raise ValueError("candidate_count must be a positive integer")
	a = _as_signal(signal_a, "signal_a")
	b = _as_signal(signal_b, "signal_b")
	if not np.isfinite(sample_rate) or sample_rate <= 0:
		raise ValueError("sample_rate must be a positive finite number")
	if not np.isfinite(max_delay_s) or max_delay_s < 0:
		raise ValueError("max_delay_s must be a non-negative finite number")
	if isinstance(interpolation, bool) or not isinstance(interpolation, int) or interpolation < 1:
		raise ValueError("interpolation must be a positive integer")
	if not np.isfinite(phat_beta) or not 0 < phat_beta <= 1:
		raise ValueError("phat_beta must be in the interval (0, 1]")
	if time_window_s is not None:
		start_s, end_s = time_window_s
		if not np.isfinite(start_s) or not np.isfinite(end_s) or start_s < 0 or end_s <= start_s:
			raise ValueError("time_window_s must satisfy 0 <= start < end")
		start = int(round(start_s * sample_rate))
		end = int(round(end_s * sample_rate))
		if end - start < 2 or end > min(a.size, b.size):
			raise ValueError("time_window_s must contain at least two samples within both signals")
		a, b = a[start:end], b[start:end]
	if frequency_band_hz is not None:
		low_hz, high_hz = frequency_band_hz
		if not 0 < low_hz < high_hz < sample_rate / 2:
			raise ValueError("frequency_band_hz must satisfy 0 < low < high < Nyquist")
		sos = butter(4, frequency_band_hz, btype="bandpass", fs=sample_rate, output="sos")
		try:
			a, b = sosfiltfilt(sos, a), sosfiltfilt(sos, b)
		except ValueError as error:
			raise ValueError("signals are too short for the requested band-pass filter") from error
	a, b = a - np.mean(a), b - np.mean(b)
	if not np.any(a) or not np.any(b):
		raise ValueError("signals must contain non-constant audio")
	fft_length = 1 << (a.size + b.size - 1).bit_length()
	cross = np.fft.rfft(b, n=fft_length) * np.conj(np.fft.rfft(a, n=fft_length))
	magnitude = np.abs(cross)
	valid = magnitude > np.finfo(float).eps * magnitude.max()
	if not np.any(valid):
		raise ValueError("signals do not contain enough information to correlate")
	weight = np.power(magnitude, phat_beta)
	cross = np.divide(cross, weight, out=np.zeros_like(cross), where=valid & (weight > 0))
	corr = np.fft.irfft(cross, n=fft_length * interpolation)
	max_lag = min(min(a.size, b.size) - 1, int(np.ceil(max_delay_s * sample_rate)))
	shift = max_lag * interpolation
	searched = corr[:1] if shift == 0 else np.concatenate((corr[-shift:], corr[:shift + 1]))
	lags = np.arange(-shift, shift + 1, dtype=np.int64) if shift else np.array([0], dtype=np.int64)
	absolute = np.abs(searched)
	peak_indices, _ = find_peaks(absolute)
	peak_indices = np.unique(np.concatenate((peak_indices, np.array([0, absolute.size - 1]))))
	peak_indices = sorted(peak_indices, key=lambda idx: float(absolute[idx]), reverse=True)
	selected: list[int] = []
	minimum_separation = 2 * interpolation
	for index in peak_indices:
		if all(abs(int(lags[index]) - int(lags[other])) >= minimum_separation for other in selected):
			selected.append(int(index))
		if len(selected) >= candidate_count:
			break
	result: list[DelayEstimate] = []
	for index in selected:
		lag = int(lags[index])
		peak = float(absolute[index])
		outside = np.abs(lags - lag) > interpolation
		baseline = float(np.median(absolute[outside])) if np.any(outside) else 0.0
		ratio = peak / max(baseline, np.finfo(float).eps)
		result.append(DelayEstimate(lag / (interpolation * sample_rate), peak, ratio))
	return tuple(result)


def _as_signal(signal: ArrayLike, name: str) -> np.ndarray:
	"""Convert an audio input to a finite, non-empty float64 vector."""
	result = np.asarray(signal, dtype=np.float64)
	if result.ndim != 1:
		raise ValueError(f"{name} must be a one-dimensional signal")
	if result.size == 0:
		raise ValueError(f"{name} must not be empty")
	if not np.all(np.isfinite(result)):
		raise ValueError(f"{name} must contain only finite samples")
	return result
