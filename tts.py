"""Bounded sentence queue and cancellable RAM playback, with a local OS fallback."""
from queue import Queue, Empty, Full
from threading import Event, RLock, Thread
import time
from safety import Refusal, verify_model


class Speech:
    def __init__(self, audio, config, post, *, backend=None, player=None):
        self.audio, self.config, self.post = audio, config, post
        self.queue, self.closed = Queue(maxsize=12), Event()
        self.lock, self.generation, self.active = RLock(), 0, False
        self.backend, self.player, self.voice, self.engine = backend, player, None, None
        self.output_stream = None
        self.cache, self.cache_bytes = {}, 0
        self.worker = Thread(target=self._worker, name='jarvis-speech', daemon=True)
        self.worker.start()

    def say(self, text):
        if not text or self.closed.is_set():
            return
        item = (self.generation, str(text)[:65536])
        while not self.closed.is_set() and item[0] == self.generation:
            try:
                self.queue.put(item, timeout=.1)
                return
            except Full:
                continue

    def stop(self):
        with self.lock:
            self.generation += 1
            stream = self.output_stream
        if stream:
            try:
                stream.abort()
            except Exception:
                pass
        if self.engine:
            # Engine loop observes generation on its next 10 ms pump.
            pass
        while True:
            try:
                self.queue.get_nowait()
                self.queue.task_done()
            except Empty:
                break

    def _chunks(self, text):
        if text in self.cache:
            yield from self.cache[text]
            return
        canned = text in ('Goodbye, sir.', 'Cancelled, sir.', "I didn't catch that, sir.",
                          'Good evening, sir. JARVIS online in offline mode.')
        cached, size = [], 0
        for chunk in self._uncached_chunks(text):
            if canned:
                size += len(chunk[0])
                if size <= 1_000_000 - self.cache_bytes:
                    cached.append(chunk)
                else:
                    canned = False
                    cached.clear()
            yield chunk
        if canned:
            self.cache[text] = cached
            self.cache_bytes += size

    def _uncached_chunks(self, text):
        if self.backend:
            yield from self.backend(text)
            return
        if self.voice is None:
            import json
            import onnxruntime as ort
            from piper import PiperVoice
            from piper.config import PiperConfig
            path = verify_model(self.config['path'], self.config['sha256'], self.config['max_bytes'])
            verify_model(self.config['config_path'], self.config['config_sha256'], 100000)
            with open(self.config['config_path'], encoding='utf-8') as stream:
                voice_config = json.load(stream)
            if voice_config.get('phoneme_type', 'espeak') != 'espeak' or not voice_config.get('espeak', {}).get('voice', '').startswith('en'):
                raise Refusal('Only a verified local English espeak voice is supported.')
            options = ort.SessionOptions()
            options.intra_op_num_threads = 1
            options.inter_op_num_threads = 1
            options.enable_mem_pattern = False
            ort.disable_telemetry_events()
            self.voice = PiperVoice(config=PiperConfig.from_dict(voice_config),
                session=ort.InferenceSession(str(path), sess_options=options, providers=['CPUExecutionProvider']))
            self.voice.use_tashkeel = False
        for chunk in self.voice.synthesize(text):
            yield chunk.audio_int16_bytes, chunk.sample_rate, chunk.sample_channels

    def _play(self, data, rate, channels, generation):
        if self.player:
            self.player(data, rate, channels, lambda: generation != self.generation)
            return
        import sounddevice as sd
        with sd.RawOutputStream(samplerate=rate, channels=channels, dtype='int16', blocksize=max(1, rate // 50)) as stream:
            with self.lock:
                self.output_stream = stream
            step = max(2 * channels, int(rate * .02) * 2 * channels)
            try:
                for offset in range(0, len(data), step):
                    if generation != self.generation or self.closed.is_set():
                        break
                    stream.write(data[offset:offset+step])
            finally:
                with self.lock:
                    self.output_stream = None

    def _fallback(self, text, generation):
        import pyttsx3
        if self.engine is None:
            self.engine = pyttsx3.init()
            self.engine.setProperty('rate', 170)
            wanted = self.config.get('voice', 'Microsoft David Desktop')
            voices = self.engine.getProperty('voices')
            selected = next((voice for voice in voices if wanted.casefold() in voice.name.casefold()), None)
            if selected is not None:
                self.engine.setProperty('voice', selected.id)
        self.engine.say(text)
        self.engine.startLoop(False)
        try:
            while self.engine.isBusy() and generation == self.generation and not self.closed.is_set():
                self.engine.iterate()
                self.closed.wait(.01)
            self.engine.stop()
        finally:
            self.engine.endLoop()

    def _worker(self):
        while not self.closed.is_set():
            item = self.queue.get()
            if item is None:
                self.queue.task_done()
                break
            generation, text = item
            try:
                if generation != self.generation:
                    continue
                self.active = True
                self.audio.begin_speech()
                if self.config.get('backend') == 'system':
                    self._fallback(text, generation)
                else:
                    for data, rate, channels in self._chunks(text):
                        if generation != self.generation:
                            break
                        self._play(data, rate, channels, generation)
            except Exception:
                self.post('speech_error')
            finally:
                self.active = False
                self.audio.end_speech()
                self.queue.task_done()
                self.post('speech_done')

    def idle(self):
        return not self.active and self.queue.unfinished_tasks == 0

    def unload(self):
        if self.idle():
            self.voice = None
            self.cache.clear()
            self.cache_bytes = 0

    def shutdown(self):
        self.stop()
        self.closed.set()
        self.queue.put(None)
        self.worker.join(timeout=.3)
