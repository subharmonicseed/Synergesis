import sys

import requests


def check_sse(url):
    try:
        # Try to get headers and not stream forever
        r = requests.get(url, stream=True, timeout=5)
        print(f"SSE endpoint {url} status: {r.status_code}")
        # Read a small chunk if available
        try:
            it = r.iter_lines()
            first = next(it, None)
            print("SSE first line:", first)
        except Exception as e:
            print("SSE read error:", e)
    except Exception as e:
        print(f"SSE check failed for {url}: {e}")


def check_mcp(url):
    try:
        payload = {"jsonrpc": "2.0", "method": "health_check", "id": 1, "params": {}}
        headers = {"Accept": "application/json, text/event-stream"}
        r = requests.post(url, json=payload, timeout=5, headers=headers)
        print(f"MCP endpoint {url} status: {r.status_code}")
        print("Response:", r.text)
    except Exception as e:
        print(f"MCP check failed for {url}: {e}")


if __name__ == '__main__':
    host = 'http://localhost:8051'
    sse = f"{host}/sse"
    mcp = f"{host}/mcp"

    print('Running MCP endpoint smoke tests against', host)
    check_sse(sse)
    check_mcp(mcp)
    sys.exit(0)
