"""Testable mode/deadline logic without hardware imports."""
import time
from safety import Refusal


class Conversation:
    def __init__(self, open_mic, close_mic, *, timeout=30, clock=time.monotonic):
        self.open_mic, self.close_mic, self.timeout, self.clock = open_mic, close_mic, timeout, clock
        self.enabled, self.deadline = False, 0

    def toggle(self, *, on_battery=False, allow_battery=False):
        if self.enabled:
            self.close()
        else:
            if on_battery and not allow_battery:
                raise Refusal('Conversation mode is disabled on battery, sir.')
            self.enabled = True
            self.touch()
            try:
                self.open_mic()
            except Exception:
                self.enabled = False
                raise

    def touch(self):
        self.deadline = self.clock() + self.timeout

    def tick(self):
        if self.enabled and self.clock() >= self.deadline:
            self.close()
            return True
        return False

    def close(self):
        self.enabled = False
        self.close_mic()


class OnlineMode:
    def __init__(self, close_browser, notice, *, seconds=900, clock=time.monotonic):
        self.close_browser, self.notice, self.seconds, self.clock = close_browser, notice, seconds, clock
        self.deadline, self.active = 0, False

    @property
    def name(self):
        return 'ONLINE-RESTRICTED' if self.active else 'OFFLINE'

    def enable(self):
        self.deadline = self.clock() + self.seconds
        self.active = True
        self.notice('Online mode active, sir.')

    def close(self):
        active, self.active = self.active, False
        self.close_browser()
        if active:
            self.notice('Reverting to offline mode, sir.')

    def tick(self):
        if self.active and self.clock() >= self.deadline:
            self.close()
            return True
        return False
