"""Generate multi-source microphone recordings in a simulated room.

Each phone is represented by one microphone position. Each audio source is a
speaker playing a supplied waveform from a known position in the room.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
import pyroomacoustics as pra
from numpy.typing import ArrayLike


@dataclass(frozen=True)
class AudioSource:
	"""One sound source with its room position and emitted mono waveform."""

	position: Sequence[float]
	signal: ArrayLike
	delay_s: float = 0.0


@dataclass(frozen=True)
class SimulationResult:
	"""Microphone recordings and isolated source contributions.

	``microphone_signals`` has shape ``(microphones, samples)``.
	``source_contributions`` has shape ``(sources, microphones, samples)``
	before the sources are mixed together and before optional added noise.
	"""

	microphone_signals: np.ndarray
	source_contributions: np.ndarray
	microphone_positions: np.ndarray
	source_positions: np.ndarray
	sample_rate: int


def make_chirp(
	sample_rate: int,
	duration_s: float = 0.1,
	start_hz: float = 1_000.0,
	end_hz: float | None = None,
	amplitude: float = 0.8,
) -> np.ndarray:
	"""Create a linear frequency-sweep chirp useful for localization tests."""
	_validate_sample_rate(sample_rate)
	if not np.isfinite(duration_s) or duration_s <= 0:
		raise ValueError("duration_s must be a positive finite number")
	if end_hz is None:
		end_hz = 0.45 * sample_rate
	if not np.isfinite(start_hz) or not np.isfinite(end_hz):
		raise ValueError("chirp frequencies must be finite")
	if start_hz <= 0 or end_hz <= 0:
		raise ValueError("chirp frequencies must be positive")
	if max(start_hz, end_hz) >= sample_rate / 2:
		raise ValueError("chirp frequencies must be below the Nyquist frequency")
	if not np.isfinite(amplitude) or not 0 < amplitude <= 1:
		raise ValueError("amplitude must be finite and in the interval (0, 1]")

	sample_count = max(1, int(round(duration_s * sample_rate)))
	time = np.arange(sample_count, dtype=np.float64) / sample_rate
	sweep_rate = (end_hz - start_hz) / duration_s
	phase = 2.0 * np.pi * (start_hz * time + 0.5 * sweep_rate * time**2)

	# A short fade reduces clicks at the beginning and end of the chirp.
	fade_length = min(sample_count // 10, int(0.005 * sample_rate))
	envelope = np.ones(sample_count, dtype=np.float64)
	if fade_length > 0:
		fade = np.linspace(0.0, 1.0, fade_length)
		envelope[:fade_length] = fade
		envelope[-fade_length:] = fade[::-1]

	return amplitude * envelope * np.sin(phase)


def simulate_room(
	room_dimensions: Sequence[float],
	microphone_positions: ArrayLike,
	sources: Sequence[AudioSource],
	*,
	sample_rate: int = 16_000,
	reverberation_time_s: float | None = 0.3,
	snr_db: float | None = None,
	noise_seed: int | None = 0,
) -> SimulationResult:
	"""Simulate several speaker sources recorded by phones in a shoebox room.

	Positions use meters and have shape ``(count, dimensions)``: each row is
	one phone microphone or audio source. Room and position dimensions must
	both be 2D or both be 3D. Every source waveform must use ``sample_rate``.

	Args:
		room_dimensions: Room width/length, optionally followed by height.
		microphone_positions: Phone microphone coordinates, shape
			``(n_microphones, dimensions)``.
		sources: One or more source waveforms, positions, and optional start
			delays. Multiple sources are mixed at every microphone.
		sample_rate: Shared simulation sample rate in samples per second.
		reverberation_time_s: Desired RT60 in seconds. Use ``None`` for a
			direct-path-only simulation with no wall reflections.
		snr_db: Optional target signal-to-added-noise ratio in dB. Noise is
			independently generated for each microphone after source mixing.
		noise_seed: Seed for repeatable added noise; set to ``None`` for
			nondeterministic noise.

	Returns:
		A :class:`SimulationResult` containing the mixed phone recordings,
		per-source contributions, and the coordinates used.

	Raises:
		ValueError: If room dimensions, positions, signals, or parameters are
			invalid, or if a source/microphone is outside the room.
	"""
	_validate_sample_rate(sample_rate)
	dimensions = np.asarray(room_dimensions, dtype=np.float64)
	if dimensions.ndim != 1 or dimensions.size not in (2, 3):
		raise ValueError("room_dimensions must contain two or three lengths")
	if not np.all(np.isfinite(dimensions)) or np.any(dimensions <= 0):
		raise ValueError("room dimensions must be positive and finite")

	microphones = np.asarray(microphone_positions, dtype=np.float64)
	if microphones.ndim != 2 or microphones.shape[1] != dimensions.size:
		raise ValueError(
			"microphone_positions must have shape (n_microphones, room_dimensions)"
		)
	if microphones.shape[0] == 0:
		raise ValueError("at least one microphone position is required")
	_validate_positions(microphones, dimensions, "microphone_positions")

	if not sources:
		raise ValueError("at least one audio source is required")

	source_positions = np.empty((len(sources), dimensions.size), dtype=np.float64)
	source_signals: list[np.ndarray] = []
	source_delays: list[float] = []
	for index, source in enumerate(sources):
		position = np.asarray(source.position, dtype=np.float64)
		if position.shape != (dimensions.size,):
			raise ValueError(
				f"source {index} position must have {dimensions.size} coordinates"
			)
		_validate_positions(position[None, :], dimensions, f"source {index} position")

		signal = np.asarray(source.signal, dtype=np.float64)
		if signal.ndim != 1 or signal.size == 0:
			raise ValueError(f"source {index} signal must be a non-empty mono vector")
		if not np.all(np.isfinite(signal)):
			raise ValueError(f"source {index} signal must contain only finite samples")
		if not np.isfinite(source.delay_s) or source.delay_s < 0:
			raise ValueError(f"source {index} delay_s must be non-negative and finite")

		source_positions[index] = position
		source_signals.append(np.ascontiguousarray(signal))
		source_delays.append(float(source.delay_s))

	if reverberation_time_s is None:
		room = pra.ShoeBox(dimensions.tolist(), fs=sample_rate, max_order=0)
	else:
		if not np.isfinite(reverberation_time_s) or reverberation_time_s <= 0:
			raise ValueError("reverberation_time_s must be positive, or None")
		absorption, max_order = pra.inverse_sabine(
			float(reverberation_time_s), dimensions.tolist()
		)
		room = pra.ShoeBox(
			dimensions.tolist(),
			fs=sample_rate,
			materials=pra.Material(absorption),
			max_order=max_order,
		)

	for position, signal, delay in zip(source_positions, source_signals, source_delays):
		room.add_source(position.tolist(), signal=signal, delay=delay)
	room.add_microphone_array(microphones.T.copy())

	source_contributions = np.asarray(room.simulate(return_premix=True), dtype=np.float64)
	microphone_signals = np.asarray(room.mic_array.signals, dtype=np.float64).copy()

	if snr_db is not None:
		if not np.isfinite(snr_db):
			raise ValueError("snr_db must be finite")
		signal_power = np.mean(microphone_signals**2, axis=1, keepdims=True)
		noise_std = np.sqrt(signal_power / (10.0 ** (snr_db / 10.0)))
		rng = np.random.default_rng(noise_seed)
		microphone_signals += rng.normal(size=microphone_signals.shape) * noise_std

	return SimulationResult(
		microphone_signals=microphone_signals,
		source_contributions=source_contributions,
		microphone_positions=microphones.copy(),
		source_positions=source_positions,
		sample_rate=sample_rate,
	)


def _validate_sample_rate(sample_rate: int) -> None:
	if isinstance(sample_rate, bool) or not isinstance(sample_rate, (int, np.integer)):
		raise ValueError("sample_rate must be a positive integer")
	if sample_rate <= 0:
		raise ValueError("sample_rate must be a positive integer")


def _validate_positions(
	positions: np.ndarray,
	room_dimensions: np.ndarray,
	name: str,
) -> None:
	if not np.all(np.isfinite(positions)):
		raise ValueError(f"{name} must contain only finite coordinates")
	if np.any(positions <= 0) or np.any(positions >= room_dimensions):
		raise ValueError(f"{name} must be strictly inside the room")
