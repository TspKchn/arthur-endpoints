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


WIN_SCHEMA, WIN_APP = 'arthur-windows-update-v1', 'arthur-vpn-windows'
VERSION = re.compile(r'\d+\.\d+\.\d+\.\d+')


def sign_payload(body, key_id, key_file):
    payload = json.dumps(body, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    with tempfile.TemporaryDirectory() as d:
        data = Path(d) / 'payload'; data.write_bytes(payload)
        sig = openssl('dgst', '-sha256', '-sign', str(key_file), str(data))
    return {'key': key_id, 'payload': base64.b64encode(payload).decode(), 'sig': base64.b64encode(sig).decode()}


def sign_windows(key_id, key_file):
    """windows.json (edited by hand) -> windows-update.json. SHA-256 and size come from downloading the installer."""
    src = ROOT / 'windows.json'
    if not src.is_file(): return
    w = json.loads(src.read_text(encoding='utf-8'))
    version, url = str(w['version']), str(w['url'])
    if not VERSION.fullmatch(version): raise SystemExit('windows.json version must be like 1.0.0.11')
    if not url.startswith('https://'): raise SystemExit('windows.json url must be https://')
    minimum = str(w.get('min_version') or '')
    if minimum and not VERSION.fullmatch(minimum): raise SystemExit('min_version must be like 1.0.0.9 or empty')
    import hashlib, urllib.request
    digest, size = hashlib.sha256(), 0
    with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'arthur-endpoints-signer'}), timeout=120) as r:
        while True:
            chunk = r.read(1 << 20)
            if not chunk: break
            digest.update(chunk); size += len(chunk)
            if size > 400 * 1024 * 1024: raise SystemExit('Installer larger than 400 MB')
    now = int(time.time())
    body = {'schema': WIN_SCHEMA, 'app': WIN_APP, 'version': version, 'label': str(w.get('label', ''))[:20], 'url': url,
            'sha256': digest.hexdigest(), 'size': size, 'min_version': minimum, 'notes': str(w.get('notes', ''))[:600],
            'issued': now, 'expires': now + VALID_DAYS * 86400}
    out = sign_payload(body, key_id, key_file)
    (ROOT / 'windows-update.json').write_text(json.dumps(out, indent=2) + chr(10), encoding='utf-8', newline=chr(10))
    print('Signed windows-update.json version=%s size=%d sha256=%s mandatory_below=%s' % (version, size, body['sha256'], minimum or '-'))


if __name__ == '__main__':
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument('--key-id', choices=['k1', 'k2']); a.add_argument('--key-file'); a.add_argument('--check', action='store_true')
    args = a.parse_args()
    if args.check: check()
    elif args.key_id and args.key_file: sign(args.key_id, args.key_file); check(); sign_windows(args.key_id, args.key_file)
    else: a.error('use --check, or --key-id with --key-file')
