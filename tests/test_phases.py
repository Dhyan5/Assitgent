import ast
from pathlib import Path
from threading import Event
import time
from types import SimpleNamespace
import pytest
from audio import Audio
from browser.guard import safe_url, safe_typing
from lifecycle import Conversation, OnlineMode
from session import Memory, SessionTools
from schemas import SCHEMAS
from tools.registry import full_registry, Tool, EMPTY
from tools.files import FileTools
from policy import Policy
from audit import Audit
from safety import Refusal
from stt import Whisper
from tts import Speech


def test_conversation_silence_and_battery():
    now, events = [0], []
    mode = Conversation(lambda: events.append('open'), lambda: events.append('close'), clock=lambda: now[0])
    with pytest.raises(Refusal):
        mode.toggle(on_battery=True)
    mode.toggle()
    now[0] = 29
    assert not mode.tick()
    now[0] = 30
    assert mode.tick()
    assert events == ['open', 'close']
    mode.toggle()
    mode.close()
    assert not mode.enabled and events[-1] == 'close'


def test_online_timeout_closes_owned_browser():
    now, events = [0], []
    mode = OnlineMode(lambda: events.append('closed'), events.append, clock=lambda: now[0])
    mode.enable()
    assert mode.name == 'ONLINE-RESTRICTED'
    now[0] = 900
    assert mode.tick()
    assert mode.name == 'OFFLINE'
    assert 'closed' in events


@pytest.mark.parametrize('url', ['http://example.com', 'https://evil.com', 'https://example.com.evil.com',
                               'https://user@example.com', 'file:///note.txt', 'chrome://downloads',
                               'https://example.com:8443', 'https://example.com/login',
                               'https://example.com/checkout', 'https://example.com/download'])
def test_url_guard(url):
    with pytest.raises(Refusal):
        safe_url(url, ['example.com'])


@pytest.mark.parametrize('text', ['password abc', '4111 1111 1111 1111', 'CVV 123', 'OTP 2233',
                                'hello\nsubmit', 'echo x; cmd', 'a|b', '$env:secret'])
def test_typing_guard(text):
    with pytest.raises(Refusal):
        safe_typing(text)


def test_typing_allowed_plain_text():
    assert safe_typing('Hello there') == 'Hello there'
    assert safe_url('https://example.com/about', ['example.com'])


def test_memory_is_bounded_and_cleared():
    memory = Memory(120)
    for _ in range(30):
        memory.remember('a'*30, 'b'*30)
    assert len(memory.turns) == 2
    memory.last_volume = 50
    memory.clear()
    assert not memory.turns and memory.last_volume is None


def test_timer_is_in_process():
    now, spoken = [0], []
    tools = SessionTools(Memory(), spoken.append, lambda: None, clock=lambda: now[0])
    tools.set_timer({'seconds': 3, 'label': 'tea'})
    now[0] = 2
    tools.tick()
    assert not spoken
    now[0] = 3
    tools.tick()
    assert spoken == ['Reminder, sir. tea']


def test_file_tools_confirm_and_never_overwrite(tmp_path):
    class FakeFiles:
        def __init__(self):
            self.data = {}
        def write(self, name, text, new=False):
            if new and name in self.data:
                raise Refusal('exists')
            self.data[name] = self.data.get(name, '') + text
        def read(self, name):
            return self.data[name]
    files = FakeFiles()
    tools = FileTools(files)
    registry = {'create_note': Tool(tools.create_note, SCHEMAS['create_note'], 1)}
    policy = Policy(Audit(tmp_path / 'audit.jsonl'), registry=registry, dry_run=False)
    call = {'tool': 'create_note', 'args': {'name': 'one.txt', 'text': 'keep me'}}
    assert 'keep me' in policy.dispatch(call)
    assert files.data == {}
    policy.confirm('yes.')
    assert files.data['one.txt'] == 'keep me\n'
    policy.dispatch(call)
    with pytest.raises(Refusal):
        policy.confirm('yes')
    assert files.data['one.txt'] == 'keep me\n'
    tools.undo_last_note_action({})
    assert files.data['one.txt'].startswith('keep me\n')
    assert 'Correction:' in files.data['one.txt']


