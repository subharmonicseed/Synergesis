# smoke_test.py
import argparse, itertools, json, random, string, time
import requests
try:
    import sseclient
except ImportError:
    print("[!] Please install sseclient: pip install sseclient-py")
    exit(1)

def rand_pattern(prefix="p"):
    letters = string.ascii_lowercase
    return f"{prefix}-" + "".join(random.choice(letters) for _ in range(6))

def post_pattern(base, pattern):
    r = requests.post(f"{base}/process", json={"state": [random.random() for _ in range(4)], "context": pattern})
    r.raise_for_status()
    return r.json()

def watch_sse(base, timeout=5):
    import requests
    try:
        client = sseclient.SSEClient(f"{base}/stream")
        start = time.time()
        for evt in client.events():
            data = evt.data
            if isinstance(data, bytes):
                data = data.decode(errors='replace')
            print("SSE:", data)
            if time.time() - start > timeout:
                break
    except Exception as e:
        print("[SSE fallback] Streaming with requests due to:", e)
        with requests.get(f"{base}/stream", stream=True) as resp:
            start = time.time()
            for line in resp.iter_lines():
                if line:
                    try:
                        decoded = line.decode(errors='replace') if isinstance(line, bytes) else str(line)
                        if decoded.startswith('data:'):
                            print("SSE:", decoded[5:].strip())
                    except Exception as err:
                        print("[SSE parse error]", err)
                if time.time() - start > timeout:
                    break

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://localhost:8000")
    p.add_argument("--n", type=int, default=10, help="# patterns")
    args = p.parse_args()

    for i in range(args.n):
        pat = rand_pattern()
        print(f"posting {pat}")
        post_pattern(args.url, pat)

    print("\n--- /cluster_info ---")
    print(requests.get(f"{args.url}/cluster_info").json())

    print("\n--- /metrics ---")
    print(requests.get(f"{args.url}/metrics").json())

    print("\n--- SSE (5 s) ---")
    watch_sse(args.url)

if __name__ == "__main__":
    main()
