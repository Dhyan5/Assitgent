# JARVIS

JARVIS is an offline-first Windows voice-assistant implementation in progress. The source now spans phases 1–7, with conservative defaults, a read-only text harness, and automated security/control tests. **It is not yet a runnable, accepted voice installation.** Native dependencies, model provisioning, OS setup, several hardening requirements and real-device acceptance remain outstanding. See [BUILD_STATUS.md](BUILD_STATUS.md) for the exact phase status.

Your instruction to continue all steps superseded the original stop-after-each-phase instruction. It did not relax the security or footprint limits. Nothing has been installed, downloaded as a model, added to Startup, or run against your personal files.

## Try what is available now

```powershell
cd C:\Users\Dhyan\OneDrive\Desktop\Jarvis
python main.py --doctor
python main.py --text-test --debug
```

The text harness is intentionally read-only and model-free. Try `time`, `please what time is it`, `open notepad`, `hello`, and `exit`. With the default `dry_run: true`, it describes the action. Set that flag to false to execute the three read-only status tools; time works with existing dependencies, while battery/memory status require psutil.

`python main.py --doctor` reports missing dependencies, hashes and setup gates without opening audio streams. A captured report is in [READINESS.json](READINESS.json).

Double-clicking `jarvis.bat` verifies required files and the venv, then launches at low priority without a console. `jarvis.bat debug` keeps a console visible. The launcher never installs anything. Production startup currently refuses: the outbound self-test conflicts with the no-network rule and awaits an explicit exception decision and implementation. Other missing prerequisites also refuse startup; changing a config flag cannot bypass this unfinished gate.

## Implementation

```text
main.py, runtime.py           CLI, voice event loop, hotkeys, lifecycle
configuration.py, config.yaml configuration and conservative defaults
commands.yaml, intent.py       deterministic commands and fuzzy suggestions
policy.py, schemas.py          central schema/tier/rate/mode/confirmation policy
safety.py, secure_files.py     path guards and Windows handle-based file access
audit.py                      redacted, hash-chained audit with capacity limit
llm.py                        local constrained routing and streaming chat
stt.py                        RAM-array Whisper transcription with confidence
 audio.py                     intentional capture, VAD, chimes, half-duplex gate
 tts.py                       sentence queue and Windows built-in voice by default
session.py, dialogue.py        short RAM memory, follow-ups, reminders
lifecycle.py, watchdog.py      deadlines, mode timeouts, memory-limit adapter
health.py, startup.py          resource/OS checks and single-instance lock
tray.py, jarvis.bat            visible mic state and on-demand Windows launcher
tools/                        read-only status, Windows actions, note tools
browser/                      guarded Chrome implementation; disabled by default
download_models.py            separate manual checksum-verified provisioner
models.manifest.example.json  publisher hashes; voice config hash still required
requirements*.in              current direct version candidates, NOT hashed locks
tests/                        automated security and behavior tests
measure.py, diagnostics.py     reproducible text benchmark and readiness checks
```

Full code is in the source files; [SOURCE_CODE.txt](SOURCE_CODE.txt) is a consolidated review copy. `persona.txt` keeps the response style brief and offline-aware.

## Designed voice flow

Ctrl+Alt+J holds push-to-talk; release submits the RAM buffer. Ctrl+Alt+K toggles conversation capture, with chimes, a red microphone indicator, silence timeout and battery restriction. Ctrl+Alt+S cancels speech. Ctrl+Alt+Q closes capture and the assistant's browser job, then exits. These paths are implemented but not physically tested with the missing native stack.

Capture is 16 kHz mono, bounded to 15 seconds of an utterance. Silence before speech retains only a short preroll. Whisper receives a NumPy array, never an audio pathname, and rejects absent/NaN/low confidence. Whisper and the LLM are used sequentially. Stage A exact matches go through policy; fuzzy matches are suggestions only. Stage B gets a closed JSON grammar and independently validated output. Stage C receives no tool interface and streams display-only sentences into the speech queue. File read output goes directly to talkback and never back through routing or chat memory.

Piper and ONNX run locally with single-thread synthesis and telemetry disabled. A verified English espeak voice is required. `tts.backend: system` selects the specified pyttsx3 local fallback. Both need real-device validation. No automatic model or voice download exists in runtime code. RAM-only playback cancellation is tested with a simulated device, not a hardware timing claim.

