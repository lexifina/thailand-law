"""Fetching from the Office of the Council of State (สำนักงานคณะกรรมการกฤษฎีกา, OCS) law database.

The public site https://searchlaw.ocs.go.th/council-of-state/ is an Angular app over a JSON API at /ocs-api. One call,
`/public/doc/getLawDoc` (service `getPublicLawDoc`), returns one version of a law ("timeline"): its sections as HTML,
its footnotes, and the list of every timeline of that law (principal act, amending acts, point-in-time consolidations,
the current consolidation). Timeline IDs are opaque strings issued by the site.

Requests go over one persistent HTTPS connection (keep-alive, gzip), at most WORKERS at a time, and every answer is
cached gzip-compressed under .cache/ (negative answers too), so a rebuild reads the same bytes with --offline.
"""
from __future__ import annotations

import gzip
import hashlib
import http.client
import json
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE / '.cache'
HOST = 'searchlaw.ocs.go.th'
API = '/ocs-api'
UA = 'lexifina-git-for-law/1.0 (+https://lexifina.com; corpus@lexifina.com)'
WORKERS = 4
PAUSE = 0.25

REQUESTS: list[dict] = []
_lock = threading.Lock()
_local = threading.local()
_last = [0.0]


def _conn() -> http.client.HTTPSConnection:
    c = getattr(_local, 'conn', None)
    if c is None:
        c = http.client.HTTPSConnection(HOST, timeout=120)
        _local.conn = c
    return c


def _post(path: str, payload: bytes) -> tuple[int, bytes]:
    with _lock:
        wait = _last[0] + PAUSE - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.monotonic()
    for attempt in range(2):
        c = _conn()
        try:
            c.request('POST', API + path, body=payload, headers={
                'Content-Type': 'application/json', 'Accept': 'application/json', 'Accept-Encoding': 'gzip',
                'User-Agent': UA, 'Connection': 'keep-alive'})
            r = c.getresponse()
            body = r.read()
            if r.getheader('Content-Encoding') == 'gzip':
                body = gzip.decompress(body)
            return r.status, body
        except (http.client.HTTPException, OSError):
            c.close()
            _local.conn = None
            if attempt:
                raise
    raise AssertionError


def _payload(service: str, body: dict) -> bytes:
    # The request envelope the site's own client sends (reqHeader with a service name); the IDs are fixed so a
    # request is the same bytes every time (the cache key is the service and body only).
    return json.dumps({'reqHeader': {'reqId': '0', 'reqChannel': 'WEB', 'reqDtm': '2026-10-28 12:00:00.000',
                                     'reqBy': 'unknow', 'serviceName': service, 'uuid': 'lexifina',
                                     'sessionId': 'lexifina'},
                       'reqBody': body}, ensure_ascii=True, sort_keys=True).encode()


def call(path: str, service: str, body: dict, offline: bool = False) -> dict:
    key = json.dumps([path, service, body], ensure_ascii=True, sort_keys=True)
    h = hashlib.sha256(key.encode()).hexdigest()[:32]
    p = CACHE / (h + '.json.gz')
    err = CACHE / (h + '.err')
    with _lock:
        REQUESTS.append({'path': path, 'service': service, 'body': body, 'file': p.name})
    if p.exists():
        return json.loads(gzip.decompress(p.read_bytes()))
    if err.exists():
        raise LookupError(f'{key}: {err.read_text(encoding="utf-8")}')
    if offline:
        raise SystemExit(f'not cached: {key}')
    CACHE.mkdir(parents=True, exist_ok=True)
    (CACHE / '.gitignore').write_text('*\n')
    for attempt in range(4):
        status, raw = _post(path, _payload(service, body))
        if status == 200:
            d = json.loads(raw)
            code = (d.get('respHeader') or {}).get('errorCode')
            if code == 'SUCCESS':
                p.write_bytes(gzip.compress(raw, 9, mtime=0))
                return d
            if code and code.endswith('CIPHER_EXCEPTION'):
                err.write_text(code, encoding='utf-8')
                raise LookupError(f'{key}: {code}')
        elif 400 <= status < 500:
            err.write_text(f'HTTP {status}', encoding='utf-8')
            raise LookupError(f'{key}: HTTP {status}')
        time.sleep(3 * (attempt + 1))
    raise RuntimeError(f'{key}: no answer after 4 tries')


def law_doc(timeline_id: str, offline: bool = False) -> dict:
    return call('/public/doc/getLawDoc', 'getPublicLawDoc', {'isTransEng': False, 'timelineId': timeline_id},
                offline)['respBody']
