"""Conservative guards. No file mutation or OS action is implemented here."""
import hashlib
import os
from pathlib import Path
import re
import stat


class Refusal(ValueError):
    pass


def user_text(text):
    if not isinstance(text, str) or not 0 < len(text) <= 2000:
        raise Refusal('Input must contain 1 to 2000 characters.')
    if any(ord(c) < 32 for c in text):
        raise Refusal('Control characters are not permitted.')
    if re.search(r'\b(delete|remove|rmdir|trash|format|install|uninstall|download|'
                 r'powershell|cmd|terminal|registry|password|cvv|otp|overwrite|'
                 r'rename|move|purchase|ignore|bypass)\b', text, re.I):
        raise Refusal('That request is outside my permissions, sir.')
    if any(c in text for c in (';', '|', '`', '$(', '\x00')):
        raise Refusal('Shell-like input is not permitted.')
    return text


def no_links(path):
    path = Path(os.path.abspath(path))
    for part in (*reversed(path.parents), path):
        if part.is_symlink():
            raise Refusal('Symbolic links are not permitted.')
        if part.exists():
            info = part.lstat()
            if getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                raise Refusal('Reparse points are not permitted.')
    return path


def safe_path(root, name, *, new=False, max_bytes=65536):
    root = no_links(Path(root).expanduser())
    # Deliberately restrict Phase 1 to a single flat folder and plain text names.
    if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9 _-]{0,60}\.txt', name):
        raise Refusal('Only simple .txt names are permitted.')
    if re.search(r'(secret|password|credential|token|private|key)', name, re.I):
        raise Refusal('Sensitive paths are not permitted.')
    if name.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL', *('COM'+str(i) for i in range(10)), *('LPT'+str(i) for i in range(10))}:
        raise Refusal('Reserved filename.')
    target = no_links(root / name)
    if target.resolve().parent != root.resolve():
        raise Refusal('Path escapes the approved folder.')
    if target.exists():
        if new or not target.is_file() or target.stat().st_nlink != 1:
            raise Refusal('Existing files, hard links or non-files are not allowed here.')
        if target.stat().st_size > max_bytes:
            raise Refusal('File exceeds the size limit.')
    return target


def verify_model(path, expected, max_bytes):
    path = no_links(path)
    if not isinstance(expected, str) or not re.fullmatch('[0-9a-f]{64}', expected):
        raise Refusal('A trusted model SHA256 must be configured.')
    if not path.is_file() or path.stat().st_size > max_bytes:
        raise Refusal('Model missing or exceeds the disk allowance.')
    with path.open('rb') as stream:
        actual = hashlib.file_digest(stream, 'sha256').hexdigest()
    if actual != expected:
        raise Refusal('Model checksum mismatch.')
    return path


def guard_app(name, apps):
    # Launching any executable is deferred to the full toolset phase.
    raise Refusal('App launching is unavailable in Phase 1.')


def guard_typing(text, *, own_chrome=False):
    raise Refusal('Input control is disabled in Phase 1.')
