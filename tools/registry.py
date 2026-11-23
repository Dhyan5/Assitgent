from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from jsonschema import Draft202012Validator

EMPTY = {'type': 'object', 'properties': {}, 'additionalProperties': False}


def get_time_date(args):
    Draft202012Validator(EMPTY).validate(args)
    return datetime.now().astimezone().strftime('It is %H:%M on %A, %d %B %Y, sir.')


def get_battery_status(args):
    Draft202012Validator(EMPTY).validate(args)
    import psutil
    battery = psutil.sensors_battery()
    if battery is None:
        return 'No battery information is available, sir.'
    return f'Battery is at {battery.percent:.0f} percent, sir.'


def system_status(args):
    Draft202012Validator(EMPTY).validate(args)
    import psutil
    memory = psutil.virtual_memory()
    return f'Memory usage is {memory.percent:.0f} percent, sir.'


@dataclass(frozen=True)
class Tool:
    handler: object
    schema: dict
    tier: int = 0
    online: bool = False


REGISTRY = MappingProxyType({
    'get_time_date': Tool(get_time_date, EMPTY),
    'get_battery_status': Tool(get_battery_status, EMPTY),
    'system_status': Tool(system_status, EMPTY),
})


def call_schema(registry=REGISTRY):
    variants = [{'type': 'object', 'properties': {'tool': {'const': name}, 'args': tool.schema},
                 'required': ['tool', 'args'], 'additionalProperties': False}
                for name, tool in registry.items()]
    variants.append({'type': 'object', 'properties': {'tool': {'const': 'none'}, 'route': {'const': 'chat'}},
                     'required': ['tool', 'route'], 'additionalProperties': False})
    return {'oneOf': variants}


def full_registry(files, system, session, browser=None):
    from schemas import SCHEMAS
    registry = dict(REGISTRY)
    for owner, names, tier in [
        (files, ('list_folder', 'read_file'), 0),
        (files, ('create_note', 'append_note', 'undo_last_note_action', 'take_screenshot'), 1),
        (system, ('open_app', 'close_app', 'set_volume', 'mute', 'set_brightness', 'media_play_pause',
                  'media_next', 'media_prev', 'lock_screen'), 0),
        (session, ('set_timer', 'stop_speaking', 'forget_conversation', 'what_did_you_do'), 0),
    ]:
        for name in names:
            registry[name] = Tool(getattr(owner, name), SCHEMAS[name], tier)
    if browser:
        registry['enable_online'] = Tool(browser.enable_online, SCHEMAS['enable_online'], 1)
        for name in ('open_chrome', 'web_search', 'close_chrome', 'type_text'):
            registry[name] = Tool(getattr(browser, name), SCHEMAS[name], 1 if name == 'type_text' else 0, True)
    return MappingProxyType(registry)
