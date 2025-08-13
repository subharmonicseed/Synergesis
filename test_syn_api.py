import requests
import json

# 1. POST a pattern
resp = requests.post(
    "http://127.0.0.1:8000/process",
    headers={"Content-Type": "application/json"},
    data=json.dumps({"state": [1, 0], "context": "hello world"})
)
print("POST /process:", resp.status_code, resp.text)

# 2. Send a second pattern
resp2 = requests.post(
    "http://127.0.0.1:8000/process",
    headers={"Content-Type": "application/json"},
    data=json.dumps({"state": [0, 1], "context": "second pattern"})
)
print("POST /process (2):", resp2.status_code, resp2.text)

# 3. GET cluster info again
resp3 = requests.get("http://127.0.0.1:8000/cluster_info")
print("GET /cluster_info (after 2 patterns):", resp3.status_code, resp3.text)

# 4. Stream SSE (prints 3 updates, Python 3.x fix)
import httpx
with httpx.stream("GET", "http://127.0.0.1:8000/stream") as r:
    for i, line in enumerate(r.iter_lines()):
        if line:
            print("SSE:", line)
        if i >= 2:
            break
