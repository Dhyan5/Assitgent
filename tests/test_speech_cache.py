from types import SimpleNamespace
from tts import Speech


def test_canned_speech_cache_is_ram_bounded_and_unloaded():
    calls = []
    def backend(text):
        calls.append(text)
        yield (b'pcm', 16000, 1)
    speech = Speech(SimpleNamespace(begin_speech=lambda: None, end_speech=lambda: None), {},
                    lambda *args: None, backend=backend)
    try:
        assert list(speech._chunks('Goodbye, sir.')) == list(speech._chunks('Goodbye, sir.'))
        assert len(calls) == 1
        assert speech.cache_bytes <= 1_000_000
        speech.unload()
        assert not speech.cache and speech.cache_bytes == 0
    finally:
        speech.shutdown()
