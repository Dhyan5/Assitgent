"""16 kHz mono RAM-only capture. No stream exists until intentional opening."""
from threading import RLock
import time
from safety import Refusal


class Audio:
    def __init__(self, post, state, *, max_seconds=15, silence_seconds=0.7, clock=time.monotonic):
        self.post, self.state, self.clock = post, state, clock
        self.max_seconds, self.silence_seconds = max_seconds, silence_seconds
        self.stream = None
        self.lock = RLock()
        self.frames, self.speech, self.silence, self.stopping = [], 0, 0, False
        self.live, self.speaking, self.conversation = False, False, False

    def open(self, conversation=False):
        with self.lock:
            if self.speaking:
                raise Refusal('Microphone cannot open during speech.')
            if self.live:
                return
            import sounddevice as sd
            import webrtcvad
            self.vad = webrtcvad.Vad(2)
            self.frames, self.speech, self.silence, self.stopping = [], 0, 0, False
            self.conversation = conversation
            self.chime(True)
            self.state('listening')
            self.live = True
            try:
                self.stream = sd.RawInputStream(samplerate=16000, channels=1, dtype='int16',
                                                blocksize=480, callback=self._capture)
                self.stream.start()
            except Exception:
                self.live = False
                if self.stream:
                    self.stream.close()
                self.stream = None
                self.state('idle')
                raise

    def _capture(self, data, frames, timing, status):
        with self.lock:
            if not self.live or self.speaking or self.stopping:
                return
            if status or frames != 480:
                self.stopping = True
                self.post('audio_error')
                return
            chunk = bytes(data)
            self.frames.append(chunk)
            voiced = self.vad.is_speech(chunk, 16000)
            if voiced:
                self.speech += 1
                self.silence = 0
            else:
                self.silence += 1
            if not self.speech and len(self.frames) > 10:
                self.frames = self.frames[-10:]
            # Active audio frame callbacks are not idle polling.
            if len(self.frames) * .03 >= self.max_seconds or (
                self.conversation and self.speech >= 5 and self.silence * .03 >= self.silence_seconds):
                self.stopping = True
                self.post('utterance')

    def close(self, *, discard=False, notice=True):
        with self.lock:
            was_live, self.live = self.live, False
            stream, self.stream = self.stream, None
        if stream:
            stream.abort()
            stream.close()
        with self.lock:
            data = b''.join(self.frames) if not discard and self.speech >= 5 else b''
            self.frames.clear()
            self.speech = self.silence = 0
        if was_live:
            self.state('idle')
            if notice:
                self.chime(False)
        return data

    def begin_speech(self):
        self.close(discard=True)
        with self.lock:
            self.speaking = True
        self.state('speaking')

    def end_speech(self):
        with self.lock:
            self.speaking = False
        self.state('idle')

    @staticmethod
    def chime(opening):
        import numpy as np
        import sounddevice as sd
        samples = np.arange(1600, dtype=np.float32) / 16000
        wave = .08 * np.sin(2 * np.pi * (880 if opening else 440) * samples)
        sd.play(wave, 16000, blocking=True)
