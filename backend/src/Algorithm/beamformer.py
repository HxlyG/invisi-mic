"""Delay-and-sum beamformer using TDOA measurements."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
from numpy.typing import ArrayLike

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