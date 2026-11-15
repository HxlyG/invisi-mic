testing:
{"is_2_dimensional": true, "shoebox": [2, 2], "mics": [[0, 1], [1, 0]], "talkers": [[0.5, 0.5], [1.5, 1.5]]}

GET http://127.0.0.1:5000/materials

Returns {"materials": [...], "absorption": {name: mean coefficient}}.

POST http://127.0.0.1:5000/data
Content-Type: application/json

{"is_2_dimensional":true,"shoebox":[2,2],"mics":[[0,1],[1,0]],"talkers":[[0.5,0.5],[1.5,1.5]],"material":"brickwork","talker_tracks":["lecture",null],"mic_focus":[1,null]}

Optional fields: outline (list of [x, y] floor points; the room becomes that polygon, extruded to shoebox[2] in 3D, and mics/talkers must be inside it), material (a name from /materials), talker_tracks (track id or null per talker), mic_focus (talker index, or null for nearest, per mic), talker_audio (base64 16 kHz mono WAV or null per talker).

Returns JSON with the submitted config, focus (target talker and distance per mic), rt60 (seconds, null without a material), and audio (base64 WAV per mic, null when no talker has audio).
