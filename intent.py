import re
from safety import user_text


def normalize(text):
    text = text.lower().strip().rstrip('?.!')
    text = re.sub(r'^please\s+', '', text)
    return re.sub(r'[, ]+(please|sir)$', '', text).strip()


class Intent:
    def __init__(self, commands):
        self.phrases = {normalize(phrase): tool for tool, phrases in commands.items() for phrase in phrases}

    def match(self, text):
        original = user_text(text).strip()
        text = normalize(original)
        if text in self.phrases:
            return {'tool': self.phrases[text], 'args': {}}
        # Recognize later-phase syntax but let the policy refuse unavailable tools.
        for pattern, tool, key in [(r'open (.+)', 'open_app', 'app'),
                                   (r'volume (\d{1,3})', 'set_volume', 'level')]:
            matched = re.fullmatch(pattern, text)
            if matched:
                value = matched[1]
                return {'tool': tool, 'args': {key: int(value) if key == 'level' else value}}
        if text == 'mute':
            return {'tool': 'mute', 'args': {}}
        from schemas import SCHEMAS
        aliases = {'forget that': 'forget_conversation', 'stop speaking': 'stop_speaking',
                   'what did you just do': 'what_did_you_do', 'list notes': 'list_folder',
                   'take a screenshot': 'take_screenshot', 'lock screen': 'lock_screen',
                   'pause music': 'media_play_pause', 'play music': 'media_play_pause',
                   'next track': 'media_next', 'previous track': 'media_prev',
                   'go online': 'enable_online', 'go offline': 'close_chrome',
                   'undo last note action': 'undo_last_note_action'}
        if text in aliases:
            return {'tool': aliases[text], 'args': {}}
        for pattern, tool, key in [(r'close ([a-z][a-z0-9_-]*)', 'close_app', 'app'),
                                   (r'brightness (\d{1,3})', 'set_brightness', 'level'),
                                   (r'read (.+\.txt)', 'read_file', 'name')]:
            matched = re.fullmatch(pattern, text)
            if matched:
                return {'tool': tool, 'args': {key: int(matched[1]) if key == 'level' else matched[1]}}
        matched = re.fullmatch(r'(create|append) note (.+\.txt): (.+)', original, re.I)
        if matched:
            return {'tool': 'create_note' if matched[1].lower() == 'create' else 'append_note',
                    'args': {'name': matched[2], 'text': matched[3]}}
        matched = re.fullmatch(r'(?:set )?timer (\d+) (seconds?|minutes?)(?: for (.+))?', text)
        if matched:
            return {'tool': 'set_timer', 'args': {'seconds': int(matched[1]) * (60 if matched[2].startswith('minute') else 1),
                                                'label': matched[3] or 'Your timer has finished.'}}
        return None

    def suggest(self, text):
        # Fuzzy matches are suggestions only. Never execute a near match.
        from rapidfuzz import process, fuzz
        match = process.extractOne(normalize(user_text(text)), self.phrases, scorer=fuzz.ratio, score_cutoff=85)
        return match[0] if match else None