Tier 1 prompts repeat the action and its arguments. The fixed yes/no/cancel decision never invokes an LLM. In voice mode the eight-second confirmation window starts after the spoken prompt. Ambiguous follow-ups without a known volume value ask for a percentage. Session history is capped to six turns and 2,400 characters and is cleared on exit or `forget that`.

## Tools and defaults

The full registry covers app open/owned graceful close, volume/mute/media, brightness (minimum 10%), lock screen, time/battery/memory status, flat-folder list/read, exclusive new-note creation, append, corrective append, screenshot and in-process reminders. Screenshots are new PNGs in the approved folder. Note changes and screenshots require confirmation. Every handler also validates its own schema.

The app whitelist is empty. Each configured executable requires an absolute `.exe` path and SHA256; shells, browsers and interpreters are refused as normal apps. Process arguments are fixed and `shell=False`. No generic process-launching tool exists. `close_app` only targets the process handle launched by this session.

Only Windows is implemented. Unsupported platforms fail closed; no misleading Linux/macOS launcher is included. Online mode, browser typing, wake word, speaker verification and persistent memory are disabled. Optional features are not silently represented by weak substitutes.

## Verification

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest -q
python measure.py
```

The suite uses real policy/routing logic with simulated device and OS adapters. It covers traversal, overwrite and link guards, redacted audit tampering/capacity, schema rejection, prompt injection, chat isolation, 50 deterministic commands without LLM calls, confirmation expiry/replay, dry run, rate/breaker/deadline behavior, follow-up memory, microphone gating, simulated cancellation, VAD bounds, online timeout, URL/input guards, firewall-rule coverage, download hash verification and launcher structure. A real symlink test skips when Windows denies link creation. Small test fixtures are retained under `.test-artifacts`; no automated deletion is introduced.

[MEASUREMENTS.json](MEASUREMENTS.json) measures the model-free text path and Windows process working set. It does not measure inference RAM, full install size, true idle CPU or voice latency. Real hardware tests remain mandatory. Realtek input/output devices were enumerated without recording audio.

## Versions, models and footprint

See [VERSIONS.md](VERSIONS.md) for current direct dependency versions and their purposes. Python 3.15.2 is the latest stable candidate observed, but ONNX Runtime's published classifiers/wheels currently stop at 3.14. A compatible latest-stable interpreter must be resolved before installation; the existing 3.12.10 environment only ran preliminary tests. No version downgrade or upgrade was silently performed.

The publisher's actual Qwen 0.5B Q4_K_M file is approximately 491 MB and Whisper tiny.en q5_1 is 32.2 MB: roughly 523 MB before Python and dependencies. The default uses the installed Windows speech voice, saving the 63 MB Piper voice and ONNX Runtime. Therefore the requested 700 MB ULTRA-LITE total is **not yet established**. The earlier 400 MB model estimate was wrong. The hard budget remains unchanged. No models or packages were installed to exceed it. Larger profiles are not validated.

`requirements.txt` is absent because pip-tools is unavailable and shell package downloads fail. The `.in` files are exact direct candidates, not a resolved transitive/hash lock. Do not treat them as release-ready requirements. Native builds also require controlled build dependencies. The manual downloader refuses incomplete manifests, overwrites, unknown redirect domains and budget overflow; interrupted/untrusted files remain unusable because runtime rechecks hashes. The sample voice JSON hash is intentionally unset, causing preflight refusal before any download.

## Security boundaries and setup

[SETUP_WINDOWS.md](SETUP_WINDOWS.md) contains the concrete limited-account/firewall preparation and manual acceptance checklist. [THREAT_MODEL.md](THREAT_MODEL.md) describes residual risks. Production startup must validate the venv/lock, account separation, private directories, firewall rule coverage, model hashes, whitelist, devices and resource budget. It currently has an explicit unresolved network-test gate and cannot complete.

No-delete wins over automatic log expiry and voice erasure: logs are append-only, redacted and capped at 4 MB; reaching capacity refuses further actions. No registry writes or firewall changes were made. Chrome policy checks are read-only; the setup script is withheld pending the explicit registry exception. Browser policies are machine-wide and must be evaluated in a dedicated VM before use on a normal Chrome installation.

The watchdog locks future actions on deadline expiry and closes capture; it cannot forcibly cancel an arbitrary native call already in progress or undo its side effects. Hard process-memory limits have a Windows Job adapter but are not live-tested. Browser and foreground-input protections require real Windows acceptance. These are release gates, not claimed guarantees.
