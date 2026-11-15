import math
import threading

from sim.sim import get_materials, shoebox_simulation

from flask import Flask, jsonify, request

app = Flask(__name__)

sim_lock = threading.Lock()


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _validate_config(config):
    shoebox = config.get("shoebox")
    if not isinstance(shoebox, list) or len(shoebox) not in (2, 3):
        return "shoebox must be a list of 2 or 3 dimensions"
    if not all(_is_number(d) and math.isfinite(d) and d > 0 for d in shoebox):
        return "shoebox dimensions must be positive finite numbers"

    is_2_dimensional = config.get("is_2_dimensional")
    if is_2_dimensional is not None:
        if not isinstance(is_2_dimensional, bool):
            return "is_2_dimensional must be a boolean"
        if is_2_dimensional != (len(shoebox) == 2):
            return (
                f"is_2_dimensional={is_2_dimensional} is inconsistent with "
                f"a {len(shoebox)}D shoebox"
            )

    dim = len(shoebox)
    for key in ("mics", "talkers"):
        points = config.get(key)
        if not isinstance(points, list) or not points:
            return f"{key} must be a non-empty list of points"
        for i, point in enumerate(points):
            if not isinstance(point, list) or len(point) != dim:
                return f"{key}[{i}] must have {dim} coordinates"
            if not all(_is_number(c) and math.isfinite(c) for c in point):
                return f"{key}[{i}] coordinates must be finite numbers"
            for axis, (c, size) in enumerate(zip(point, shoebox)):
                if c < 0 or c > size:
                    return (
                        f"{key}[{i}] is outside the shoebox on axis {axis}: "
                        f"{c} not in [0, {size}]"
                    )

    return None

@app.get("/")
def index():
    return jsonify({"status": "ok", "service": "invisi-mic"})

@app.get("/materials")
def materials():
    return jsonify({"materials": list(get_materials())})

@app.route("/data", methods=["POST"])
def data():
    config = request.get_json(silent=True)
    if not isinstance(config, dict):
        return jsonify({"error": "expected a JSON object body"}), 400

    error = _validate_config(config)
    if error:
        return jsonify({"error": error}), 400

    shoebox = config["shoebox"]
    mics = config["mics"]
    talkers = config["talkers"]
    is_2_dimensional = config.get("is_2_dimensional", len(shoebox) == 2)

    with sim_lock:
        shoebox_simulation(shoebox, mics, talkers)

    return jsonify(
        {
            "sim": config,
            "is_2_dimensional": is_2_dimensional,
            "shoebox": shoebox,
            "mics": mics,
            "talkers": talkers,
        }
    )


@app.post("/echo")
def echo():
    data = request.get_json(silent=True) or {}
    return jsonify({"received": data})
