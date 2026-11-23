"""Read-only readiness report. Does not open audio streams, launch apps, or download."""
from importlib import metadata
import json
from pathlib import Path
import platform
import sys
from safety import verify_model


def report(root, config):
    packages = {}
    for line in (root / 'requirements.in').read_text().splitlines():
        if '==' not in line or line.startswith('#'):
            continue
        package, rest = line.split('==', 1)
        expected = rest.split(';')[0].strip()
        try:
            actual = metadata.version(package)
        except metadata.PackageNotFoundError:
            actual = None
        packages[package] = {'expected': expected, 'installed': actual, 'matches': actual == expected}
    models = {}
    for key in ('model', 'stt'):
        item = config[key]
        try:
            verify_model(item['path'], item['sha256'], item['max_bytes'])
            models[key] = 'verified'
        except Exception as exc:
            models[key] = str(exc)
    if config['tts']['backend'] == 'piper':
        try:
            verify_model(config['tts']['path'], config['tts']['sha256'], config['tts']['max_bytes'])
            verify_model(config['tts']['config_path'], config['tts']['config_sha256'], 100000)
            models['tts'] = 'verified'
        except Exception as exc:
            models['tts'] = str(exc)
    else:
        models['tts'] = 'Windows built-in voice: ' + config['tts'].get('voice', 'default')
    result = {'python': platform.python_version(), 'executable': sys.executable,
              'dedicated_venv': sys.prefix != sys.base_prefix,
              'hashed_lock_present': (root / 'requirements.txt').is_file(),
              'profile': config['profile'], 'packages': packages, 'models': models,
              'online_enabled': config['browser']['enabled'],
              'production_ready': False,
              'blockers': ['OS setup and real voice/model validation pending',
                           'Outbound self-test exception and implementation unresolved',
                           'Native stack and model footprint must fit the hard profile budget']}
    print(json.dumps(result, indent=2))
    return result
