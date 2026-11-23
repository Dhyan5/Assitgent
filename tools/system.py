"""Narrow Windows actions; never a shell or an arbitrary executable."""
from pathlib import Path
import subprocess
from schemas import checked
from safety import Refusal, verify_model

DENIED_APPS = {'cmd', 'powershell', 'pwsh', 'wt', 'wscript', 'cscript', 'mshta', 'rundll32',
               'reg', 'regedit', 'python', 'pythonw', 'node', 'bash', 'sh', 'chrome', 'msedge',
               'firefox', 'iexplore', 'opera', 'brave', 'explorer', 'control', 'mmc', 'msiexec'}


def approved_executable(name, apps):
    item = apps.get(name)
    if not item or set(item) != {'path', 'sha256'}:
        raise Refusal('That app is not on the approved list, sir.')
    path = Path(item['path'])
    if not path.is_absolute() or path.suffix.lower() != '.exe' or path.stem.lower() in DENIED_APPS:
        raise Refusal('Browsers, shells and interpreters are not app tools.')
    return verify_model(path, item['sha256'], 500_000_000)


class SystemTools:
    def __init__(self, apps):
        self.apps, self.launched = apps, {}

    @checked('open_app')
    def open_app(self, args):
        name = args['app']
        exe = approved_executable(name, self.apps)
        old = self.launched.get(name)
        if old and old.poll() is None:
            return 'That app is already open, sir.'
        # argv is fixed; user/model text cannot become process flags.
        process = subprocess.Popen([str(exe)], shell=False, close_fds=True, cwd=str(exe.parent))
        self.launched[name] = process
        return 'Opening ' + name + ', sir.'

    @checked('close_app')
    def close_app(self, args):
        process = self.launched.get(args['app'])
        if process is None or process.poll() is not None:
            raise Refusal('I did not launch a running instance of that app, sir.')
        graceful_close(process.pid)
        return 'I requested that my app instance close, sir.'

    def _volume(self):
        from pycaw.pycaw import AudioUtilities
        return AudioUtilities.GetSpeakers().EndpointVolume

    @checked('set_volume')
    def set_volume(self, args):
        self._volume().SetMasterVolumeLevelScalar(args['level'] / 100, None)
        return f"Volume is {args['level']} percent, sir."

    @checked('mute')
    def mute(self, args):
        self._volume().SetMute(1, None)
        return 'Muted, sir.'

    @checked('set_brightness')
    def set_brightness(self, args):
        import screen_brightness_control as sbc
        sbc.set_brightness(args['level'])
        return f"Brightness is {args['level']} percent, sir."

    def _media(self, key):
        import win32api
        import win32con
        win32api.keybd_event(key, 0, 0, 0)
        win32api.keybd_event(key, 0, win32con.KEYEVENTF_KEYUP, 0)
        return 'Media command sent, sir.'

    @checked('media_play_pause')
    def media_play_pause(self, args):
        return self._media(0xB3)

    @checked('media_next')
    def media_next(self, args):
        return self._media(0xB0)

    @checked('media_prev')
    def media_prev(self, args):
        return self._media(0xB1)

    @checked('lock_screen')
    def lock_screen(self, args):
        import ctypes
        if not ctypes.windll.user32.LockWorkStation():
            raise Refusal('Windows refused the screen lock, sir.')
        return 'Locking the screen, sir.'


def graceful_close(pid):
    import win32gui
    import win32process
    import win32con
    def visit(hwnd, _):
        if win32process.GetWindowThreadProcessId(hwnd)[1] == pid:
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
    win32gui.EnumWindows(visit, None)
