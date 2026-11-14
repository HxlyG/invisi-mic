import requests

url = "http://127.0.0.1:5000/data"

sim = {
    "is_2_dimensional": True,
    "shoebox": [2, 2],
    "mics": [[0, 1], [1, 0]],
    "talkers": [[0.5, 0.5], [1.5, 1.5]]
}

response = requests.post(url, json=sim)

print("Status:", response.status_code)
print("Response:", response.text)