import base64
import io
import math

import numpy as np
import pyroomacoustics as pra
from scipy.io import wavfile

SAMPLE_RATE = 16000
DURATION_SECONDS = 30
IMAGE_BUDGET = 20_000
INPUT_RMS = 0.1
OUTPUT_RMS = 0.25
MAX_ORDER = 8

def get_materials():
    return pra.parameters.materials_absorption_table.keys()

def get_material_absorption():
    table = pra.parameters.materials_absorption_table
    return {name: float(np.mean(entry["coeffs"])) for name, entry in table.items()}

def add_mics(mic_positions: list[list[float]], room: pra.Room):
    for mic in mic_positions:
        room.add_microphone(mic)

def add_sources(talker_positions: list[list[float]], room: pra.Room, signals):
    # pyroomacoustics can't simulate sources without a signal, so silent talkers are skipped.
    for talker, signal in zip(talker_positions, signals):
        if signal is not None:
            room.add_source(talker, signal=signal)

def decode_wav(encoded: str):
    rate, data = wavfile.read(io.BytesIO(base64.b64decode(encoded, validate=True)))
    if data.ndim > 1:
        data = data.mean(axis=1)
    if np.issubdtype(data.dtype, np.integer):
        data = data / np.iinfo(data.dtype).max
    return rate, data.astype(np.float64)

def encode_wav(signal: np.ndarray):
    buffer = io.BytesIO()
    wavfile.write(buffer, SAMPLE_RATE, (np.clip(signal, -1, 1) * 32767).astype(np.int16))
    return base64.b64encode(buffer.getvalue()).decode("ascii")

def mic_focus_targets(mic_positions, talker_positions, mic_focus):
    # A null focus entry means the mic aims at its nearest talker.
    mics = np.asarray(mic_positions, dtype=float)
    talkers = np.asarray(talker_positions, dtype=float)
    targets = []
    for i, mic in enumerate(mics):
        distances = np.linalg.norm(talkers - mic, axis=1)
        index = mic_focus[i] if mic_focus[i] is not None else int(np.argmin(distances))
        targets.append({"mic": i, "talker": index, "distance": float(distances[index])})
    return targets

def build_room(shoebox_dims, outline, material):
    if not outline:
        materials = pra.Material(material) if material else None
        return pra.ShoeBox(shoebox_dims, fs=SAMPLE_RATE, materials=materials, max_order=MAX_ORDER)

    points = np.asarray(outline, dtype=float)
    if points.ndim != 2 or points.shape[1] != 2:
        raise ValueError("outline must hold [x, y] points")
    # Drop repeated consecutive points (including closing duplicates), which would make zero-length walls.
    keep = np.any(points != np.roll(points, 1, axis=0), axis=1)
    corners = points[keep].T
    if corners.shape[1] < 3:
        raise ValueError("outline must hold at least three [x, y] points")
    # Shoelace area; zero means the points are collinear.
    x, y = corners
    if abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))) < 1e-9:
        raise ValueError("outline must enclose a non-zero area")

    # Each wall needs its own Material because pyroomacoustics resamples them in place.
    n_walls = corners.shape[1] + (2 if len(shoebox_dims) == 3 else 0)
    # Image sources grow roughly as walls**order, so many-walled rooms get a lower order.
    max_order = int(min(MAX_ORDER, max(1, math.log(IMAGE_BUDGET) / math.log(n_walls))))
    walls = [pra.Material(material) for _ in range(corners.shape[1])] if material else None
    room = pra.Room.from_corners(corners, fs=SAMPLE_RATE, max_order=max_order, materials=walls)
    if len(shoebox_dims) == 3:
        room.extrude(float(shoebox_dims[2]), materials=pra.Material(material) if material else None)
    return room

def check_inside(room, positions, label):
    for index, position in enumerate(positions):
        if not room.is_inside(np.asarray(position, dtype=float)):
            raise ValueError(f"{label} {index} is outside the room outline")
    
    

def shoebox_simulation(
    shoebox_dims,
    mic_positions,
    talker_positions: list[list[float]],
    material=None,
    talker_audio=None,
    outline=None,
):
    room = build_room(shoebox_dims, outline, material)
    if outline:
        check_inside(room, mic_positions, "mic")
        check_inside(room, talker_positions, "talker")

    talker_audio = talker_audio or [None] * len(talker_positions)
    signals = []
    for encoded in talker_audio:
        if encoded is None:
            signals.append(None)
            continue
        rate, data = decode_wav(encoded)
        if rate != SAMPLE_RATE:
            raise ValueError(f"talker audio must be {SAMPLE_RATE} Hz WAV")
        if data.size == 0:
            raise ValueError("talker audio is empty")
        # np.resize repeats short clips so every talker fills the full duration.
        signal = np.resize(data, SAMPLE_RATE * DURATION_SECONDS)
        # Equal input loudness keeps quiet recordings (like the lecture) audible next to loud ones.
        signals.append(signal * (INPUT_RMS / max(float(np.sqrt(np.mean(signal**2))), 1e-9)))

    add_sources(talker_positions, room, signals)
    add_mics(mic_positions, room)

    mixed = None
    if any(signal is not None for signal in signals):
        room.simulate()
        mixed = room.mic_array.signals[:, : SAMPLE_RATE * DURATION_SECONDS]
        # One shared gain keeps the relative level between mics; tanh soft-limits the loudest peaks.
        channel_rms = np.sqrt(np.mean(mixed**2, axis=1))
        mixed = np.tanh(mixed * (OUTPUT_RMS / max(float(np.median(channel_rms)), 1e-9))) * 0.95

    # Without a material the room is perfectly reflective and RT60 is infinite.
    rt60 = float(room.rt60_theory())
    return {"rt60": rt60 if np.isfinite(rt60) else None, "audio": mixed}
