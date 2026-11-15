import math
import threading

from sim.sim import get_material_absorption, get_materials, mic_focus_targets, shoebox_simulation

from flask import Flask, jsonify, request

app = Flask(__name__)

sim_lock = threading.Lock()

# Base64 characters; roughly 3 MB of WAV per talker.
MAX_AUDIO_CHARS = 4_000_000

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

    if not shoebox or not mics or not talkers:
        return jsonify({"error": "shoebox, mics, and talkers are required"}), 400
    if not isinstance(mics, list) or not isinstance(talkers, list):
        return jsonify({"error": "mics and talkers must be lists"}), 400

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

    talker_audio = config.get("talker_audio") or [None] * len(talkers)
    if (
        not isinstance(talker_audio, list)
        or len(talker_audio) != len(talkers)
        or not all(a is None or (isinstance(a, str) and len(a) <= MAX_AUDIO_CHARS) for a in talker_audio)
    ):
        return jsonify({"error": "talker_audio must hold one base64 WAV or null per talker"}), 400

    with sim_lock:
        try:
            result = shoebox_simulation(shoebox, mics, talkers, material, talker_audio, outline)
        except ValueError as error:
            return jsonify({"error": str(error)}), 400

    return jsonify(
        {
            "sim": {key: value for key, value in config.items() if key != "talker_audio"},
            "is_2_dimensional": is_2_dimensional,
            "shoebox": shoebox,
            "outline": outline,
            "mics": mics,
            "talkers": talkers,
            "material": material,
            "talker_tracks": talker_tracks,
            "focus": mic_focus_targets(mics, talkers, mic_focus),
            "rt60": result["rt60"],
            "audio": result["audio"],
            "mic_audio": [
                {"mic_index": index, "position": position, "audio": result["audio"][index]}
                for index, position in enumerate(mics)
            ] if result["audio"] is not None else [],
        }
    )


@app.post("/echo")
def echo():
    data = request.get_json(silent=True) or {}
    return jsonify({"received": data})