def test_online_policy_cannot_be_bypassed(tmp_path):
    called = []
    tool = Tool(lambda args: called.append(True), EMPTY, 0, True)
    policy = Policy(Audit(tmp_path / 'audit.jsonl'), registry={'browser': tool}, dry_run=False)
    with pytest.raises(Refusal):
        policy.dispatch({'tool': 'browser', 'args': {}})
    assert not called


def test_audio_rejects_unintentional_capture():
    audio = Audio(lambda *a: None, lambda s: None)
    audio._capture(b'not audio', 480, None, None)
    assert audio.frames == []
    audio.live = True
    audio.speaking = True
    audio._capture(b'not audio', 480, None, None)
    assert audio.frames == []


def test_half_duplex_gate(monkeypatch):
    events = []
    audio = Audio(lambda *a: None, events.append)
    audio.live = True
    monkeypatch.setattr(audio, 'chime', lambda flag: events.append('open_chime' if flag else 'close_chime'))
    audio.begin_speech()
    assert not audio.live and audio.speaking
    assert 'close_chime' in events
    with pytest.raises(Refusal):
        audio.open()
    audio.end_speech()
    assert not audio.speaking


def test_audio_vad_and_ram_cap():
    events = []
    audio = Audio(lambda *e: events.append(e), lambda s: None, max_seconds=.15)
    audio.live = True
    audio.vad = SimpleNamespace(is_speech=lambda data, rate: True)
    for _ in range(6):
        audio._capture(bytes(960), 480, None, False)
    assert len(audio.frames) == 5 and events == [('utterance',)]


def test_speech_barge_in_under_300ms():
    began, stopped = Event(), Event()
    audio = SimpleNamespace(begin_speech=lambda: None, end_speech=lambda: None)
    def player(data, rate, channels, cancelled):
        began.set()
        while not cancelled():
            stopped.wait(.005)
        stopped.set()
    speech = Speech(audio, {}, lambda *e: None,
                    backend=lambda text: [(b'pcm', 16000, 1)], player=player)
    speech.say('hello')
    assert began.wait(1)
    start = time.monotonic()
    speech.stop()
    assert stopped.wait(.3)
    assert time.monotonic() - start < .3
    speech.shutdown()


def test_confidence_unknown_rejected(monkeypatch):
    import sys
    numpy = SimpleNamespace(int16='i', float32='f', frombuffer=lambda *a, **kw: SimpleNamespace(astype=lambda *_: 0))
    monkeypatch.setitem(sys.modules, 'numpy', numpy)
    monkeypatch.setitem(sys.modules, 'pywhispercpp', SimpleNamespace())
    monkeypatch.setitem(sys.modules, 'pywhispercpp.model', SimpleNamespace(Model=object))
    whisper = Whisper({})
    whisper.model = SimpleNamespace(transcribe=lambda *a, **kw: [SimpleNamespace(text='time', probability=float('nan'))])
    with pytest.raises(Refusal, match='confidently'):
        whisper.transcribe(b'00')


def test_runtime_has_no_network_imports():
    root = Path(__file__).resolve().parents[1]
    prohibited = {'requests', 'httpx', 'urllib.request', 'http.client'}
    for path in root.rglob('*.py'):
        relative = path.relative_to(root)
        if any(p.startswith('.') for p in relative.parts) or 'tests' in relative.parts or path.name == 'download_models.py':
            continue
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                assert not any(alias.name in prohibited for alias in node.names), path
                if any(alias.name == 'socket' for alias in node.names):
                    assert relative.as_posix() == 'startup.py'
            if isinstance(node, ast.ImportFrom):
                assert node.module not in prohibited, path


def test_launcher_is_on_demand():
    text = (Path(__file__).resolve().parents[1] / 'jarvis.bat').read_text()
    for required in ('HF_HUB_OFFLINE=1', 'PYTHONNOUSERSITE=1', '/LOW', 'pythonw.exe', 'goto missing', '--debug', 'pause'):
        assert required in text
    assert 'schtasks' not in text.lower() and 'reg add' not in text.lower()
