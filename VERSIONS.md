# Dependency candidates checked 2026-11-23

These are direct pins from upstream PyPI release pages, not an installed environment or a generated hash lock. Native compatibility must still be resolved. No PyTorch, TensorFlow, Electron, server or Docker runtime is introduced.

| Package | Candidate | Purpose | Published distribution size / budget note |
| --- | --- | --- | --- |
| [PyYAML](https://pypi.org/project/PyYAML/) | 6.0.4 | Safe configuration parsing | Small; installed size unmeasured |
| [jsonschema](https://pypi.org/project/jsonschema/) | 4.26.0 | Validate every routed call | About 91 KB wheel plus transitives |
| [RapidFuzz](https://pypi.org/project/RapidFuzz/) | 3.14.6 | Fuzzy suggestions, never automatic actions | Native wheel size depends on target ABI |
| [psutil](https://pypi.org/project/psutil/) | 7.2.2 | Process/battery/memory checks | Installed size unmeasured |
| [llama-cpp-python](https://pypi.org/project/llama-cpp-python/) | 0.3.37 | CPU local routing/chat | 80.9 MB source archive; compiled/install overhead unmeasured |
| [pynput](https://pypi.org/project/pynput/) | 1.8.2 | Hotkeys and optional guarded text entry | About 92 KB wheel plus platform dependencies |
| [sounddevice](https://pypi.org/project/sounddevice/) | 0.5.6 | Audio capture/playback | Bundled PortAudio on Windows; installed size unmeasured |
| [numpy](https://pypi.org/project/numpy/) | 2.5.5 | Audio arrays | Windows x64 wheel around 13 MB; expanded size is larger |
| [webrtcvad-wheels](https://pypi.org/project/webrtcvad-wheels/) | 2.0.14.post1 | Voice activity detection | Small native wheel |
| [pywhispercpp](https://pypi.org/project/pywhispercpp/) | 1.5.1 | Local speech transcription | 9.8 MB source archive; target native wheel unmeasured |
| [pyttsx3](https://pypi.org/project/pyttsx3/) | 2.99 | Windows built-in speech voice; no voice model download | About 32 KB wheel plus small COM dependency |
| [pycaw](https://pypi.org/project/pycaw/) | 20260927 | Windows volume | About 29 KB wheel plus COM dependencies |
| [screen-brightness-control](https://pypi.org/project/screen-brightness-control/) | 0.27.2 | Display brightness | About 37 KB wheel; monitor support varies |
| [pywin32](https://pypi.org/project/pywin32/) | 312 | Secure handles, COM, foreground PID, Jobs | Native install size unmeasured |
| [pystray](https://pypi.org/project/pystray/) | 0.19.5 | Visible microphone state | Small Python distribution |
| [Pillow](https://pypi.org/project/pillow/) | 13.0.0 | Tray bitmap and confirmed screenshot | Native install size unmeasured |
| [pytest](https://pypi.org/project/pytest/) | 9.2.0 | Development tests | About 412 KB wheel plus transitives; not needed at runtime |
| [pip-tools](https://pypi.org/project/pip-tools/) | 7.7.0 | Build-time hashes and resolution | About 75 KB wheel plus build dependencies |

Published archive sizes are not installed sizes and must not be summed as an installation estimate. Installed-size and memory checks need a real resolved target environment. Python 3.15.2 is the latest stable candidate according to [Python.org](https://www.python.org/downloads/release/python-3152/); the native stack may require the latest stable 3.14 patch until compatible wheels exist. Nothing has been silently changed on this PC.

## Pinned model provenance

* [Qwen's 0.5B Q4_K_M](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/blob/main/qwen2.5-0.5b-instruct-q4_k_m.gguf): about 491 MB, SHA256 `74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db`.
* [whisper.cpp tiny.en q5_1](https://huggingface.co/ggerganov/whisper.cpp/blob/main/ggml-tiny.en-q5_1.bin): about 32.2 MB, SHA256 `c77c5766f1cef09b6b7d47f21b546cbddd4157886b3b5d6d4f709e91e66c7c2b`.
Piper remains an optional code path, but the default build selects the existing Windows voice to avoid a 63 MB voice file and ONNX Runtime. The configured default is Microsoft David Desktop; Windows also reports Microsoft Zira Desktop. No voice cloning is used.

The manifest uses publisher URLs and immutable expected content hashes. A changed upstream file fails verification. Hashes establish expected bytes, not that native parsers or the model are safe.
