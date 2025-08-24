import json
import sys
import urllib.request
import urllib.error

URL = 'http://localhost:8051/mcp'
TIMEOUT = 15


def post_json(data: dict, extra_headers: dict | None = None):
    body = json.dumps(data).encode('utf-8')
    req = urllib.request.Request(URL, data=body, method='POST')
    req.add_header('Content-Type', 'application/json')
    req.add_header('Accept', 'text/event-stream, application/json')
    if extra_headers:
        for k, v in extra_headers.items():
            req.add_header(k, v)
    try:
        resp = urllib.request.urlopen(req, timeout=TIMEOUT)
        status = getattr(resp, 'status', 200)
        headers = dict(resp.headers.items())
        text = resp.read().decode('utf-8', errors='replace') if resp.length else ''
        return status, headers, text
    except urllib.error.HTTPError as e:
        # Even on HTTP errors we want headers (for mcp-session-id)
        status = e.code
        headers = dict(e.headers.items()) if e.headers else {}
        text = e.read().decode('utf-8', errors='replace')
        return status, headers, text
    except Exception as e:
        print(f"Request failed: {e}")
        sys.exit(2)


def main():
    init_payload = {"jsonrpc": "2.0", "id": "1", "method": "initialize", "params": {}}
    s1, h1, b1 = post_json(init_payload)
    sid = h1.get('mcp-session-id')
    print(f"INIT_STATUS={s1}")
    print(f"SESSION={sid}")
    if not sid:
        print("No session id returned; cannot proceed.")
        sys.exit(1)

    list_payload = {"jsonrpc": "2.0", "id": "2", "method": "tools/list", "params": {}}
    s2, h2, b2 = post_json(list_payload, {"mcp-session-id": sid})
    print(f"TOOLS_STATUS={s2}")
    print(b2)


if __name__ == '__main__':
    main()
