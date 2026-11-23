"""Windows voice lifecycle: blocking event loop, one inference worker, hotkey control."""
from pathlib import Path
from queue import Queue, Empty, Full
from threading import Event, Thread
import time
import yaml
from audio import Audio
from audit import Audit
from browser.chrome import Chrome
from dialogue import Assistant
from health import Health
from intent import Intent
from lifecycle import Conversation
from llm import LocalLLM
from policy import Policy
from safety import Refusal
from secure_files import SecureFiles
from session import Memory, SessionTools
from startup import InstanceLock, self_check
from stt import Whisper
from tools.files import FileTools
from tools.registry import full_registry
from tools.system import SystemTools
from tray import Tray
from tts import Speech
from watchdog import process_memory_limit
from health import PROFILES


class Runtime:
    def __init__(self, root, config, debug=False):
        self.root, self.config, self.debug = root, config, debug
        self.events, self.work = Queue(maxsize=64), Queue(maxsize=1)
        self.quit_event, self.cancelled = Event(), Event()
        self.epoch, self.busy, self.ptt = 0, False, False
        self.last_use, self.last_health = time.monotonic(), time.monotonic()
        self.lock = InstanceLock(Path(config['log_dir']) / 'jarvis.lock')
        self.lock.acquire()
        self.tray = self.speech = self.audio = self.browser = self.listener = self.memory_job = None
        try:
            self_check(config, root)
            self.memory_job = process_memory_limit(PROFILES[config['profile']][1])
            self.audit = Audit(Path(config['log_dir']) / 'audit.jsonl')
            self.health = Health(config)
            self.memory = Memory(config['memory_chars'])
            self.tray = Tray(self.kill)
            self.audio = Audio(self.post, self.state)
            self.speech = Speech(self.audio, config['tts'], self.post)
            self.session = SessionTools(self.memory, self.speech.say, self.speech.stop)
            self.browser = Chrome(config['browser'], Path(config['approved_folder']) / 'chrome-profiles',
                                  self.speech.say, self.audit)
            self.audit.mode = lambda: self.browser.mode.name
            registry = full_registry(FileTools(SecureFiles(config['approved_folder'])),
                                     SystemTools(config['apps']), self.session, self.browser)
            self.policy = Policy(self.audit, dry_run=config['dry_run'], registry=registry,
                rate=config['max_calls_per_minute'], failure_limit=config['failure_limit'],
                confirmation_seconds=config['confirmation_seconds'], guard=self._guard,
                mode=lambda: self.browser.mode.name, deadline_seconds=config['tool_deadline_seconds'],
                on_timeout=lambda: self.post('tool_timeout'))
            self.session.policy = self.policy
            self.whisper = Whisper(config['stt'], config['stt_confidence'])
            self.llm = LocalLLM(config['model'], (root / 'persona.txt').read_text(), registry,
                                cancelled=lambda: self.cancelled.is_set() or self.quit_event.is_set())
            self.assistant = Assistant(Intent(yaml.safe_load((root / 'commands.yaml').read_text())),
                                       self.policy, self.llm, self.memory, self.speech.say)
            self.conversation = Conversation(lambda: self.audio.open(True),
                lambda: self.audio.close(discard=True), timeout=config['conversation_seconds'])
            self.worker = Thread(target=self._worker, name='jarvis-inference', daemon=True)
            self.worker.start()
            self._hotkeys()
        except Exception:
            self.cleanup()
            raise

    def post(self, event, payload=None):
        try:
            self.events.put_nowait((event, payload))
        except Full:
            # Losing a control event is unsafe: immediately close the microphone.
            self.quit_event.set()
            if self.audio:
                self.audio.live = False

    def state(self, state):
        if self.tray:
            self.tray.state(state, self.browser.mode.name if self.browser else 'OFFLINE')

    def _guard(self, name):
        if self.cancelled.is_set() or self.quit_event.is_set():
            raise Refusal('Cancelled, sir.')
        self.health.tool(name)

    def _hotkeys(self):
        from pynput.keyboard import Listener, HotKey
        keys = self.config['hotkeys']
        ptt_keys = set(HotKey.parse(keys['push_to_talk']))
        pressed = set()
        combinations = [HotKey(HotKey.parse(keys['conversation']), lambda: self.post('conversation')),
                        HotKey(HotKey.parse(keys['stop']), self.interrupt),
                        HotKey(HotKey.parse(keys['quit']), self.kill)]
        def press(key):
            key = self.listener.canonical(key)
            was_active = ptt_keys <= pressed
            pressed.add(key)
            if not was_active and ptt_keys <= pressed:
                self.interrupt()
                self.ptt = True
                self.post('ptt_open')
            for combination in combinations:
                combination.press(key)
        def release(key):
            key = self.listener.canonical(key)
            was_active = ptt_keys <= pressed
            pressed.discard(key)
            if was_active and not ptt_keys <= pressed:
                self.ptt = False
                self.post('utterance')
            for combination in combinations:
                combination.release(key)
        self.listener = Listener(on_press=press, on_release=release)
        self.listener.start()

    def interrupt(self):
        self.epoch += 1
        self.cancelled.set()
        if self.speech:
            self.speech.stop()

    def kill(self, *_):
        self.quit_event.set()
        self.interrupt()
        if self.audio:
            self.audio.close(discard=True, notice=False)
        if self.browser:
            self.browser.mode.close()
        self.post('quit')

    def _worker(self):
        import pythoncom
        pythoncom.CoInitialize()
        try:
            while not self.quit_event.is_set():
                item = self.work.get()
                if item is None:
                    break
                epoch, pcm = item
                try:
                    self.health.heavy()
                    self.llm.close()
                    text = self.whisper.transcribe(pcm, lambda: epoch != self.epoch or self.quit_event.is_set())
                    self.whisper.close()
                    if epoch != self.epoch or self.quit_event.is_set():
                        continue
                    self.health.heavy()
                    answer = self.assistant.handle(text)
                    if self.policy.pending:
                        # Confirmation clock starts after the full spoken prompt.
                        self.policy.pending = (self.policy.pending[0], float('inf'))
                    if epoch == self.epoch and not self.quit_event.is_set() and not self.assistant.streamed:
                        self.speech.say(answer)
                except Refusal as exc:
                    if epoch == self.epoch:
                        self.speech.say(str(exc))
                except Exception:
                    if epoch == self.epoch:
                        self.speech.say('The request failed safely, sir.')
                finally:
                    self.whisper.close()
                    self.post('work_done')
        finally:
            pythoncom.CoUninitialize()

    def _capture_result(self):
        pcm = self.audio.close()
        if not pcm:
            return
        if self.busy:
            self.speech.say('The previous request is still stopping, sir.')
            return
        self.cancelled.clear()
        self.busy = True
        self.last_use = time.monotonic()
        self.conversation.touch()
        self.state('thinking')
        self.work.put_nowait((self.epoch, pcm))

    def _resume(self):
        if self.busy or not self.speech.idle() or self.quit_event.is_set():
            return
        if self.ptt:
            self.audio.open()
        elif self.policy.pending:
            if self.policy.pending[1] == float('inf'):
                self.policy.pending = (self.policy.pending[0], time.monotonic() + self.config['confirmation_seconds'])
            self.audio.open(True)
        elif self.conversation.enabled and not self.conversation.tick():
            self.audio.open(True)

    def loop(self):
        self.speech.say('Good evening, sir. JARVIS online in offline mode.')
        try:
            while not self.quit_event.is_set():
                now = time.monotonic()
                # No idle poll faster than five seconds; real deadlines wake exactly.
                deadlines = [self.last_health + 5, self.session.next_deadline()]
                if not self.busy and not self.audio.live:
                    deadlines.append(self.last_use + self.config['idle_exit_seconds'])
                if self.policy.pending:
                    deadlines.append(self.policy.pending[1])
                if self.conversation.enabled:
                    deadlines.append(self.conversation.deadline)
                if self.browser.mode.active:
                    deadlines.append(self.browser.mode.deadline)
                timeout = max(.01, min(deadlines) - now)
                try:
                    event, payload = self.events.get(timeout=timeout)
                except Empty:
                    event = 'tick'
                try:
                    if event == 'quit':
                        break
                    if event == 'conversation':
                        self.last_use = time.monotonic()
                        self.conversation.toggle(on_battery=self.health.on_battery(),
                            allow_battery=self.config['conversation_on_battery'])
                    elif event == 'ptt_open':
                        self.last_use = time.monotonic()
                        self._resume()
                    elif event == 'utterance':
                        self._capture_result()
                    elif event == 'audio_error':
                        self.audio.close(discard=True)
                        self.speech.say('Audio capture failed; please repeat, sir.')
                    elif event == 'speech_error':
                        self.audio.close(discard=True)
                        self.state('error')
                        raise Refusal('Speech output failed. Voice mode must stop safely.')
                    elif event == 'tool_timeout':
                        self.interrupt()
                        self.audio.close(discard=True)
                        self.speech.say('A tool exceeded its deadline. Safety lock engaged, sir.')
                    elif event == 'work_done':
                        self.busy = False
                        self._resume()
                    elif event == 'speech_done':
                        self._resume()
                    self._tick()
                except Refusal as exc:
                    if event == 'speech_error':
                        self.kill()
                    else:
                        self.speech.say(str(exc))
        finally:
            self.cleanup()

    def _tick(self):
        now = time.monotonic()
        self.conversation.tick()
        self.browser.mode.tick()
        self.session.tick()
        if self.policy.expire_confirmation():
            self.audio.close(discard=True)
            self.speech.say('Cancelled, sir.')
        if now - self.last_health >= 5:
            self.last_health = now
            if self.health.on_battery() and self.conversation.enabled and not self.config['conversation_on_battery']:
                self.conversation.close()
                self.speech.say('On battery; conversation mode closed, sir.')
        if not self.busy and now - self.last_use >= self.config['model_idle_seconds']:
            self.llm.close()
            self.whisper.close()
            self.speech.unload()
        if not self.busy and not self.audio.live and now - self.last_use >= self.config['idle_exit_seconds']:
            self.kill()

    def cleanup(self):
        self.quit_event.set()
        self.cancelled.set()
        if self.listener:
            self.listener.stop()
        if self.audio:
            self.audio.close(discard=True, notice=False)
        if self.browser:
            self.browser.mode.close()
        if self.speech:
            self.speech.stop()
            self.speech.say('Goodbye, sir.')
            end = time.monotonic() + .3
            while not self.speech.idle() and time.monotonic() < end:
                Event().wait(.01)
            self.speech.shutdown()
        if self.tray:
            self.tray.close()
        if hasattr(self, 'memory'):
            self.memory.clear()
        self.lock.close()
        if self.memory_job:
            self.memory_job.Close()
