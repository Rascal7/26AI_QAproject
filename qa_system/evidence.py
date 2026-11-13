import json
import re
import zipfile
from demo_web.seed import PASSWORD, WRONG_PASSWORD


def redact(value, secrets=()):
    if isinstance(value, dict):
        return {k: ('[REDACTED]' if k.lower() in
                {'password', 'password_hash', 'cookie', 'cookies', 'authorization', 'headers', 'postdata'}
                else redact(v, secrets)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v, secrets) for v in value]
    if isinstance(value, str):
        for secret in (PASSWORD, WRONG_PASSWORD, 'invalid-hash-format', *secrets):
            if secret:
                value = value.replace(secret, '[REDACTED]')
        value = re.sub(r'scrypt:[^\s"\']+\$[^\s"\']+\$[0-9a-f]+', '[REDACTED]', value)
        value = re.sub(r'sk-[A-Za-z0-9_-]+', '[REDACTED]', value)
    return value


def sanitize_trace(source, destination, secrets=()):
    # No request/response bodies, headers, DOM snapshots or source files retained.
    with zipfile.ZipFile(source) as src, zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as dst:
        for name in src.namelist():
            if name.endswith('.network'):
                dst.writestr(name, '')
            elif name.endswith('.trace'):
                lines = [json.dumps(redact(json.loads(line), secrets), ensure_ascii=False)
                         for line in src.read(name).decode('utf-8').splitlines() if line.strip()]
                dst.writestr(name, '\n'.join(lines) + '\n')
            elif name.startswith('resources/') and name.endswith(('.png', '.jpeg', '.jpg')):
                dst.writestr(name, src.read(name))
