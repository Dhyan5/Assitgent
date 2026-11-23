"""Read-only OS backstop checks; never silently repair permissions or firewall."""
import os
from pathlib import Path
import socket
import sys
from safety import Refusal, no_links, verify_model
from health import PROFILES


class InstanceLock:
    def __init__(self, path):
        self.path, self.file = no_links(path), None

    def acquire(self):
        import msvcrt
        if not self.path.parent.is_dir():
            raise Refusal('The private log directory is missing; complete the limited-account setup first.')
        self.file = self.path.open('a+b')
        if self.path.stat().st_size == 0:
            self.file.write(b'0')
            self.file.flush()
        self.file.seek(0)
        try:
            msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            self.file.close()
            self.file = None
            raise Refusal('Another JARVIS instance is running, sir.') from exc

    def close(self):
        if self.file:
            self.file.close()
            self.file = None


def check_firewall(executable):
    import win32com.client
    firewall = win32com.client.Dispatch('HNetCfg.FwPolicy2')
    for profile in (1, 2, 4):
        if not firewall.FirewallEnabled(profile):
            raise Refusal('Windows Firewall must be enabled on every profile.')
    expected = os.path.normcase(os.path.abspath(executable))
    covered = 0
    for rule in firewall.Rules:
        if (rule.Enabled and rule.Direction == 2 and rule.Action == 0
            and os.path.normcase(os.path.abspath(rule.ApplicationName or '.')) == expected
            and rule.Protocol == 256 and rule.LocalAddresses == '*' and rule.RemoteAddresses == '*'
            and rule.InterfaceTypes == 'All' and not rule.ServiceName):
            covered |= rule.Profiles
    if covered & 7 != 7:
        raise Refusal('An unrestricted outbound block for this exact Python executable is required.')


def outbound_self_test(connect=socket.create_connection, *, timeout=2.0):
    """One fixed, short TCP handshake; sends no application data and always closes."""
    try:
        connection = connect(('1.1.1.1', 443), timeout=timeout)
    except OSError:
        return
    try:
        raise Refusal('Outbound traffic is reachable; Offline startup refused, sir.')
    finally:
        connection.close()


def check_account(config):
    import getpass
    import ctypes
    if getpass.getuser().casefold() != config['security']['account'].casefold():
        raise Refusal('Run JARVIS under its dedicated limited Windows account.')
    if ctypes.windll.shell32.IsUserAnAdmin():
        raise Refusal('JARVIS must never run as administrator.')
    home = Path(config['security']['protected_home'])
    if not home.is_absolute() or home == Path.home():
        raise Refusal('A separate protected personal home must be configured.')
    try:
        with os.scandir(home) as entries:
            next(entries, None)
    except PermissionError:
        return
    except OSError as exc:
        raise Refusal('Cannot establish the personal-home access boundary.') from exc
    raise Refusal('The assistant account still has access to the personal home.')


def check_private_folder(path):
    import win32security as s
    import win32api
    import win32con
    path = no_links(path)
    if not path.is_dir():
        raise Refusal('Required private directory is missing.')
    token = s.OpenProcessToken(win32api.GetCurrentProcess(), win32con.TOKEN_QUERY)
    try:
        user = s.GetTokenInformation(token, s.TokenUser)[0]
    finally:
        token.Close()
    allowed = {s.ConvertSidToStringSid(user), 'S-1-5-18', 'S-1-5-32-544'}
    descriptor = s.GetFileSecurity(str(path), s.DACL_SECURITY_INFORMATION)
    acl = descriptor.GetSecurityDescriptorDacl()
    if acl is None:
        raise Refusal('Private folder has an unrestricted ACL.')
    for index in range(acl.GetAceCount()):
        ace = acl.GetAce(index)
        if ace[0][0] == s.ACCESS_ALLOWED_ACE_TYPE and s.ConvertSidToStringSid(ace[2]) not in allowed:
            raise Refusal('Private folder grants access to another account or group.')


def check_deployment_root(root):
    """The assistant must not execute source from a cloud-synced or user-writable tree."""
    root = no_links(root)
    if not root.is_dir() or any(part.casefold() == 'onedrive' for part in root.parts):
        raise Refusal('Deploy JARVIS in a local, unsynced directory outside OneDrive.')
    import win32security as s
    import win32api
    import win32con
    token = s.OpenProcessToken(win32api.GetCurrentProcess(), win32con.TOKEN_QUERY)
    try:
        user = s.GetTokenInformation(token, s.TokenUser)[0]
    finally:
        token.Close()
    user_sid = s.ConvertSidToStringSid(user)
    descriptor = s.GetFileSecurity(str(root), s.DACL_SECURITY_INFORMATION)
    acl = descriptor.GetSecurityDescriptorDacl()
    if acl is None:
        raise Refusal('Application directory has an unrestricted ACL.')
    write_mask = (win32con.FILE_GENERIC_WRITE | win32con.FILE_WRITE_DATA | win32con.FILE_APPEND_DATA |
                  win32con.FILE_WRITE_ATTRIBUTES | win32con.FILE_WRITE_EA | win32con.WRITE_DAC |
                  win32con.WRITE_OWNER | win32con.DELETE)
    for index in range(acl.GetAceCount()):
        ace = acl.GetAce(index)
        if ace[0][0] == s.ACCESS_ALLOWED_ACE_TYPE and s.ConvertSidToStringSid(ace[2]) == user_sid and ace[1] & write_mask:
            raise Refusal('Assistant account must have read-and-execute only on the application directory.')


def check_models(config):
    for key in ('model', 'stt'):
        item = config[key]
        verify_model(item['path'], item['sha256'], item['max_bytes'])
    if config['tts']['backend'] == 'piper':
        item = config['tts']
        verify_model(item['path'], item['sha256'], item['max_bytes'])
        verify_model(item['config_path'], item['config_sha256'], 100000)
    elif config['tts']['backend'] != 'system':
        raise Refusal('Unknown speech backend.')


def self_check(config, root):
    if os.name != 'nt':
        raise Refusal('This build currently supports Windows only.')
    if sys.prefix == sys.base_prefix:
        raise Refusal('Use the dedicated, hash-locked .venv.')
    if not (root / 'requirements.txt').is_file():
        raise Refusal('The generated hashed requirements lock is missing.')
    check_account(config)
    check_deployment_root(root)
    check_private_folder(Path(config['approved_folder']).expanduser())
    check_private_folder(Path(config['log_dir']).expanduser())
    check_firewall(sys.executable)
    check_models(config)
    from tools.system import approved_executable
    for name in config['apps']:
        approved_executable(name, config['apps'])
    total = sum(path.stat().st_size for path in root.rglob('*') if path.is_file()
                and '.test-artifacts' not in path.parts)
    if total >= PROFILES[config['profile']][0]:
        raise Refusal('The installation exceeds the selected disk budget.')
    import psutil
    cores = psutil.cpu_count(logical=False)
    if cores is None or cores < 4 or psutil.virtual_memory().total < 4_000_000_000:
        raise Refusal('Minimum CPU or RAM requirements are not verified.')
    for key in ('model', 'stt'):
        config[key]['threads'] = min(config[key].get('threads', 1), max(1, cores-1))
    psutil.Process().nice(psutil.IDLE_PRIORITY_CLASS)
    import sounddevice as sd
    sd.check_input_settings(channels=1, dtype='int16', samplerate=16000)
    sd.check_output_settings(channels=1, dtype='int16', samplerate=16000)
    if not config['security'].get('network_probe_exception', False):
        raise Refusal('The approved fixed outbound self-test must be enabled in configuration.')
    outbound_self_test()
