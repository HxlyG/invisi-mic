# BeamStage backend

Flask API that simulates a room with pyroomacoustics, localizes the talkers and beamforms each one out of the mic recordings. The request and response format is documented in the [root README](../README.md#backend-api).

## Layout

| Path                    | Contents                                                                    |
| ----------------------- | --------------------------------------------------------------------------- |
| `src/main.py`           | Entry point; serves the API on port 8080                                    |
| `src/server.py`         | Flask routes (`GET /`, `GET /materials`, `POST /data`)                      |
| `src/Simulation/`       | Room simulation (`sim.py`) and test-signal helpers (`signals.py`)           |
| `src/Algorithm/`        | GCC-PHAT, TDOA, onset detection, position solver, calibration, beamformer   |
| `tests/`                | Unit tests and the experiment scripts (`tests/visualization/` plots results) |
| `scripts/`              | Manual helpers, such as `post_sim.py` which posts a small simulation        |
| `examples/`             | Sample simulation JSON and a test ping sound                                |
| `data/`                 | Local datasets (LibriSpeech); not committed                                 |

Plots from earlier experiments are kept in [`../docs/images`](../docs/images).

## Run

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 src/main.py
```

The server does not auto-reload, so restart it after changing backend code.

## Test

```bash
python3 -m pytest
```
