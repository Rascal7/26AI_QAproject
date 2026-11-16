import json
from pathlib import Path

root = Path('docs/design')
d = json.loads((root / 'stitch-home-response.json').read_text(encoding='utf-8'))['result']['structuredContent']


def walk(x):
    if isinstance(x, dict):
        if 'htmlCode' in x or 'screenshot' in x:
            print(
                json.dumps(
                    {k: v for k, v in x.items() if k in ('name', 'id', 'title', 'htmlCode', 'screenshot')},
                    ensure_ascii=False,
                )
            )
            for kind, field in [('html', 'htmlCode'), ('image', 'screenshot')]:
                if field in x:
                    (root / f'stitch-{kind}-request.json').write_text(
                        json.dumps({'name': 'download_file', 'arguments': {'name': x[field]['name']}}), encoding='utf-8'
                    )
        if 'designMd' in x:
            (root / 'STITCH_DESIGN.md').write_text(x['designMd'], encoding='utf-8')
        for v in x.values():
            walk(v)
    elif isinstance(x, list):
        for v in x:
            walk(v)


walk(d)
for x in d.get('outputComponents', []):
    if x.get('text'):
        print(x['text'])
