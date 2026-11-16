import base64, json, subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
repo = 'repos/Rascal7/26AI_QAproject'


def api(path, payload=None):
    args = ['gh', 'api', repo + '/' + path]
    if payload is not None:
        args += ['--method', 'POST', '--input', '-']
    result = subprocess.run(
        args,
        input=json.dumps(payload) if payload is not None else None,
        text=True,
        encoding='utf-8',
        capture_output=True,
        check=True,
    )
    return json.loads(result.stdout)


head = api('git/ref/heads/main')['object']['sha']
commit = api('git/commits/' + head)
entries = []
for local, remote in [
    ('docs/github-readme.md', 'README.md'),
    ('docs/images/requirements.png', 'docs/images/requirements.png'),
    ('docs/images/test-cases.png', 'docs/images/test-cases.png'),
    ('docs/images/dashboard.png', 'docs/images/dashboard.png'),
]:
    blob = api('git/blobs', {'encoding': 'base64', 'content': base64.b64encode((root / local).read_bytes()).decode()})
    entries.append({'path': remote, 'mode': '100644', 'type': 'blob', 'sha': blob['sha']})
tree = api('git/trees', {'base_tree': commit['tree']['sha'], 'tree': entries})
new = api(
    'git/commits',
    {'message': 'docs: replace UI wireframes with actual app screenshots', 'tree': tree['sha'], 'parents': [head]},
)
if api('git/ref/heads/main')['object']['sha'] != head:
    raise RuntimeError('Remote main changed; inspect before retrying')
api('git/refs/heads/main', {'sha': new['sha'], 'force': False})
print(new['sha'])
