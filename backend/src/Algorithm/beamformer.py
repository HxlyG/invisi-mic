"""Delay-and-sum beamformer using TDOA measurements."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
from numpy.typing import ArrayLike
from scipy.ndimage import uniform_filter
from scipy.signal import istft, stft

from .tdoa import TDOAResult


@dataclass(frozen=True)
class BeamformResult:
    """Result produced by the beamformer."""

    signal: np.ndarray
    sample_rate: float


def beamform(
    signals: Sequence[ArrayLike],
    tdoa: TDOAResult,
    sample_rate: float,
) -> BeamformResult:
    """Beamform microphone recordings toward the source described by TDOA.

    Args:
        signals:
            One-dimensional recording from each microphone.

        tdoa:
            TDOA result describing the relative arrival time of the
            selected source at each microphone.

        sample_rate:
            Shared sample rate of the recordings.

    Returns:
        BeamformResult containing the beamformed audio.

    Notes:
        TDOAResult delays are interpreted as:

            positive -> microphone received the sound later
            negative -> microphone received the sound earlier

        Therefore, a positive delay causes that microphone's signal
        to be advanced in time before summation.

        Fractional-sample delays are handled using linear interpolation.
    """

    if len(signals) != len(tdoa.delays_seconds):
        raise ValueError(
            "number of signals must match the number of TDOA delays"
        )

    if len(signals) < 2:
        raise ValueError(
            "at least two microphone signals are required"
        )

    if not np.isfinite(sample_rate) or sample_rate <= 0:
        raise ValueError(
            "sample_rate must be a positive finite number"
        )

    microphone_signals = [
        _as_signal(signal, index)
        for index, signal in enumerate(signals)
    ]

    signal_length = microphone_signals[0].size

    if any(
        signal.size != signal_length
        for signal in microphone_signals
    ):
        raise ValueError(
            "all microphone signals must have the same length"
        )

    # Convert TDOA from seconds to samples.
    #
    # Example:
    #
    #     delay = +0.5 ms
    #
    # means this microphone heard the source 0.5 ms later
    # than the reference. Therefore we need to move its signal
    # 0.5 ms earlier.
    delays_samples = (
        np.asarray(tdoa.delays_seconds, dtype=np.float64)
        * sample_rate
    )

    aligned_signals = []

    for signal, delay_samples in zip(
        microphone_signals,
        delays_samples,
    ):
        aligned = _shift_signal(
            signal,
            delay_samples,
        )

        aligned_signals.append(aligned)

    # Average rather than sum so the output level does not
    # increase directly with the number of microphones.
    output = np.mean(
        np.stack(aligned_signals, axis=0),
        axis=0,
    )

    return BeamformResult(
        signal=output,
        sample_rate=sample_rate,
    )


def beamform_talkers(
    signals: Sequence[ArrayLike],
    mic_positions: ArrayLike,
    talker_positions: ArrayLike,
    sample_rate: float,
    speed_of_sound: float = 343.0,
    n_fft: int = 1024,
    loading: float = 1e-3,
    reverb_time: float | None = None,
) -> list[np.ndarray]:
    """Isolate each talker from the microphone recordings with an LCMV beamformer.

    Every output keeps unity gain toward its own talker and places nulls toward
    the other talkers, using only the recorded mixture plus the talker positions.
    A mic array can null at most ``len(mics) - 1`` talkers, so when there are more
    the ones nearest the array are nulled. Reverberant energy is not nulled, so
    some leakage remains. With a single mic nothing can be separated and that
    mic's recording is returned.

    A Wiener-style mask across the beams then suppresses what the nulls miss, which
    matters most in reverberant rooms.

    If ``reverb_time`` (RT60 in seconds) is given, the late reverberant tail is
    then spectrally subtracted from each output; this also lowers the level a little.

    Outputs are time-aligned to the talker (propagation delay removed) and carry
    the level that talker has at the first mic.
    """

    recordings = np.stack([_as_signal(signal, index) for index, signal in enumerate(signals)])
    mics = np.asarray(mic_positions, dtype=np.float64)
    talkers = np.asarray(talker_positions, dtype=np.float64)
    mic_count, length = recordings.shape

    if mics.shape[0] != mic_count:
        raise ValueError("number of mic positions must match the number of signals")
    if mic_count < 2:
        return [recordings[0].copy() for _ in talkers]

    freqs, _, spectra = stft(recordings, fs=sample_rate, nperseg=n_fft)
    frames = spectra.shape[-1]

    # The mixture covariance per frequency; diagonal loading keeps the inverse stable.
    covariance = np.einsum("mft,nft->fmn", spectra, spectra.conj()) / frames
    power = np.trace(covariance, axis1=1, axis2=2).real[:, None, None] / mic_count
    covariance = covariance + (loading * power + 1e-12) * np.eye(mic_count)
    inverse = np.linalg.inv(covariance)

    # Free-field steering vectors with spreading loss, shape (talker, frequency, mic).
    distances = np.linalg.norm(talkers[:, None, :] - mics[None, :, :], axis=2)
    steering = (
        np.exp(-2j * np.pi * freqs[None, :, None] * distances[:, None, :] / speed_of_sound)
        / distances[:, None, :]
    )
    centroid_distance = np.linalg.norm(talkers - mics.mean(axis=0), axis=1)

    beams = []
    for target in range(len(talkers)):
        nearest = [i for i in np.argsort(centroid_distance) if i != target]
        constraints = steering[[target, *nearest[: mic_count - 1]]].transpose(1, 2, 0)
        count = constraints.shape[2]

        weighted = inverse @ constraints
        gram = constraints.conj().transpose(0, 2, 1) @ weighted
        gram_power = np.trace(gram, axis1=1, axis2=2).real[:, None, None] / count
        gram = gram + (loading * gram_power + 1e-12) * np.eye(count)

        response = np.zeros((freqs.size, count, 1), dtype=np.complex128)
        response[:, 0, 0] = 1.0 / distances[target, 0]
        weights = (weighted @ np.linalg.solve(gram, response))[..., 0]
        beams.append(np.einsum("fm,mft->ft", weights.conj(), spectra))

    # Each talker keeps the time-frequency bins where its own beam dominates the others.
    stacked = np.stack(beams)
    beam_power = np.abs(stacked) ** 2
    masks = beam_power / (beam_power.sum(axis=0) + 1e-20)

    outputs = []
    for beam, mask in zip(stacked, masks):
        cleaned = beam * mask
        if reverb_time:
            cleaned = _suppress_late_reverb(cleaned, reverb_time, sample_rate, n_fft)
        _, output = istft(cleaned, fs=sample_rate, nperseg=n_fft)
        outputs.append(np.pad(output, (0, max(0, length - output.size)))[:length])

    return outputs


def _suppress_late_reverb(
    spectrum: np.ndarray,
    reverb_time: float,
    sample_rate: float,
    n_fft: int,
    early_seconds: float = 0.05,
    floor: float = 0.1,
    over_subtraction: float = 2.0,
) -> np.ndarray:
    """Spectrally subtract the late reverberant tail from an STFT (Habets' exponential-decay model)."""

    hop = n_fft // 2
    lag = max(1, round(early_seconds * sample_rate / hop))
    decay = 3.0 * np.log(10.0) / reverb_time
    # Smoothing over time and frequency keeps single noisy bins from swinging the gain.
    power = uniform_filter(np.abs(spectrum) ** 2, size=(3, 5), mode="nearest")

    # Late energy at a frame is the energy one early-window earlier, decayed by the room.
    late = np.zeros_like(power)
    late[:, lag:] = np.exp(-2.0 * decay * lag * hop / sample_rate) * power[:, :-lag]

    gain = np.sqrt(np.maximum(1.0 - over_subtraction * late / (power + 1e-20), floor**2))
    return spectrum * gain


def _shift_signal(
    signal: np.ndarray,
    delay_samples: float,
) -> np.ndarray:
    """Align a signal according to a TDOA measurement.

    Positive delay:
        Signal arrived later, so advance it.

    Negative delay:
        Signal arrived earlier, so delay it.

    Fractional delays are handled with linear interpolation.
    """

    sample_indices = np.arange(
        signal.size,
        dtype=np.float64,
    )

    # If the signal arrived later by D samples, the sample that
    # belongs at output position n occurs at input position n + D.
    source_indices = sample_indices + delay_samples

    return np.interp(
        source_indices,
        sample_indices,
        signal,
        left=0.0,
        right=0.0,
    )


def _as_signal(
    signal: ArrayLike,
    index: int,
) -> np.ndarray:
    """Convert and validate one microphone signal."""

    result = np.asarray(
        signal,
        dtype=np.float64,
    )

    if result.ndim != 1:
        raise ValueError(
            f"signal {index} must be one-dimensional"
        )

    if result.size == 0:
        raise ValueError(
            f"signal {index} must not be empty"
        )

    if not np.all(np.isfinite(result)):
        raise ValueError(
            f"signal {index} must contain only finite values"
        )

    return result