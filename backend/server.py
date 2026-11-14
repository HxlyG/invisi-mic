import json
from pathlib import Path
from sim.sim import shoebox_simulation, get_materials

from flask import Flask, jsonify, request

app = Flask(__name__)

SIM_DIR = Path(__file__).parent

@app.get("/")
def index():
    return jsonify({"status": "ok", "service": "invisi-mic"})

@app.get("/materials")
def materials():
    return jsonify({"materials": list(get_materials())})

@app.route("/data", methods=["POST"])
def data():
    sim = request.get_json()

    sim_path = SIM_DIR / Path(sim).name
    if not sim_path.is_file():
        return jsonify({"error": f"unknown sim: {sim}"}), 404

    with sim_path.open() as f:
        config = json.load(f)

    is_2_dimensional = config.get("is_2_dimensional", False)
    shoebox = config.get("shoebox", [])
    mics = config.get("mics", [])
    talkers = config.get("talkers", [])

    shoebox_simulation(shoebox, mics, talkers)

    return jsonify(
        {
            "sim": sim,
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
