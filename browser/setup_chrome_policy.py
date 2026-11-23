"""Apply the configured machine-wide Chrome restrictions; requires elevation."""
import argparse
from pathlib import Path
import yaml
from browser.guard import setup_chrome_policy


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Write HKLM Chrome policies')
    args = parser.parse_args()
    if not args.apply:
        parser.error('Pass --apply to write the explicit machine-wide policy set.')
    config = yaml.safe_load((Path(__file__).resolve().parents[1] / 'config.yaml').read_text(encoding='utf-8'))
    setup_chrome_policy(config['browser']['hosts'])
    print('Chrome policies applied and read back. Verify at chrome://policy.')


if __name__ == '__main__':
    main()
