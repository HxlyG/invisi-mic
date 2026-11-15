import math
import threading

from Simulation.sim import get_material_absorption, get_materials, mic_focus_targets, shoebox_simulation, encode_wav
from Algorithm.tdoa import estimate_tdoa, estimate_tdoa_with_onset_window
from Algorithm.beamformer import beamform_talkers
from Algorithm.solver import solve_position

import numpy as np
from flask import Flask, jsonify, request

app = Flask(__name__)

sim_lock = threading.Lock()

# Base64 characters; roughly 3 MB of WAV per talker.
MAX_AUDIO_CHARS = 4_000_000

# Constants for simulation and sound localization
SAMPLE_RATE = 16000
SPEED_OF_SOUND = 343.0

# Linear boost on the beamformed audio (about +14 dB); tanh soft-limits the peaks it would push past full scale.
BEAM_GAIN = 5.0

# The simulation truncates reflections, so its tail decays faster than the theoretical RT60 for reflective rooms.
MAX_REVERB_TIME = 0.8

def _validate_config(config):
    shoebox = config.get("shoebox")
    mics = config.get("mics")
    talkers = config.get("talkers")
    if not shoebox or not mics or not talkers:
        return "shoebox, mics, and talkers are required"
    if not isinstance(mics, list) or not isinstance(talkers, list):
        return "mics and talkers must be lists"
    return None

@app.get("/")
def index():
    return jsonify({"status": "ok", "service": "invisi-mic"})

@app.get("/materials")
def materials():
    return jsonify({"materials": list(get_materials()), "absorption": get_material_absorption()})

@app.route("/data", methods=["POST"])
def data():
    config = request.get_json(silent=True)
    if not isinstance(config, dict):
        return jsonify({"error": "expected a JSON object body"}), 400

    error = _validate_config(config)
    if error:
        return jsonify({"error": error}), 400

    shoebox = config.get("shoebox")
    mics = config.get("mics")
    talkers = config.get("talkers")

    # Determine if the simulation space is 2D based on shoebox dimensions
    is_2_dimensional = len(shoebox) == 2 if isinstance(shoebox, list) else False

    # 1. Extract and validate outline BEFORE simulation
    outline = config.get("outline")
    if outline is not None and (
        not isinstance(outline, list)
        or len(outline) < 3
        or not all(
            isinstance(point, list)
            and len(point) == 2
            and all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in point)
            for point in outline
        )
    ):
        return jsonify({"error": "outline must be a list of at least three [x, y] points"}), 400

    # 2. Extract and validate material BEFORE simulation
    material = config.get("material")
    if material is not None and material not in get_materials():
        return jsonify({"error": f"unknown material: {material}"}), 400

    talker_tracks = config.get("talker_tracks") or [None] * len(talkers)
    if (
        not isinstance(talker_tracks, list)
        or len(talker_tracks) != len(talkers)
        or not all(track is None or isinstance(track, str) for track in talker_tracks)
    ):
        return jsonify({"error": "talker_tracks must hold one track id or null per talker"}), 400

    mic_focus = config.get("mic_focus") or [None] * len(mics)
    if (
        not isinstance(mic_focus, list)
        or len(mic_focus) != len(mics)
        or not all(f is None or (isinstance(f, int) and 0 <= f < len(talkers)) for f in mic_focus)
    ):
        return jsonify({"error": "mic_focus must hold one talker index or null per mic"}), 400

    # 3. Extract and validate talker_audio BEFORE simulation
    talker_audio = config.get("talker_audio") or [None] * len(talkers)
    if (
        not isinstance(talker_audio, list)
        or len(talker_audio) != len(talkers)
        or not all(a is None or (isinstance(a, str) and len(a) <= MAX_AUDIO_CHARS) for a in talker_audio)
    ):
        return jsonify({"error": "talker_audio must hold one base64 WAV or null per talker"}), 400

    # 4. Now all variables are defined and validated, call simulation safely
    with sim_lock:
        try:
            result = shoebox_simulation(shoebox, mics, talkers, material, talker_audio, outline)
        except ValueError as err:
            return jsonify({"error": str(err)}), 400
        
    audio_channels = result["audio"]
    if audio_channels is None:
        audio_channels = []
    estimated_positions = []
    beamformed_list = []

    # Beams come from the recorded mixture only; talkers without audio make no sound to isolate.
    beams = {}
    audible = [index for index, track in enumerate(talker_audio) if track is not None]
    if result["linear_audio"] is not None:
        try:
            beams = dict(zip(audible, beamform_talkers(
                result["linear_audio"],
                mics,
                [talkers[index] for index in audible],
                SAMPLE_RATE,
                SPEED_OF_SOUND,
                reverb_time=min(result["rt60"] or MAX_REVERB_TIME, MAX_REVERB_TIME),
            )))
        except Exception as e:
            print(f"Error beamforming: {e}")

    for talker_index, talker_pos in enumerate(talkers):
        try:
            # 1. Compute TDOA relative to the current talker / onset window
            raw_tdoa = estimate_tdoa_with_onset_window(
                audio_channels, 
                SAMPLE_RATE, 
                max_inter_mic_delay_s=0.01, 
                pre_roll_s=0.01, 
                event_duration_s=0.1, 
                noise_window_s=(0.0, 0.1)
            )
            tdoa_result = raw_tdoa[0] if isinstance(raw_tdoa, tuple) else raw_tdoa

            # 2. Solve position independently
            sound_localization_result = solve_position(
                mics, 
                tdoa_result, 
                speed_of_sound=SPEED_OF_SOUND, 
                room_dimensions=shoebox
            )

            if sound_localization_result.success:
                estimated_positions.append(sound_localization_result.position)
            else:
                estimated_positions.append(talker_pos)

        except Exception as e:
            print(f"Error localizing talker {talker_index}: {e}")
            estimated_positions.append(talker_pos)

        beam = beams.get(talker_index)
        if beam is not None:
            beamformed_list.append({
                "talker_index": talker_index,
                "position": talker_pos,
                "audio": encode_wav(np.tanh(beam * BEAM_GAIN)),
            })

    audio = [encode_wav(channel) for channel in audio_channels]

    return jsonify(
        {
            "sim": {key: value for key, value in config.items() if key != "talker_audio"},
            "is_2_dimensional": is_2_dimensional,
            "shoebox": shoebox,
            "outline": outline,
            "mics": mics,
            "talkers": estimated_positions,
            "material": material,
            "talker_tracks": talker_tracks,
            "focus": mic_focus_targets(mics, talkers, mic_focus),
            "rt60": result["rt60"],
            "audio": audio,
            "mic_audio": [
                {"mic_index": index, "position": position, "audio": audio[index]}
                for index, position in enumerate(mics[: len(audio)])
            ],
            "beamformed": beamformed_list,
        }
    )

@app.post("/echo")
def echo():
    data = request.get_json(silent=True) or {}
    return jsonify({"received": data})

if __name__ == "__main__":
    app.run(debug=True)