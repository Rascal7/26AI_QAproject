"""Small Streamable HTTP MCP client. Credentials stay in the ignored .env."""

import json
import sys
from pathlib import Path
import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


def request(method, params):
    key = dotenv_values(ROOT / '.env').get('STITCH_API_KEY')
    headers = {'X-Goog-Api-Key': key, 'Accept': 'application/json, text/event-stream'}
    with httpx.Client(timeout=240) as client:
        response = client.post(
            'https://stitch.googleapis.com/mcp',
            headers=headers,
            json={'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params},
        )
        if response.status_code != 200:
            raise RuntimeError(f'Stitch HTTP {response.status_code}: {response.text[:1000].replace(key, "[REDACTED]")}')
        if 'text/event-stream' in response.headers.get('content-type', ''):
            messages = [json.loads(line[5:].strip()) for line in response.text.splitlines() if line.startswith('data:')]
            return next(m for m in reversed(messages) if m.get('id') == 1)
        return response.json()


if __name__ == '__main__':
    method = sys.argv[1]
    params = json.loads(Path(sys.argv[2]).read_text(encoding='utf-8-sig')) if len(sys.argv) > 2 else {}
    result = request(method, params)
    if method == 'tools/list' and len(sys.argv) <= 3:
        result = [{k: t[k] for k in ('name', 'description', 'inputSchema')} for t in result['result']['tools']]
    if len(sys.argv) > 3:
        Path(sys.argv[3]).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        print('Saved response:', sys.argv[3])
    else:
        print(json.dumps(result, ensure_ascii=False))
