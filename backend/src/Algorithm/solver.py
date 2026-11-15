"""Estimate a sound source position from microphone TDOA measurements."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
from numpy.typing import ArrayLike
from scipy.optimize import least_squares

from .tdoa import TDOAResult


@dataclass(frozen=True)
class LocalizationResult:
    """Position estimate and residual diagnostics.

    ``position`` is in meters. ``residuals_seconds`` follows microphone input
    order and is zero for the reference microphone. RMS residual is a measure
    of how well the estimated position matches the supplied TDOAs; it is not a
    calibrated probability that the position is correct.
    """

    position: tuple[float, ...]
    reference_index: int
    residuals_seconds: tuple[float, ...]
    rms_error_seconds: float
    success: bool
    message: str


def solve_position(
    microphone_positions: ArrayLike,
    tdoa: TDOAResult,
    *,
    speed_of_sound: float = 343.0,
    room_dimensions: Sequence[float] | None = None,
    initial_position: ArrayLike | None = None,
) -> LocalizationResult:
    """Find the source position that best explains measured arrival delays.

    The solver minimizes the difference between the measured and geometric
    range differences. For microphone ``i`` and reference ``r``, the model is
    ``(||x - p_i|| - ||x - p_r||) / speed_of_sound``.

    Args:
        microphone_positions: Coordinates in meters, shape
            ``(n_microphones, dimensions)``. Dimensions must be 2 or 3, and
            the microphone geometry must span that coordinate space.
        tdoa: Delays from :func:`src.Algorithm.tdoa.estimate_tdoa`, in the same
            microphone order as ``microphone_positions``.
        speed_of_sound: Sound speed in meters per second.
        room_dimensions: Optional room lengths. When supplied, constrains the
            estimate to the room and adds the room center as an initial guess.
        initial_position: Optional starting coordinate in meters. The solver
            also tries deterministic geometry-based starts to reduce local
            minimum sensitivity.

    Returns:
        A :class:`LocalizationResult` with the estimated coordinate and the
        TDOA residual diagnostics.

    Raises:
        ValueError: If the microphone geometry, delays, or optional arguments
            are invalid or cannot determine a position in the requested
            dimensions.
    """
    print(microphone_positions)
    microphones = np.asarray(microphone_positions, dtype=np.float64)
    if microphones.ndim != 2 or microphones.shape[1] not in (2, 3):
        raise ValueError("microphone_positions must have shape (n_mics, 2 or 3)")
    dimensions = microphones.shape[1]
    microphone_count = microphones.shape[0]
    if microphone_count < dimensions + 1:
        raise ValueError(
            f"at least {dimensions + 1} microphones are required for {dimensions}D"
        )
    if not np.all(np.isfinite(microphones)):
        raise ValueError("microphone_positions must contain only finite coordinates")
    if np.linalg.matrix_rank(microphones - microphones[0]) < dimensions:
        raise ValueError(
            "microphone positions must span the requested coordinate dimensions; "
            "for 3D, avoid coplanar microphones"
        )

    delays = np.asarray(tdoa.delays_seconds, dtype=np.float64)
    reference_index = tdoa.reference_index
    if delays.shape != (microphone_count,):
        raise ValueError("the number of TDOA delays must match the microphones")
    if not np.all(np.isfinite(delays)):
        raise ValueError("TDOA delays must be finite")
    if (
        isinstance(reference_index, bool)
        or not isinstance(reference_index, int)
        or not 0 <= reference_index < microphone_count
    ):
        raise ValueError("TDOA reference_index is outside the microphone array")
    if abs(delays[reference_index]) > 1e-12:
        raise ValueError("the reference microphone's TDOA must be zero")
    if not np.isfinite(speed_of_sound) or speed_of_sound <= 0:
        raise ValueError("speed_of_sound must be a positive finite number")

    room_size: np.ndarray | None = None
    if room_dimensions is None:
        lower_bounds = np.full(dimensions, -np.inf)
        upper_bounds = np.full(dimensions, np.inf)
    else:
        room_size = np.asarray(room_dimensions, dtype=np.float64)
        if room_size.shape != (dimensions,):
            raise ValueError("room_dimensions must match the microphone dimensions")
        if not np.all(np.isfinite(room_size)) or np.any(room_size <= 0):
            raise ValueError("room_dimensions must be positive and finite")
        if np.any(microphones < 0) or np.any(microphones > room_size):
            raise ValueError("microphone positions must lie within room_dimensions")
        lower_bounds = np.zeros(dimensions, dtype=np.float64)
        upper_bounds = room_size.copy()

    explicit_start: np.ndarray | None = None
    if initial_position is not None:
        explicit_start = np.asarray(initial_position, dtype=np.float64)
        if explicit_start.shape != (dimensions,) or not np.all(np.isfinite(explicit_start)):
            raise ValueError("initial_position must be finite and match coordinate dimensions")

    reference_position = microphones[reference_index]
    other_indices = np.array(
        [index for index in range(microphone_count) if index != reference_index],
        dtype=np.int64,
    )
    measured_range_differences = (
        delays[other_indices] * speed_of_sound
    )

    def range_residual(position: np.ndarray) -> np.ndarray:
        reference_range = np.linalg.norm(position - reference_position)
        microphone_ranges = np.linalg.norm(
            position - microphones[other_indices], axis=1
        )
        return microphone_ranges - reference_range - measured_range_differences

    center = np.mean(microphones, axis=0)
    span = max(float(np.max(np.ptp(microphones, axis=0))), 1.0)
    starts = [center]
    if room_size is not None:
        starts.append(room_size / 2.0)
    if explicit_start is not None:
        starts.insert(0, explicit_start)
    for axis in range(dimensions):
        offset = np.zeros(dimensions, dtype=np.float64)
        offset[axis] = span
        starts.extend((center + offset, center - offset))

    unique_starts: list[np.ndarray] = []
    for start in starts:
        if room_size is not None:
            start = np.clip(start, 1e-8, room_size - 1e-8)
        if not any(np.allclose(start, existing) for existing in unique_starts):
            unique_starts.append(start)

    solutions = [
        least_squares(
            range_residual,
            start,
            bounds=(lower_bounds, upper_bounds),
            loss="soft_l1",
            f_scale=0.01,
            x_scale="jac",
            max_nfev=2_000,
        )
        for start in unique_starts
    ]
    best = min(solutions, key=lambda solution: float(np.dot(solution.fun, solution.fun)))

    predicted_delays = np.zeros(microphone_count, dtype=np.float64)
    source_to_reference = np.linalg.norm(best.x - reference_position)
    predicted_delays[other_indices] = (
        np.linalg.norm(best.x - microphones[other_indices], axis=1)
        - source_to_reference
    ) / speed_of_sound
    residuals = predicted_delays - delays
    rms_error = float(np.sqrt(np.mean(residuals[other_indices] ** 2)))

    return LocalizationResult(
        position=tuple(float(coordinate) for coordinate in best.x),
        reference_index=reference_index,
        residuals_seconds=tuple(float(error) for error in residuals),
        rms_error_seconds=rms_error,
        success=bool(best.success),
        message=str(best.message),
    )