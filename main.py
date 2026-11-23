"""Phase 1 text harness. Production startup remains locked until OS checks exist."""
import argparse
import os
from pathlib import Path
import sys

for key in ('HF_HUB_OFFLINE', 'TRANSFORMERS_OFFLINE', 'DO_NOT_TRACK', 'PYTHONNOUSERSITE', 'PYTHONDONTWRITEBYTECODE'):
    os.environ[key] = '1'
sys.dont_write_bytecode = True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--debug', action='store_true')
    parser.add_argument('--doctor', action='store_true', help='Read-only readiness report')
    parser.add_argument('--text-test', action='store_true', help='Read-only development harness; no model loading')
    args = parser.parse_args()
    if args.doctor:
        from configuration import load_config
        from diagnostics import report
        root = Path(__file__).resolve().parent
        report(root, load_config(root))
        return 0
    if not args.text_test:
        try:
            from configuration import load_config
            from runtime import Runtime
            root = Path(__file__).resolve().parent
            runtime = Runtime(root, load_config(root), args.debug)
            runtime.loop()
            return 0
        except Exception as exc:
            message = 'JARVIS startup refused: ' + str(exc).splitlines()[0][:300]
            print(message)
            if not args.debug and os.name == 'nt':
                import ctypes
                ctypes.windll.user32.MessageBoxW(None, message, 'JARVIS', 0x10)
            return 2
    import yaml
    from audit import Audit
    from dialogue import Assistant
    from intent import Intent
    from policy import Policy
    root = Path(__file__).resolve().parent
    config = yaml.safe_load((root / 'config.yaml').read_text(encoding='utf-8'))
    commands = yaml.safe_load((root / 'commands.yaml').read_text(encoding='utf-8'))
    # Intentionally fixed capabilities; configuration cannot enable models or writes in this harness.
    audit = Audit(root / 'phase1-audit.jsonl')
    policy = Policy(audit, dry_run=config['dry_run'], rate=config['max_calls_per_minute'],
                    failure_limit=config['failure_limit'], confirmation_seconds=config['confirmation_seconds'])
    assistant = Assistant(Intent(commands), policy)
    print('JARVIS Phase 1 text test. No microphone, model or network. Type exit to finish.')
    try:
        while True:
            text = input('You> ')
            if text.strip().lower() in {'exit', 'quit'}:
                break
            if text.strip():
                print('JARVIS> ' + assistant.handle(text))
    except (EOFError, KeyboardInterrupt):
        pass
    print('Goodbye, sir.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
