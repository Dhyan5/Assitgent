# Windows provisioning and acceptance

These are manual operator steps, **not commands executed during development**. Production is still blocked; completing OS setup alone does not bypass unresolved application acceptance gates. Use a dedicated VM first. Do not apply machine-wide Chrome policies to your normal browsing machine without reviewing their impact.

## 1. Resolve the compatible current runtime and budget

Use current stable Python and current stable compatible package versions, with the requested CPU-only stack. Python 3.15.2 was the latest stable observed, but ONNX Runtime's published native wheels need a compatibility check; the newest stable 3.14 patch may be required. This PC currently has only Python 3.12.10. No interpreter was installed.

Before installing, calculate the expanded environment plus models against 700 MB (ULTRA-LITE). Models alone are approximately 586 MB. If the required environment cannot fit, obtain explicit approval for STANDARD or a stack/model change; do not silently exceed the cap. Native source builds may require substantially more temporary disk than the application allowance.

After choosing and manually provisioning the compatible interpreter, create one venv in a local unsynced deployment directory, for example `C:\Jarvis`:

```powershell
# Example for an already-provisioned compatible 3.14 interpreter.
cd C:\Jarvis
py -3.14 -m venv .venv
```

Provision pip-tools 7.7.0 and its dependencies from reviewed, hash-verified artifacts. Then generate both locks in that exact target environment:

```powershell
.venv\Scripts\python.exe -m piptools compile --generate-hashes --output-file requirements.txt requirements.in
.venv\Scripts\python.exe -m piptools compile --generate-hashes --output-file requirements-dev.txt requirements-dev.in
```

Review the complete resolution and every native artifact/build dependency. From a separately prepared local wheelhouse, install only the verified runtime lock:

```powershell
.venv\Scripts\python.exe -m pip install --no-index --find-links wheelhouse --require-hashes -r requirements.txt
```

The command requires a real generated `requirements.txt` and the matching local artifacts; neither is supplied as a fake placeholder. Installation is a manual build operation, never an assistant tool. Do not install the `.in` file directly as a substitute. Preserve the lock with the deployed source. Run tests using the development lock in the same project venv before final deployment and measure its complete disk footprint.

## 2. Verify local model artifacts

The expected model hashes in config.yaml came from publisher file metadata; sources are in VERSIONS.md. Obtain a trusted SHA256 for the Alan `.onnx.json` configuration and add it both to the manifest and config. The example manifest intentionally fails validation until that hash exists.

From a manually chosen provisioning environment with network access, the sole network downloader is:

```powershell
python download_models.py models.manifest.example.json --output C:\Jarvis\models
```

Do not run this before the total installation budget is established. It has no install capability, does not overwrite existing files, checks every manifest before starting, validates HTTPS hosts on redirects, caps byte counts/time, and verifies hashes. If interrupted or mismatched it retains the incomplete file; no auto-delete or rename is performed. The runtime re-verifies all model/config hashes and will not load that file. Model paths in config are local paths, not model names that could trigger a library download.

## 3. Dedicated limited account and folders

In an elevated PowerShell session in the dedicated VM, use a fresh account name that does not already exist. The following creates a standard user, not an administrator:

```powershell
$jarvisPassword = Read-Host 'Password for the dedicated JARVIS account' -AsSecureString
New-LocalUser -Name JarvisLocal -Password $jarvisPassword -Description 'Limited local JARVIS account'
Add-LocalGroupMember -SID 'S-1-5-32-545' -Member JarvisLocal
```

Sign in once to initialize its Windows profile. Put the application source/venv/models in `C:\Jarvis`, outside your personal OneDrive tree. Do not run JARVIS from `C:\Users\Dhyan`: the account's personal-home deny rule deliberately prevents that.

Create the approved folders under the assistant account profile, and grant only that account, SYSTEM and Administrators access. These exact commands assume the fresh profile is `C:\Users\JarvisLocal`:

```powershell
New-Item -ItemType Directory -Path C:\Users\JarvisLocal\AssistantFiles -Force
New-Item -ItemType Directory -Path C:\Users\JarvisLocal\AssistantFiles\logs -Force
icacls C:\Users\JarvisLocal\AssistantFiles /inheritance:r
icacls C:\Users\JarvisLocal\AssistantFiles /grant:r 'JarvisLocal:(OI)(CI)M' '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-544:(OI)(CI)F'
icacls C:\Users\JarvisLocal\AssistantFiles\logs /inheritance:r
icacls C:\Users\JarvisLocal\AssistantFiles\logs /grant:r 'JarvisLocal:(OI)(CI)M' '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-544:(OI)(CI)F'
icacls C:\Users\JarvisLocal\AssistantFiles /deny 'JarvisLocal:(OI)(CI)(DE,DC)'
icacls C:\Users\JarvisLocal\AssistantFiles\logs /deny 'JarvisLocal:(OI)(CI)(DE,DC)'
icacls C:\Users\Dhyan /deny 'JarvisLocal:(OI)(CI)F'
icacls C:\Jarvis /grant 'JarvisLocal:(OI)(CI)RX'
```

The deny ACE targets **only the dedicated account**, never your main account. No-delete applies to child objects as well as directory delete-child rights. Existing unexpected ACL grants must be reviewed; startup refuses broad access on the private folders. Startup also rejects source under OneDrive and rejects an application directory writable by the assistant account. The application folder should be maintained by the build operator and read-only to the assistant; test artifacts and production logs are separate. Keep an ACL backup before changing an established machine, or perform this in a fresh VM. These rules do not protect against administrators.

