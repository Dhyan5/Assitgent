import gc
import math
from safety import Refusal, verify_model


class Whisper:
    def __init__(self, config, threshold=.80):
        self.config, self.threshold, self.model = config, threshold, None

    def transcribe(self, pcm, cancelled=lambda: False):
        if not pcm or len(pcm) > 16000 * 2 * 15:
            raise Refusal("I didn't catch that, sir.")
        import numpy as np
        from pywhispercpp.model import Model
        if self.model is None:
            path = verify_model(self.config['path'], self.config['sha256'], self.config['max_bytes'])
            self.model = Model(str(path), n_threads=self.config.get('threads', 1),
                               context_params={'use_gpu': False}, language='en', no_context=True,
                               print_realtime=False, print_progress=False, print_timestamps=False)
        samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768
        segments = self.model.transcribe(samples, extract_probability=True, abort_callback=cancelled)
        if cancelled() or not segments:
            raise Refusal("I didn't catch that, sir.")
        confidence = min(float(getattr(item, 'probability', float('nan'))) for item in segments)
        if not math.isfinite(confidence) or confidence < self.threshold:
            raise Refusal("I didn't catch that confidently, sir. Please repeat.")
        text = ' '.join(item.text for item in segments).strip()
        if not text:
            raise Refusal("I didn't catch that, sir.")
        return text

    def close(self):
        if self.model is not None:
            self.model = None
            gc.collect()
