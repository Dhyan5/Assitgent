"""Dedicated Chrome job, exact URL allowlist, no page ingestion or gateway."""
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4
from schemas import checked
from safety import Refusal, verify_model, no_links
from lifecycle import OnlineMode
from browser.guard import safe_url, safe_typing, check_chrome_policies


class Chrome:
    def __init__(self, config, profile_root, notice, audit):
        self.config, self.profile_root, self.audit = config, Path(profile_root), audit
        self.process, self.pid, self.job = None, None, None
        self.mode = OnlineMode(self._close, notice, seconds=config.get('seconds', 900))

    @checked('enable_online')
    def enable_online(self, args):
        if not self.config.get('enabled'):
            raise Refusal('Online mode is disabled in configuration, sir.')
        check_chrome_policies(self.config['hosts'])
        verify_model(self.config['path'], self.config['sha256'], 500_000_000)
        self.mode.enable()
        return 'Restricted browsing is ready, sir.'

    def _require_online(self):
        self.mode.tick()
        if not self.mode.active:
            raise Refusal('Online mode has expired or is disabled, sir.')
        check_chrome_policies(self.config['hosts'])
        if self.profile_root.exists():
            used = sum(path.stat().st_size for path in self.profile_root.rglob('*') if path.is_file())
            if used >= 64_000_000:
                self.mode.close()
                raise Refusal('Retained browser profiles reached their disk allowance; Online mode closed.')

    @checked('open_chrome')
    def open_chrome(self, args):
        self._require_online()
        url = safe_url(args['url'], self.config['hosts'])
        exe = verify_model(self.config['path'], self.config['sha256'], 500_000_000)
        if self.job:
            self._close()
        import subprocess
        import win32api
        import win32con
        import win32job
        import win32process
        profile = no_links(self.profile_root / uuid4().hex)
        profile.mkdir(parents=True, exist_ok=False)
        argv = [str(exe), '--user-data-dir=' + str(profile), '--no-first-run', '--no-default-browser-check',
                '--disable-extensions', '--disable-background-mode', '--disable-sync', '--incognito',
                '--disk-cache-size=16777216', '--media-cache-size=16777216', url]
        job = win32job.CreateJobObject(None, None)
        limits = win32job.QueryInformationJobObject(job, win32job.JobObjectExtendedLimitInformation)
        limits['BasicLimitInformation']['LimitFlags'] = win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        win32job.SetInformationJobObject(job, win32job.JobObjectExtendedLimitInformation, limits)
        process = thread = None
        try:
            process, thread, pid, _ = win32process.CreateProcess(str(exe), subprocess.list2cmdline(argv), None, None,
                False, win32con.CREATE_SUSPENDED | win32con.CREATE_NO_WINDOW, None, str(exe.parent), win32process.STARTUPINFO())
            win32job.AssignProcessToJobObject(job, process)
            self.job, self.process, self.pid = job, process, pid
            win32process.ResumeThread(thread)
        except Exception:
            # Closing the owned job stops only its processes; no generic process killer exists.
            job.Close()
            if process:
                process.Close()
            raise
        finally:
            if thread:
                thread.Close()
        return 'Opening the approved page in restricted Chrome, sir.'

    @checked('web_search')
    def web_search(self, args):
        self._require_online()
        url = self.config['search_url'] + quote(args['query'], safe='')
        return self.open_chrome({'url': url})

    def _close(self):
        if self.job:
            self.job.Close()
            self.job = None
        if self.process:
            self.process.Close()
            self.process = None
        self.pid = None
        self.audit.record('close_chrome', {}, 'closed')

    @checked('close_chrome')
    def close_chrome(self, args):
        self.mode.close()
        return 'Offline mode restored, sir.'

    @checked('type_text')
    def type_text(self, args):
        self._require_online()
        if not self.config.get('input_control') or not self.pid or not self.job:
            raise Refusal('Browser input control is disabled, sir.')
        import win32gui
        import win32process
        from pynput.keyboard import Controller
        text = safe_typing(args['text'])
        keyboard = Controller()
        # No Enter/Tab is sent: form submission is deliberately not a tool.
        for char in text:
            self._require_online()
            if win32process.GetWindowThreadProcessId(win32gui.GetForegroundWindow())[1] != self.pid:
                raise Refusal('Focus left my Chrome window; typing stopped, sir.')
            keyboard.type(char)
        return 'Text entered without submitting the form, sir.'
