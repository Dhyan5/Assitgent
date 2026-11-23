"""Manual-only, pinned HTTPS provisioning. Never imported by the assistant."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import time
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, HTTPSHandler, ProxyHandler, Request, build_opener
from safety import Refusal, no_links


class PinnedRedirects(HTTPRedirectHandler):
    def __init__(self, hosts):
        self.hosts, self.count = set(hosts), 0

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.count += 1
        validate_url(newurl, self.hosts)
        if self.count > 5:
            raise Refusal('Too many model redirects.')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def validate_url(url, hosts):
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or parsed.hostname not in hosts or parsed.port not in (None, 443) or parsed.username or parsed.password:
        raise Refusal('Model URL or redirect is not approved HTTPS.')


def provision(entry, root, *, opener=None):
    validate_entry(entry)
    return _provision(entry, root, opener=opener)


def validate_entry(entry):
    required = {'url', 'sha256', 'filename', 'max_bytes', 'hosts'}
    if set(entry) != required or not re.fullmatch('[0-9a-f]{64}', entry['sha256'] or ''):
        raise Refusal('A complete trusted model manifest and SHA256 are required.')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,100}\.(gguf|bin|onnx|json)', entry['filename']):
        raise Refusal('Invalid model filename.')
    if not isinstance(entry['max_bytes'], int) or not 0 < entry['max_bytes'] <= 500_000_000:
        raise Refusal('Provisioning is capped to the ULTRA-LITE per-file allowance.')
    validate_url(entry['url'], entry['hosts'])


def _provision(entry, root, *, opener=None):
    root = no_links(root)
    root.mkdir(parents=True, exist_ok=True)
    path = no_links(root / entry['filename'])
    if path.exists():
        raise Refusal('The destination exists; it will not be overwritten.')
    if shutil.disk_usage(root).free < entry['max_bytes'] + 100_000_000:
        raise Refusal('Insufficient free disk space.')
    opener = opener or build_opener(ProxyHandler({}), PinnedRedirects(entry['hosts']), HTTPSHandler())
    digest, size, started = hashlib.sha256(), 0, time.monotonic()
    # CREATE_NEW semantics; interrupted or mismatched files are retained, never loaded without hash validation.
    with opener.open(Request(entry['url'], headers={'User-Agent': 'JARVIS-manual-provisioner'}), timeout=15) as response:
        validate_url(response.geturl(), entry['hosts'])
        with path.open('xb') as target:
            while True:
                chunk = response.read(65536)
                if not chunk:
                    break
                size += len(chunk)
                if size > entry['max_bytes'] or time.monotonic() - started > 900:
                    raise Refusal('Model download exceeded its size or time cap; incomplete file retained.')
                target.write(chunk)
                digest.update(chunk)
    if digest.hexdigest() != entry['sha256']:
        raise Refusal('Checksum mismatch; untrusted file retained and runtime will refuse it.')
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parent / 'models')
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
    if not isinstance(manifest, list) or len(manifest) > 4:
        raise Refusal('Expected up to four pinned model assets.')
    for entry in manifest:
        validate_entry(entry)
    if sum(entry.get('max_bytes', 0) for entry in manifest) > 600_000_000:
        raise Refusal('The model set exceeds the ULTRA-LITE provisioning budget.')
    project = Path(__file__).resolve().parent
    existing = sum(p.stat().st_size for p in project.rglob('*') if p.is_file() and '.test-artifacts' not in p.parts)
    if existing + sum(entry.get('max_bytes', 0) for entry in manifest) >= 700_000_000:
        raise Refusal('The project plus model allowances would exceed 700 MB. Nothing downloaded.')
    for entry in manifest:
        print('Verified: ' + str(provision(entry, args.output)))


if __name__ == '__main__':
    main()
