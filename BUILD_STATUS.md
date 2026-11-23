# Build and acceptance status

The source has been extended across the requested phases. This is not equivalent to completing their deployment or passing every required acceptance test.

| Phase | Implemented | Still required |
| --- | --- | --- |
| 1: text/security/model | Text harness, schemas, policy, audit, exact commands, constrained-model adapter, isolated chat, tests | Generated hashed lock; latest compatible Python; live Qwen routing/chat tests |
| 2: offline tools | Full registry, exclusive Windows file handles, notes/corrections/screenshots, app whitelist/owned close, system controls, reminders | Live Win32 handle/ACL, volume/brightness/app/screenshot tests under dedicated account |
| 3: voice input | Intentional capture, VAD, RAM-only buffers, Whisper adapter, confidence rejection | Install native libraries/model; microphone integration and transcription confidence calibration |
| 4: talkback | Windows built-in voice selected by default, optional Piper path, sentence queue, streaming chat, half-duplex, cancellation, prompt/greeting/goodbye | Install pyttsx3 dependency; actual voice/cancellation latency; startup refusal talkback |
| 5: conversation | Toggle state, chimes/red state, silence/battery gating, RAM memory, volume follow-up, typed/spoken confirmation flow | Full hotkey/device lifecycle tests; real end-of-speech latency and memory/temperature traces |
| 6: lifecycle/setup | Launcher, tray, watchdog, single-instance lock, account/ACL/firewall/model/device checks, diagnostic report, memory-limit adapter, approved fixed outbound probe | venv/locks; OS provisioning; battery profile switching and critical-battery beep behavior; AVX2 validation; measured idle budgets |
| 7: online restricted | URL allowlist, Chrome policy readback and explicitly invoked HKLM setup script, dedicated process job, guarded typing, timeout/kill state | Actual Chrome policies/download block/redirect/focus tests; browser footprint; remains disabled |
| 8: optional | Optional settings fail closed; VM setup guidance | Speaker verification, wake word, CHAT+ tuning and packaging are not implemented or enabled |

## Measurements

Final automated regression result: **93 passed, 1 skipped** on Python 3.12.10 (pytest 8.3.4). The skipped test needs Windows symlink privilege. This is not a run against the latest candidate locked environment. Text-harness smoke tests, runtime imports and configuration validation passed; normal startup correctly refused missing private-log setup. No voice capture or real PC mutation was performed.

`MEASUREMENTS.json` is the current text-only benchmark. All voice and native-model latency measurements, full installation footprint and post-inference idle RAM remain unmeasured. There is no claim that the 700 MB / 800 MB / 60 MB ULTRA-LITE limits pass. Required models alone are about 523 MB; package/build overhead may exceed the budget.

Realtek microphone and speaker endpoints were visible to sounddevice. No microphone was opened or recorded during development. The simulated speech cancellation test meets 300 ms in the test environment only.

## External blockers

* Network requests from shell Python/PowerShell are refused. pip-tools and most native libraries are absent. The connected browser can read release metadata but does not install packages in this environment.
* Only Python 3.12.10 is installed; latest compatible stable Python/native-wheel resolution is outstanding.
* Personal Windows account/home/ACL and firewall provisioning have not been changed. The source currently lives under OneDrive and cannot serve as the private limited-account deployment location.
* The user approved the narrow startup outbound test and machine-wide Chrome policy setup. The fixed probe and explicit `--apply` script are implemented and mocked tests pass. The registry script has not been run on the user's machine; that requires an elevated deployment console after review.

## Important implementation limits

Native calls may outlive cooperative cancellation; deadline expiry locks future work but cannot roll back a tool that has begun. Log hash chaining is not an authenticated external trust anchor. Input focus checks narrow, but do not eliminate, race windows between checking focus and typing. Browser process creation/Job assignment and secure file APIs are untested on the target account. Hardware safety is conservative but not a verified thermal interlock. Production remains blocked rather than claiming these gaps have passed.
