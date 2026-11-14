import threading

from sim.sim import get_materials, shoebox_simulation

from flask import Flask, jsonify, request

app = Flask(__name__)

sim_lock = threading.Lock()

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

    is_2_dimensional = config.get("is_2_dimensional", False)
    shoebox = config.get("shoebox")
    mics = config.get("mics")
    talkers = config.get("talkers")

    if not shoebox or not mics or not talkers:
        return jsonify({"error": "shoebox, mics, and talkers are required"}), 400

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
