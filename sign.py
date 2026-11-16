#!/usr/bin/env python3
"""Sign panel.json into endpoints.json for the Arthur VPN app.

Only the Python standard library and the openssl command are used.
  python sign.py --key-id k1 --key-file /path/k1-private.pem
  python sign.py --check            (verify endpoints.json with keys/*.pub.pem)
The private key never needs to be stored in this repository.
"""
import argparse, base64, json, os, re, subprocess, sys, tempfile, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCHEMA, APP = 'arthur-endpoints-v1', 'arthur-vpn'
VALID_DAYS = 90
HOST = re.compile(r'(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z][a-z0-9-]{0,61}[a-z0-9]')


def origin(value):
    v = str(value).strip().rstrip('/')
    if not v.startswith('https://'): raise SystemExit('Panel must start with https:// : ' + v)
    host = v[8:].lower()
    if len(host) > 253 or not HOST.fullmatch(host): raise SystemExit('Panel must be https://host only (no port/path): ' + v)
    return 'https://' + host


def openssl(*args, data=None):
    exe = os.environ.get('OPENSSL', 'openssl')
    return subprocess.run([exe, *args], input=data, capture_output=True, check=True).stdout


def previous():
    path = ROOT / 'endpoints.json'
    if not path.is_file(): return None
    outer = json.loads(path.read_text(encoding='utf-8'))
    return json.loads(base64.b64decode(outer['payload']))


def sign(key_id, key_file):
    wanted = json.loads((ROOT / 'panel.json').read_text(encoding='utf-8'))
    panels = [origin(p) for p in wanted['panels']]
    if not 1 <= len(panels) <= 5: raise SystemExit('panels needs 1 to 5 entries')
    revoked = sorted(set(wanted.get('revoked_keys', [])))
    if key_id in revoked: raise SystemExit('A key cannot sign a file that revokes itself')
    old = previous()
    seq = 1
    if old:
        same = old.get('panels') == panels and sorted(old.get('revoked_keys', [])) == revoked
        seq = int(old['seq']) if same else int(old['seq']) + 1  # Any change is newer; re-signing keeps the number.
    now = int(time.time())
    body = {'schema': SCHEMA, 'app': APP, 'seq': seq, 'issued': now, 'expires': now + VALID_DAYS * 86400,
            'panels': panels, 'revoked_keys': revoked}
    payload = json.dumps(body, separators=(',', ':'), ensure_ascii=True).encode()
    with tempfile.TemporaryDirectory() as d:
        data = Path(d) / 'payload'; data.write_bytes(payload)
        sig = openssl('dgst', '-sha256', '-sign', str(key_file), str(data))
    out = {'key': key_id, 'payload': base64.b64encode(payload).decode(), 'sig': base64.b64encode(sig).decode()}
    (ROOT / 'endpoints.json').write_text(json.dumps(out, indent=2) + '\n', encoding='utf-8', newline='\n')
    print('Signed endpoints.json seq=%d key=%s panels=%s expires in %d days' % (seq, key_id, ', '.join(panels), VALID_DAYS))


def check():
    outer = json.loads((ROOT / 'endpoints.json').read_text(encoding='utf-8'))
    pub = ROOT / 'keys' / (outer['key'] + '.pub.pem')
    if not pub.is_file(): raise SystemExit('Unknown key id ' + outer['key'])
    payload, sig = base64.b64decode(outer['payload']), base64.b64decode(outer['sig'])
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / 'p').write_bytes(payload); (Path(d) / 's').write_bytes(sig)
        result = subprocess.run([os.environ.get('OPENSSL', 'openssl'), 'dgst', '-sha256', '-verify', str(pub), '-signature', str(Path(d) / 's'), str(Path(d) / 'p')], capture_output=True)
    if result.returncode: raise SystemExit('Signature check FAILED')
    body = json.loads(payload)
    assert body['schema'] == SCHEMA and body['app'] == APP and body['expires'] > time.time(), 'Payload invalid or expired'
    for p in body['panels']: origin(p)
    print('PASS endpoints.json seq=%s key=%s panels=%s' % (body['seq'], outer['key'], ', '.join(body['panels'])))


if __name__ == '__main__':
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument('--key-id', choices=['k1', 'k2']); a.add_argument('--key-file'); a.add_argument('--check', action='store_true')
    args = a.parse_args()
    if args.check: check()
    elif args.key_id and args.key_file: sign(args.key_id, args.key_file); check()
    else: a.error('use --check, or --key-id with --key-file')
