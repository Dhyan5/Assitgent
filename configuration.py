from pathlib import Path
import yaml
from jsonschema import Draft202012Validator
from safety import Refusal
from health import PROFILES


def load_config(root):
    with (root / 'config.yaml').open(encoding='utf-8') as stream:
        config = yaml.safe_load(stream)
    schema = {'type': 'object', 'required': ['profile', 'dry_run', 'model', 'stt', 'tts', 'security', 'apps', 'browser'],
              'properties': {
                  'profile': {'enum': list(PROFILES)}, 'dry_run': {'type': 'boolean'},
                  'max_calls_per_minute': {'type': 'integer', 'minimum': 1, 'maximum': 60},
                  'failure_limit': {'type': 'integer', 'minimum': 1, 'maximum': 10},
                  'stt_confidence': {'type': 'number', 'minimum': .75, 'maximum': 1},
                  'confirmation_seconds': {'type': 'integer', 'minimum': 1, 'maximum': 8},
                  'conversation_seconds': {'type': 'integer', 'minimum': 5, 'maximum': 60},
                  'idle_exit_seconds': {'type': 'integer', 'minimum': 30, 'maximum': 600},
                  'model_idle_seconds': {'type': 'integer', 'minimum': 5, 'maximum': 60}}}
    Draft202012Validator(schema).validate(config)
    if any(config.get('optional', {}).values()):
        raise Refusal('Optional wake word, identity verification and persistent memory are not enabled in this build.')
    for key in ('model', 'stt'):
        item = config[key]
        if not isinstance(item.get('threads'), int) or not 1 <= item['threads'] <= 8:
            raise Refusal('Inference thread count is outside the safe range.')
    if not 1024 <= config['model']['context'] <= 2048 or not 1 <= config['model']['max_tokens'] <= 256:
        raise Refusal('Model context or reply token cap is outside the safe range.')
    for item, field in [(config['model'], 'path'), (config['stt'], 'path'),
                         (config['tts'], 'path'), (config['tts'], 'config_path')]:
        path = Path(item[field]).expanduser()
        item[field] = str(path if path.is_absolute() else root / path)
    for key in ('approved_folder', 'log_dir'):
        config[key] = str(Path(config[key]).expanduser())
    return config
