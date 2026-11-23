from pathlib import Path
from threading import Event
from types import SimpleNamespace
import hashlib
import json
import sys
import pytest
import yaml
from audit import Audit
from dialogue import Assistant
from intent import Intent
from policy import Policy
from safety import Refusal
from session import Memory
from tools.registry import Tool, EMPTY
from schemas import SCHEMAS
from startup import check_firewall, check_deployment_root, outbound_self_test
from download_models import provision


def test_followup_volume_and_forget(tmp_path):
    memory, levels = Memory(), []
    registry = {
        'set_volume': Tool(lambda args: levels.append(args['level']) or 'done', SCHEMAS['set_volume']),
        'forget_conversation': Tool(lambda args: memory.clear() or 'forgotten', EMPTY)}
    policy = Policy(Audit(tmp_path / 'audit.jsonl'), registry=registry, dry_run=False)
    assistant = Assistant(Intent({}), policy, memory=memory)
    assert assistant.handle('volume 50') == 'done'
    assert assistant.handle('now turn it down a bit') == 'done'
    assert levels == [50, 45]
    assistant.handle('forget that')
    assert 'specify' in assistant.handle('turn it down a bit')


def test_tool_deadline_locks_future_actions(tmp_path):
    expired = Event()
    def slow(args):
        assert expired.wait(1)
        return 'late'
    policy = Policy(Audit(tmp_path / 'audit.jsonl'), registry={'slow': Tool(slow, EMPTY)},
                    dry_run=False, deadline_seconds=.02, on_timeout=expired.set)
    with pytest.raises(Refusal):
        policy.dispatch({'tool': 'slow', 'args': {}})
    assert policy.failures >= policy.failure_limit
    with pytest.raises(Refusal, match='lock engaged'):
        policy.dispatch({'tool': 'slow', 'args': {}})


def test_firewall_must_cover_all_profiles(monkeypatch):
    rule = SimpleNamespace(Enabled=True, Direction=2, Action=0, ApplicationName=sys.executable,
                           Protocol=256, LocalAddresses='*', RemoteAddresses='*', InterfaceTypes='All',
                           ServiceName='', Profiles=7)
    firewall = SimpleNamespace(FirewallEnabled=lambda profile: True, Rules=[rule])
    client = SimpleNamespace(Dispatch=lambda name: firewall)
    monkeypatch.setitem(sys.modules, 'win32com', SimpleNamespace(client=client))
    monkeypatch.setitem(sys.modules, 'win32com.client', client)
    check_firewall(sys.executable)
    rule.Profiles = 1
    with pytest.raises(Refusal):
        check_firewall(sys.executable)
    rule.Profiles = 7
    rule.RemoteAddresses = '192.0.2.0/24'
    with pytest.raises(Refusal):
        check_firewall(sys.executable)


def test_deployment_rejects_onedrive_before_os_acl_import():
    with pytest.raises(Refusal, match='outside OneDrive'):
        check_deployment_root(Path('C:/Users/Dhyan/OneDrive/Desktop/Jarvis'))


def test_outbound_probe_passes_closed_and_rejects_open():
    from safety import Refusal
    def blocked(address, timeout):
        raise OSError('blocked')
    outbound_self_test(blocked)
    class Socket:
        def __init__(self):
            self.closed = False
        def close(self):
            self.closed = True
    opened = Socket()
    with pytest.raises(Refusal, match='Outbound traffic is reachable'):
        outbound_self_test(lambda address, timeout: opened)
    assert opened.closed


def test_chrome_setup_writes_then_reads_exact_values():
    from browser.guard import setup_chrome_policy
    class Key(dict):
        def __enter__(self):
            return self
        def __exit__(self, *_):
            return False
    class FakeRegistry:
        HKEY_LOCAL_MACHINE = object()
        KEY_SET_VALUE = 1
        KEY_WOW64_64KEY = 2
        KEY_READ = 4
        REG_DWORD = 10
        REG_SZ = 11
        def __init__(self):
            self.keys = {}
        def CreateKeyEx(self, root, path, reserved, access):
            return self.keys.setdefault(path, Key())
        def SetValueEx(self, key, name, reserved, kind, value):
            key[name] = (value, kind)
        def OpenKey(self, root, path, reserved, access):
            return self.keys[path]
        def QueryValueEx(self, key, name):
            return key[name]
        def QueryInfoKey(self, key):
            return (0, len(key), 0)
        def EnumValue(self, key, index):
            name = sorted(key)[index]
            return (name, key[name][0], key[name][1])
    registry = FakeRegistry()
    setup_chrome_policy(['example.com'], registry=registry)


