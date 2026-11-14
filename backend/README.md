testing:
{"is_2_dimensional":  true, "shoebox": [2, 2], "mics": [[0, 1], [1, 0]], "talkers": [[0.5, 0.5], [1.5, 1.5]]}

POST http://127.0.0.1:5000/data
Content-Type: application/json

{"is_2_dimensional":true,"shoebox":[2,2],"mics":[[0,1],[1,0]],"talkers":[[0.5,0.5],[1.5,1.5]]}

Returns JSON with the submitted config and opens the room plot.