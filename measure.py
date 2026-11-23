"""Measure the read-only text path; never substitute this for live model measurements."""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import platform
import statistics
import time
from uuid import uuid4
import yaml
from audit import Audit
from dialogue import Assistant
from intent import Intent
from policy import Policy


def memory_windows():
    class Counters(ctypes.Structure):
        _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD)] + [
            (name, ctypes.c_size_t) for name in ('PeakWorkingSetSize', 'WorkingSetSize',
            'QuotaPeakPagedPoolUsage', 'QuotaPagedPoolUsage', 'QuotaPeakNonPagedPoolUsage',
            'QuotaNonPagedPoolUsage', 'PagefileUsage', 'PeakPagefileUsage')]
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    psapi = ctypes.WinDLL('psapi', use_last_error=True)
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
        raise OSError('Unable to measure working set')
    return {'working_set_bytes': counters.WorkingSetSize, 'peak_working_set_bytes': counters.PeakWorkingSetSize}


def main():
    root = Path(__file__).resolve().parent
    folder = root / '.test-artifacts' / uuid4().hex
    folder.mkdir(parents=True)
    assistant = Assistant(Intent(yaml.safe_load((root / 'commands.yaml').read_text())),
                          Policy(Audit(folder / 'measure.jsonl'), dry_run=False, rate=100))
    timings = []
    for _ in range(50):
        start = time.perf_counter()
        answer = assistant.handle('what time is it')
        assert answer.startswith('It is ')
        timings.append((time.perf_counter() - start) * 1000)
    measured = {'python': platform.python_version(), 'sample_count': 50,
                'stage_a_with_policy_audit_ms_median': statistics.median(timings),
                'stage_a_with_policy_audit_ms_max': max(timings),
                'project_bytes_excluding_test_artifacts': sum(p.stat().st_size for p in root.rglob('*')
                    if p.is_file() and not any(s.startswith('.') for s in p.relative_to(root).parts)),
                'model_ram_and_latency': 'NOT MEASURED: no verified local model',
                'voice_latency': 'NOT MEASURED: native voice stack not provisioned',
                'full_install_size': 'NOT MEASURED: no venv or model installed'}
    if os.name == 'nt':
        measured.update(memory_windows())
    print(json.dumps(measured, indent=2))


if __name__ == '__main__':
    main()