Read the official [icacls reference](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/icacls) for the exact DE/DC and inheritance semantics. Runtime file tools also reject links/reparse points and use exclusive Windows file handles; actual ACL/link-race acceptance is still required.

## 4. Outbound firewall backstop

In elevated PowerShell on the deployment machine, create program-specific all-profile outbound block rules for both venv entry points:

```powershell
New-NetFirewallRule -DisplayName 'JARVIS Python outbound deny' -Direction Outbound -Action Block -Program 'C:\Jarvis\.venv\Scripts\python.exe' -Profile Any -Enabled True
New-NetFirewallRule -DisplayName 'JARVIS Pythonw outbound deny' -Direction Outbound -Action Block -Program 'C:\Jarvis\.venv\Scripts\pythonw.exe' -Profile Any -Enabled True
Get-NetFirewallRule -DisplayName 'JARVIS Python* outbound deny' | Get-NetFirewallApplicationFilter
```

Check that Windows Firewall is already enabled on every profile. The application reads Firewall COM policy and requires an all-profile, all-protocol, unrestricted-address block for its exact executable. This check is implemented and tested with simulated COM data; it is not a live proof of packet blocking. The explicit outbound probe is intentionally not implemented until the contradiction with the no-runtime-network rule is resolved. **Production remains blocked at that gate.** Merely setting `network_probe_exception: true` does not unblock it.

See Microsoft's [New-NetFirewallRule documentation](https://learn.microsoft.com/en-us/powershell/module/netsecurity/new-netfirewallrule) for command semantics. Do not weaken these rules for package provisioning; use a separate provisioning environment. A single failed connection is not itself evidence of a complete firewall boundary.

## 5. Launcher and manual verification

Create a desktop shortcut to `C:\Jarvis\jarvis.bat`. Do not place it in Startup. Run under the dedicated account:

```powershell
runas /user:.\JarvisLocal 'C:\Jarvis\jarvis.bat debug'
```

Avoid `/savecred`: cached credentials let other programs use that account without re-entering its password. The launcher verifies required files, sets offline/no-user-site variables, and uses low priority. The application owns single-instance locking; no scheduler or service is created.

After outstanding gates have actually been implemented/resolved, manually verify all of the following:

* Startup fails on bad model hashes, writable/inappropriate account boundaries, missing devices or unblocked outbound traffic; repeat for python.exe and pythonw.exe.
* Microphone chimes and red tray state accurately track live capture; no capture occurs while idle or speaking. Hotkeys work on press and release, including a modifier released first.
* Native stop-speech and push-to-talk interruption meet 300 ms; measure rather than assume. Confirmations start their timeout only after the spoken prompt.
* Notes cannot escape the folder via symlinks, junctions, hardlinks, alternate data streams or path races; existing files cannot be overwritten.
* Measure actual 50-command latency, first spoken audio latency, inference peak RAM, complete installed disk, and five-minute idle CPU/RAM. Keep a trace across repeated model load/unload cycles.
* Exercise low battery, missing thermal sensors, long native calls, exhausted audit capacity, full disk, device removal, shutdown and restart.

## 6. Optional restricted Chrome

`browser.enabled: false` and `browser.input_control: false` remain the defaults. The machine-wide Chrome registry exception has been approved, and `browser/setup_chrome_policy.py` now applies only the explicit policy set below. Use a dedicated VM: these policies affect Chrome for all users on the machine. After reviewing the impact, run an elevated console from the project directory:

```powershell
python browser\setup_chrome_policy.py --apply
```

This writes HKLM policies and verifies their readback. It does not enable JARVIS Online mode. Verify policy status at `chrome://policy`; revert through Windows policy management only after understanding the machine-wide consequences.

The expected machine policies are DownloadRestrictions=3, PasswordManagerEnabled=0, BrowserSignin=0, SyncDisabled=1, IncognitoModeAvailability=1, DeveloperToolsAvailability=2, ExtensionInstallBlocklist=["*"], URLBlocklist=["*"], and URLAllowlist matching configured HTTPS domains. These are machine-wide policies, not isolated per-profile settings. Use a dedicated VM; a user-data-dir alone does not isolate policy effects.

The approved startup connectivity probe makes one fixed TCP connection attempt to `1.1.1.1:443` with a two-second timeout, sends no application data, and immediately closes any successful connection before refusing startup. It only checks that traffic appears blocked; the exact-executable firewall policy inspection remains required. No general network client is available to the assistant. Package/model provisioning stays in the separate manual setup process.

After approved provisioning, inspect `chrome://policy` and test downloads, extension installation, file URLs, redirects, login pages and off-allowlist navigation manually. An allowlisted site is not automatically safe: allowed pages may have login or purchase flows. Input control remains off; PID checks and sensitive-text rules do not eliminate focus races or page-side auto-submit behavior. The optional HTTPS text gateway and page summarization are not implemented.

The browser is intended to run in a newly created dedicated profile and owned Windows Job; timeout/kill closes that job, including its descendants. Profile directories are retained because deletion is forbidden, so their cumulative disk use must be measured. Browser policy/Job behavior is not yet live-tested.

## 7. Optional features

Wake word, speaker verification, encrypted long-term memory, CHAT+ tuning and VM packaging are not implemented. They remain explicitly disabled instead of adding unmeasured models, background listeners or unverified identity guarantees. A sandbox/VM is a recommended test environment, not an included or required Docker service.
