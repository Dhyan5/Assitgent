"""Deadline notification never pretends to forcibly cancel a native call."""
from threading import Timer
import time


class Deadline:
    def __init__(self, seconds, on_timeout):
        self.seconds, self.on_timeout = seconds, on_timeout
        self.timer, self.expired = None, False

    def __enter__(self):
        def expire():
            self.expired = True
            self.on_timeout()
        self.timer = Timer(self.seconds, expire)
        self.timer.daemon = True
        self.timer.start()
        return self

    def __exit__(self, *_):
        self.timer.cancel()


def process_memory_limit(max_bytes):
    import win32api
    import win32job
    job = win32job.CreateJobObject(None, None)
    info = win32job.QueryInformationJobObject(job, win32job.JobObjectExtendedLimitInformation)
    info['BasicLimitInformation']['LimitFlags'] = win32job.JOB_OBJECT_LIMIT_PROCESS_MEMORY
    info['ProcessMemoryLimit'] = max_bytes
    win32job.SetInformationJobObject(job, win32job.JobObjectExtendedLimitInformation, info)
    win32job.AssignProcessToJobObject(job, win32api.GetCurrentProcess())
    return job
