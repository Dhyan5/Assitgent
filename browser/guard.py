import re
from urllib.parse import urlsplit
from safety import Refusal


def safe_url(url, hosts):
    if not isinstance(url, str) or len(url) > 2048 or any(ord(c) < 33 for c in url):
        raise Refusal('Invalid browser URL.')
    parsed = urlsplit(url)
    if (parsed.scheme != 'https' or parsed.hostname not in hosts or parsed.username or parsed.password
            or parsed.port not in (None, 443) or '\\' in url):
        raise Refusal('Only approved HTTPS domains are permitted, sir.')
    if re.search(r'(login|signin|checkout|payment|download|webstore|oauth)', url, re.I):
        raise Refusal('That browser destination is outside my permissions.')
    return url


def safe_typing(text):
    if not isinstance(text, str) or not 0 < len(text) <= 500:
        raise Refusal('Text is too long.')
    if re.search(r'(password|passcode|card|cvv|otp|one.?time|payment|secret|token|pin\b|\d{4,})', text, re.I):
        raise Refusal('Sensitive text cannot be entered, sir.')
    if any(mark in text for mark in (';', '|', '`', '$', '<', '>', '{', '}', '\\', '\n', '\r')):
        raise Refusal('Shell-like or control text is not permitted.')
    return ''.join(c for c in text if ord(c) >= 32 and ord(c) != 127)


def check_chrome_policies(hosts, *, registry=None):
    if registry is None:
        import winreg as registry
    base = r'SOFTWARE\Policies\Google\Chrome'
    scalar = {'DownloadRestrictions': 3, 'PasswordManagerEnabled': 0,
              'BrowserSignin': 0, 'SyncDisabled': 1, 'IncognitoModeAvailability': 1,
              'DeveloperToolsAvailability': 2}
    flags = registry.KEY_READ | registry.KEY_WOW64_64KEY
    try:
        with registry.OpenKey(registry.HKEY_LOCAL_MACHINE, base, 0, flags) as key:
            for name, expected in scalar.items():
                if registry.QueryValueEx(key, name)[0] != expected:
                    raise Refusal('Required Chrome policy is missing.')
        required = {'ExtensionInstallBlocklist': {'*'}, 'URLBlocklist': {'*'},
                    'URLAllowlist': {'https://' + host for host in hosts}}
        for name, expected in required.items():
            with registry.OpenKey(registry.HKEY_LOCAL_MACHINE, base + '\\' + name, 0, flags) as key:
                count = registry.QueryInfoKey(key)[1]
                actual = {registry.EnumValue(key, i)[1] for i in range(count)}
                if actual != expected:
                    raise Refusal('Chrome URL or extension policies do not match the approved list.')
    except OSError as exc:
        raise Refusal('Machine Chrome policies must be provisioned and verified first.') from exc


def setup_chrome_policy(hosts, *, registry=None):
    """Write exact machine policies. Run manually from elevated PowerShell/console."""
    if registry is None:
        import winreg as registry
    base = r'SOFTWARE\Policies\Google\Chrome'
    scalar = {'DownloadRestrictions': 3, 'PasswordManagerEnabled': 0,
              'BrowserSignin': 0, 'SyncDisabled': 1, 'IncognitoModeAvailability': 1,
              'DeveloperToolsAvailability': 2}
    lists = {'ExtensionInstallBlocklist': ['*'], 'URLBlocklist': ['*'],
             'URLAllowlist': ['https://' + host for host in hosts]}
    try:
        with registry.CreateKeyEx(registry.HKEY_LOCAL_MACHINE, base, 0,
                                  registry.KEY_SET_VALUE | registry.KEY_WOW64_64KEY) as key:
            for name, value in scalar.items():
                registry.SetValueEx(key, name, 0, registry.REG_DWORD, value)
        for name, values in lists.items():
            with registry.CreateKeyEx(registry.HKEY_LOCAL_MACHINE, base + '\\' + name, 0,
                                      registry.KEY_SET_VALUE | registry.KEY_WOW64_64KEY) as key:
                for index, value in enumerate(values):
                    registry.SetValueEx(key, str(index+1), 0, registry.REG_SZ, value)
        check_chrome_policies(hosts, registry=registry)
    except OSError as exc:
        raise Refusal('Chrome policy setup requires Windows administrator access.') from exc
