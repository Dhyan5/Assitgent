"""Append-only, redacted hash chain. This is not an authenticated log."""
import hashlib
import json
import os
from threading import RLock
from datetime import datetime, timezone
from safety import Refusal, no_links


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


class Audit:
    def __init__(self, path, max_bytes=4_000_000, mode=lambda: 'OFFLINE'):
        self.path = no_links(path)
        self.max_bytes = max_bytes
        self.head = self.verify()
        self.lock, self.mode = RLock(), mode

    def verify(self):
        head = '0' * 64
        if not self.path.exists():
            return head
        no_links(self.path)
        if self.path.stat().st_nlink != 1 or self.path.stat().st_size > self.max_bytes:
            raise Refusal('Audit file exceeds limits or is a hard link.')
        try:
            with self.path.open(encoding='utf-8') as stream:
                for line in stream:
                    row = json.loads(line)
                    recorded = row.pop('hash')
                    if row['previous'] != head or digest(row) != recorded:
                        raise ValueError('chain')
                    head = recorded
        except (ValueError, KeyError, TypeError) as exc:
            raise Refusal('Audit integrity check failed.') from exc
        return head

    def record(self, tool, args, result, tier=0):
        with self.lock:
            return self._record(tool, args, result, tier)

    def _record(self, tool, args, result, tier):
        if self.verify() != self.head:
            raise Refusal('Audit changed during this session.')
        row = {'timestamp': datetime.now(timezone.utc).isoformat(),
               'tool': tool, 'args': {k: '[redacted]' for k in args},
               'result': result, 'mode': self.mode(), 'tier': tier, 'previous': self.head}
        checksum = digest(row)
        line = json.dumps({**row, 'hash': checksum}, sort_keys=True) + '\n'
        size = self.path.stat().st_size if self.path.exists() else 0
        if size + len(line.encode()) > self.max_bytes:
            raise Refusal('Audit capacity reached; refusing further actions.')
        with self.path.open('a', encoding='utf-8') as stream:
            stream.write(line)
            stream.flush()
            os.fsync(stream.fileno())
        self.head = checksum