def test_manual_downloader_hash_and_overwrite(tmp_path):
    from io import BytesIO
    class Response(BytesIO):
        def geturl(self):
            return 'https://example.com/model.gguf'
    fake = SimpleNamespace(open=lambda *a, **kw: Response(b'fixture'))
    entry = {'url': 'https://example.com/model.gguf', 'sha256': hashlib.sha256(b'fixture').hexdigest(),
             'filename': 'model.gguf', 'max_bytes': 100, 'hosts': ['example.com']}
    path = provision(entry, tmp_path, opener=fake)
    assert path.read_bytes() == b'fixture'
    with pytest.raises(Refusal, match='exists'):
        provision(entry, tmp_path, opener=fake)


def test_stage_b_adapter_passes_grammar_and_revalidates(monkeypatch):
    from llm import LocalLLM
    supplied = []
    class Grammar:
        @staticmethod
        def from_json_schema(schema, verbose=False):
            supplied.append(json.loads(schema))
            return 'grammar'
    monkeypatch.setitem(sys.modules, 'llama_cpp', SimpleNamespace(LlamaGrammar=Grammar))
    model = LocalLLM({}, 'persona')
    def complete(**kwargs):
        assert kwargs['grammar'] == 'grammar'
        return {'choices': [{'message': {'content': '{"tool":"delete","args":{}}'}}]}
    model.model = SimpleNamespace(create_chat_completion=complete, tokenize=lambda text, **kw: list(text[:100]))
    with pytest.raises(Refusal, match='invalid route'):
        model.route('hello')
    assert supplied


def test_streamed_chat_failure_still_returns_error_to_speech(tmp_path):
    class Model:
        def route(self, text):
            return {'tool': 'none', 'route': 'chat'}
        def stream_chat(self, text, history):
            yield 'First sentence.'
            raise RuntimeError('model failure')
    spoken = []
    assistant = Assistant(Intent({}), Policy(Audit(tmp_path / 'audit.jsonl')), Model(), chat_sink=spoken.append)
    assert 'failed safely' in assistant.handle('hello')
    assert spoken == ['First sentence.']
    assert not assistant.streamed


def test_registered_handlers_revalidate_arguments():
    from tools.system import SystemTools
    from jsonschema.exceptions import ValidationError
    with pytest.raises(ValidationError):
        SystemTools({}).set_volume({'level': 101})


def test_imports_do_not_load_models_or_capture_audio():
    import runtime
    assert 'pywhispercpp.model' not in sys.modules
    assert 'piper' not in sys.modules
    assert 'llama_cpp' not in sys.modules


def test_incomplete_manifest_rejected_before_download(monkeypatch, tmp_path):
    import download_models
    manifest = tmp_path / 'manifest.json'
    manifest.write_text(json.dumps([{'url': 'https://example.com/a.onnx', 'filename': 'a.onnx',
                                    'sha256': None, 'max_bytes': 100, 'hosts': ['example.com']}]))
    monkeypatch.setattr(sys, 'argv', ['download_models.py', str(manifest), '--output', str(tmp_path / 'models')])
    monkeypatch.setattr(download_models, 'build_opener', lambda *a: pytest.fail('Network attempted'))
    with pytest.raises(Refusal, match='SHA256'):
        download_models.main()
    assert not (tmp_path / 'models').exists()


def test_pending_confirmation_is_typed_user_only(tmp_path):
    effects = []
    policy = Policy(Audit(tmp_path / 'audit.jsonl'), dry_run=False,
                    registry={'note': Tool(lambda args: effects.append(True), EMPTY, 1)})
    assistant = Assistant(Intent({}), policy)
    policy.dispatch({'tool': 'note', 'args': {}})
    assistant.handle('yes', source='web')
    assert not effects


def test_note_intent_preserves_user_text():
    call = Intent({}).match('Create note Meeting.txt: Meet Alice at Noon!')
    assert call['args'] == {'name': 'Meeting.txt', 'text': 'Meet Alice at Noon!'}
