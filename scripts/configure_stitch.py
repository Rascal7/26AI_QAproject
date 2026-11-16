"""Register the user-authorized Stitch server without printing credentials."""

import json
import tomllib
from pathlib import Path
from dotenv import dotenv_values

path = Path.home() / '.codex/config.toml'
text = path.read_text(encoding='utf-8-sig') if path.exists() else ''
config = tomllib.loads(text)
if 'stitch' in config.get('mcp_servers', {}):
    print('Stitch already configured; preserved existing settings.')
else:
    key = dotenv_values(Path(__file__).resolve().parents[1] / '.env')['STITCH_API_KEY']
    updated = (
        text
        + '\n[mcp_servers.stitch]\nurl = "https://stitch.googleapis.com/mcp"\n\n[mcp_servers.stitch.http_headers]\n"X-Goog-Api-Key" = '
        + json.dumps(key)
        + '\n'
    )
    tomllib.loads(updated)
    path.write_text(updated, encoding='utf-8')
    print('Stitch MCP registered. Existing settings preserved.')
