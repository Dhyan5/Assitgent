# JARVIS threat model and residual risks

Assets are personal files, credentials, PC state, microphone privacy, resource budgets and audit history. Threat inputs include misheard or malicious voice/text, model output, future file/web data, tampered configuration/model files, compromised native dependencies and other local processes.

The runtime trust boundary is user input -> deterministic routing or constrained local model -> central policy -> registered tool. Stage C has no dispatcher. File read output is spoken directly, never used as a new request or fed into tool routing. The origin label is a trusted application convention, not authentication of arbitrary Python callers.

Production is presently blocked by missing deployment prerequisites and the unresolved outbound-test exception. Text tests can run; no claim is made that all requested protections or performance targets have passed.

## Implemented controls

* Every registered tool call has a closed schema, risk tier and central policy check. Handlers validate again. No generic shell, arbitrary command, deletion, rename, overwrite or installation tool exists. Whitelisted process launch is fixed-argv and explicitly shell=False.
* Note files are flat-folder text names; exclusive creation refuses overwrite. Windows handle checks reject reparse points/hardlinks and compare the final path. The approved directory is held without delete sharing while the operation runs. These Win32 APIs still require live race/ACL tests.
* Tier 1 actions require a fresh yes; cancellations and expiry are one-shot. Voice confirmation timing starts after talkback. Chat JSON is never dispatched.
* Capture and playback use bounded RAM buffers. The microphone is intentionally opened, visibly indicated, and closed during speech. The event loop uses deadlines and a five-second idle health cadence. Native-device behavior is not yet certified.
* Audit values/results are redacted, writes are serialized inside the process, flushed and fsynced, and records are hash chained. Capacity exhaustion refuses further actions; no log auto-deletion exists.
* Local model bytes require publisher SHA256 matches and size limits. Grammar output is independently validated. Context/token limits and a single-thread Piper session constrain inference. No network model-name loaders are used.
* Browser controls are optional and disabled. The implementation checks policies, direct URLs, process ownership and foreground PID, and places launched Chrome in an owned Job. The timeout closes that job. Retained profiles have a pre-operation 64 MB allowance; no cleanup deletes them.

## What this does not protect against

* Administrator/root compromise, malicious code in this process/account, a modified source tree/config, compromised Python/native packages, kernel bugs or physical access. OS and dependency provenance are essential; keyword filters and model prompts are not a security boundary.
* Hallucinations or semantic routing errors. A JSON grammar enforces shape, not truth or correct interpretation. Low-confidence rejection reduces mistakes but is not speaker authentication.
* A local attacker replacing or recomputing an entire audit chain, or truncating its tail between sessions. There is no signed external anchor. A process crash during a write can leave a partial record and startup must refuse the corrupt log.
* Fully race-free browser typing. Foreground PID is checked before each character, but focus may change between check and injection. A page may react or submit on text events without Enter. Input control remains disabled until accepted; even accepted domains can contain login, payment or other sensitive pages.
* Fully isolated Chrome behavior from a user-data-dir alone. Enterprise policies are machine-wide, browser internals can use network, process reuse/Job assignment must be tested, and browser profile writes can exceed an allowance between checks. Online mode is not deployable yet.
* Arbitrary in-flight native calls outliving cancellation. A tool timeout locks future actions and requests capture shutdown; it cannot undo or safely terminate a tool already executing. PortAudio/Whisper/Piper/llama.cpp behavior needs physical testing. Simulated sub-300-ms cancellation is not a hardware guarantee.
* A complete hardware interlock. Thermal sensors may be absent on Windows; no reading is treated as unknown, not proof of safe temperature. The Job memory cap is implemented but untested. CPU-thread caps do not establish battery drain or thermal limits. STANDARD/CHAT+ battery profile switching is not finished; heavy work instead refuses on battery outside ULTRA-LITE.
* The requested installation/idle budgets until measured with all native libraries and models. Unloading Python model objects may retain allocator/native-library pages. The requested 60 MB idle memory limit may not be attainable in one Python process with this stack.
* OneDrive or other system services syncing project/log/model files independently. A private, unsynced deployment folder and separate account are required. This development workspace is under OneDrive; the code cannot guarantee privacy against that external service.
* Audio reaching OS paging, crash dumps or device-driver buffers. The application never intentionally writes audio, but RAM-only application buffers alone cannot guarantee that the OS never pages them. OS isolation/dump policy must be reviewed separately.
* Secret detection by patterns. The sensitive-text filter is additional defense, not an exhaustive classifier. Long-term memory, web-content ingestion, speaker verification and wake word are not implemented.
* Outbound blocking established merely by application intent or a failed connection. Firewall policy inspection is implemented, but the required active test awaits explicit approval and implementation. Production remains refused.

## Unresolved specification conflicts

No-delete takes precedence over 30-day log auto-expiry, voice erasure and profile cleanup. No runtime internet takes precedence over the requested outbound probe until a narrow exception is explicitly approved. No registry changes takes precedence over Chrome policy setup until its separate exception is explicitly approved. The 700 MB total remains a hard limit even though current publisher model files alone consume approximately 586 MB.

No services, scheduled tasks or autostart entries are created. Optional capabilities remain off rather than weakening these requirements to report artificial completion.
