"""Windows handle-based, no-delete-sharing file access; flat approved folder only."""
from contextlib import contextmanager
import os
from pathlib import Path
import shutil
from safety import Refusal, no_links, safe_path


class SecureFiles:
    def __init__(self, root, max_bytes=65536, minimum_free=100_000_000):
        self.root = no_links(Path(root).expanduser())
        self.max_bytes, self.minimum_free = max_bytes, minimum_free
        if not self.root.is_dir():
            raise Refusal('Create the approved AssistantFiles folder during setup.')

    @contextmanager
    def handle(self, name, *, write=False, new=False, image=False):
        if os.name != 'nt':
            raise Refusal('Secure file handles are implemented for Windows only.')
        import win32con as c
        import win32file as f
        from pywintypes import error
        if image:
            import re
            if not re.fullmatch(r'screenshot-[0-9a-f]{32}\.png', name):
                raise Refusal('Invalid screenshot name.')
            target = no_links(self.root / name)
        else:
            target = safe_path(self.root, name, new=new, max_bytes=self.max_bytes)
        if write and shutil.disk_usage(self.root).free < self.minimum_free:
            raise Refusal('Disk space is low, sir.')
        # Holding the root without FILE_SHARE_DELETE prevents rename/replacement.
        directory = f.CreateFile(str(self.root), c.GENERIC_READ, c.FILE_SHARE_READ | c.FILE_SHARE_WRITE,
                                 None, c.OPEN_EXISTING, c.FILE_FLAG_BACKUP_SEMANTICS | c.FILE_FLAG_OPEN_REPARSE_POINT, None)
        handle = None
        try:
            if f.GetFileInformationByHandle(directory)[0] & c.FILE_ATTRIBUTE_REPARSE_POINT:
                raise Refusal('Approved folder is a reparse point.')
            expected_root = f.GetFinalPathNameByHandle(directory, 0).casefold()
            rights = (c.GENERIC_READ | c.GENERIC_WRITE) if write else c.GENERIC_READ
            handle = f.CreateFile(str(target), rights, 0, None, c.CREATE_NEW if new else c.OPEN_EXISTING,
                                  c.FILE_FLAG_OPEN_REPARSE_POINT, None)
            info = f.GetFileInformationByHandle(handle)
            actual = f.GetFinalPathNameByHandle(handle, 0).casefold()
            if actual != expected_root.rstrip('\\') + '\\' + name.casefold():
                raise Refusal('Handle escaped the approved folder.')
            if info[0] & (c.FILE_ATTRIBUTE_REPARSE_POINT | c.FILE_ATTRIBUTE_DIRECTORY) or info[7] != 1:
                raise Refusal('Links and directories are not allowed.')
            if f.GetFileSize(handle) > (8_000_000 if image else self.max_bytes):
                raise Refusal('File is too large.')
            yield handle
        except error as exc:
            raise Refusal('File access was refused, sir.') from exc
        finally:
            if handle is not None:
                handle.Close()
            directory.Close()

    def read(self, name):
        import win32file as f
        with self.handle(name) as handle:
            size = f.GetFileSize(handle)
            data = f.ReadFile(handle, size)[1] if size else b''
        return data.decode('utf-8', errors='strict')

    def write(self, name, text, *, new=False):
        import win32file as f
        data = text.encode('utf-8')
        if not 0 < len(data) <= self.max_bytes:
            raise Refusal('Note exceeds the size limit.')
        with self.handle(name, write=True, new=new) as handle:
            if f.GetFileSize(handle) + len(data) > self.max_bytes:
                raise Refusal('Note exceeds the size limit.')
            f.SetFilePointer(handle, 0, 2)
            f.WriteFile(handle, data)
            f.FlushFileBuffers(handle)

    def image(self, name, data):
        import win32file as f
        if len(data) > 8_000_000:
            raise Refusal('Screenshot exceeds its size limit.')
        with self.handle(name, write=True, new=True, image=True) as handle:
            f.WriteFile(handle, data)
            f.FlushFileBuffers(handle)

    def names(self):
        result = []
        for path in self.root.iterdir():
            try:
                safe_path(self.root, path.name)
                if path.is_file():
                    result.append(path.name)
            except Refusal:
                continue
            if len(result) >= 100:
                break
        return sorted(result)
