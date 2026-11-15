# invisi-mic (BeamStage)

No more holdables! BeamStage is a browser-based room acoustics simulator for planning invisible microphone arrays. Lay out a room, place talkers and mic arrays, assign audio to each talker, and hear what every mic array would capture.

This is a proof of concept built for MadHacks 2026.

## Features

- **Room editor:** 2D floorplan and 3D isometric views, metric or imperial units, grid snap, and adjustable width, length, and ceiling height.
- **Draw your own room:** Use the Draw room tool to click out a custom polygon outline. Hold Shift to lock walls horizontal or vertical, Backspace to undo a corner, Enter or a click on the first corner to finish, Esc to cancel.
- **Presets:** Lecture hall, comedy club, and large conference room.
- **Talkers and mic arrays:** Place, drag, and set the height of each item. Each mic array can focus on a chosen talker, or on its nearest one, and shows a direction cone.
- **Wall materials:** Pick from the acoustic absorption table in pyroomacoustics. The sidebar shows the room volume.
- **Talker audio:** Choose a bundled clip, upload an MP3 or WAV, or record one from your microphone. Preview a clip before using it.
- **Simulation:** Run the room through pyroomacoustics and play back the mixed audio each mic array hears, along with the room's RT60.
- **Import and export:** Save and load a scene as JSON. Uploaded and recorded audio is not stored in the file and must be selected again after importing.

## Project layout

| Path          | Description                                                             |
| ------------- | ----------------------------------------------------------------------- |
| `invisi-mic/` | Next.js 16 frontend (React 19, Redux Toolkit, three.js, Tailwind CSS 4) |
| `backend/`    | Flask API that runs the acoustic simulation with pyroomacoustics        |

The frontend proxies simulation requests through its own `/api` routes (`/api/simulation`, `/api/materials`), so the browser never talks to the backend directly.

## Getting started

### Requirements

- Node.js 20 or newer
- Python 3.10 or newer

### 1. Start the backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 main.py
```

`main.py` serves the API on port **8080**. The frontend looks for it on port 5000 by default, so point it at the right address (next step), or start the server on port 5000 instead:

```bash
flask --app server run
```

### 2. Start the frontend

```bash
cd invisi-mic
npm install
INVISI_MIC_API_URL=http://127.0.0.1:8080 npm run dev
```

Open [http://localhost:3000](http://localhost:3000). The top bar shows whether the API is connected.

`INVISI_MIC_API_URL` can also be set in `invisi-mic/.env.local`. It defaults to `http://127.0.0.1:5000`.

## Using the app

1. Load a preset from the top bar, or draw your own room.
2. Place talkers and mic arrays with the toolbar, then drag them into position. Shift + drag an item to change its height.
3. Select a talker and choose, upload, or record its audio track.
4. Select a mic array's focus talker, or turn on **Sync mics** to aim every array at one talker.
5. Choose a wall material, then click **Run Simulation**.
6. Use the listen bar at the bottom of the viewport to play what each mic array captured.

In the 3D view, drag to orbit, Shift + drag to pan, and scroll to zoom.

## Backend API

| Method | Path         | Description                                        |
| ------ | ------------ | -------------------------------------------------- |
| `GET`  | `/`          | Health check                                       |
| `GET`  | `/materials` | Available wall materials and their mean absorption |
| `POST` | `/data`      | Run a simulation                                   |

A minimal request:

```json
{
  "is_2_dimensional": true,
  "shoebox": [2, 2],
  "mics": [
    [0, 1],
    [1, 0]
  ],
  "talkers": [
    [0.5, 0.5],
    [1.5, 1.5]
  ]
}
```

Optional fields:

- `outline`: list of `[x, y]` floor points. The room becomes that polygon, extruded to `shoebox[2]` in 3D. Mics and talkers must be inside it.
- `material`: a name from `/materials`.
- `talker_tracks`: a track id or `null` per talker.
- `mic_focus`: a talker index, or `null` for the nearest talker, per mic.
- `talker_audio`: a base64 16 kHz mono WAV, or `null`, per talker.

The response includes the submitted config, the focus target and distance for each mic, `rt60` in seconds (`null` without a material), and a base64 WAV for each mic (`null` when no talker has audio). Audio is simulated at 16 kHz for 30 seconds; shorter clips loop and longer ones are trimmed.

## Development

```bash
cd invisi-mic
npm run dev     # start the dev server
npm run build   # production build
npm run lint    # lint
```

## License

[MIT](LICENSE)
