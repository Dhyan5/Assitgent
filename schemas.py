"""Closed schemas shared by handlers, router, and policy."""
from functools import wraps
from jsonschema import Draft202012Validator


def obj(**properties):
    return {'type': 'object', 'properties': properties, 'required': list(properties), 'additionalProperties': False}


EMPTY = obj()
NAME = {'type': 'string', 'pattern': r'^[A-Za-z0-9][A-Za-z0-9 _-]{0,60}\.txt$'}
TEXT = {'type': 'string', 'minLength': 1, 'maxLength': 2000}
APP = {'type': 'string', 'pattern': r'^[a-z][a-z0-9_-]{0,30}$'}
LEVEL = {'type': 'integer', 'minimum': 0, 'maximum': 100}
SCHEMAS = {
    **{name: EMPTY for name in ('get_time_date', 'get_battery_status', 'system_status', 'mute',
       'media_play_pause', 'media_next', 'media_prev', 'lock_screen', 'list_folder', 'stop_speaking',
       'forget_conversation', 'what_did_you_do', 'undo_last_note_action', 'take_screenshot',
       'enable_online', 'close_chrome')},
    'open_app': obj(app=APP), 'close_app': obj(app=APP),
    'set_volume': obj(level=LEVEL), 'set_brightness': obj(level={'type': 'integer', 'minimum': 10, 'maximum': 100}),
    'read_file': obj(name=NAME), 'create_note': obj(name=NAME, text=TEXT), 'append_note': obj(name=NAME, text=TEXT),
    'set_timer': obj(seconds={'type': 'integer', 'minimum': 1, 'maximum': 86400}, label=TEXT),
    'open_chrome': obj(url={'type': 'string', 'minLength': 1, 'maxLength': 2048}),
    'web_search': obj(query={'type': 'string', 'minLength': 1, 'maxLength': 200}),
    'type_text': obj(text=TEXT),
}


def checked(name):
    def decorate(handler):
        @wraps(handler)
        def wrapped(self, args):
            Draft202012Validator(SCHEMAS[name]).validate(args)
            return handler(self, args)
        return wrapped
    return decorate
