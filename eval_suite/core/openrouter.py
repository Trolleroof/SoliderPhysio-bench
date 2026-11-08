"""Small stdlib-only OpenRouter transport. Accounting belongs to the caller."""
import json
import os
from pathlib import Path
import urllib.error
import urllib.request

ENDPOINT = 'https://openrouter.ai/api/v1/chat/completions'


def api_key(root):
    key = os.environ.get('OPENROUTER_API_KEY')
    if not key:
        path = Path(root)/'.env'
        if path.is_file():
            for line in path.read_text().splitlines():
                name, sep, value = line.strip().removeprefix('export ').partition('=')
                if sep and name.strip() == 'OPENROUTER_API_KEY':
                    key = value.strip().strip('\"\'')
    if not key:
        raise ValueError('OPENROUTER_API_KEY is missing; supply it in the environment or repo-root .env')
    return key


class OpenRouterClient:
    def __init__(self, key, timeout_s=300):
        self.key, self.timeout_s = key, timeout_s

    def complete(self, body, *, timeout_s=None):
        request = urllib.request.Request(ENDPOINT, data=json.dumps(body, allow_nan=False).encode(),
                                        headers={'Authorization': 'Bearer '+self.key,
                                                 'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(request, timeout=min(timeout_s or self.timeout_s, self.timeout_s)) as r:
                raw = r.read().decode()
        except urllib.error.HTTPError as exc:
            # Provider bodies can echo headers or inputs; never log credentials.
            raise RuntimeError(f'OpenRouter HTTP {exc.code}') from None
        data = json.loads(raw)
        if data.get('error'):
            raise RuntimeError('OpenRouter returned an API error')
        message = data['choices'][0]['message']
        return {'text': message.get('content') or '', 'message': message,
                'usage': data.get('usage') or {}, 'raw': data,
                'finish_reason': data['choices'][0].get('finish_reason')}
