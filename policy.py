"""The only dispatcher; fail closed, redacted auditing, bounded confirmations."""
from collections import deque
from copy import deepcopy
import time
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
from safety import Refusal
from tools.registry import REGISTRY


class Policy:
    def __init__(self, audit, *, dry_run=True, rate=20, failure_limit=5,
                 confirmation_seconds=8, clock=time.monotonic, registry=REGISTRY,
                 guard=None, mode=lambda: 'OFFLINE', deadline_seconds=5, on_timeout=lambda: None):
        self.audit, self.dry_run, self.registry = audit, dry_run, registry
        self.rate, self.failure_limit = rate, failure_limit
        self.confirmation_seconds, self.clock = confirmation_seconds, clock
        self.calls, self.failures, self.pending = deque(), 0, None
        self.guard, self.mode = guard, mode
        self.recent = deque(maxlen=6)
        self.deadline_seconds, self.on_timeout = deadline_seconds, on_timeout

    def refuse(self, message):
        self.failures += 1
        self.audit.record('refused', {}, 'refused')
        raise Refusal(message)

    def dispatch(self, call):
        return self._dispatch(call, confirmed=False)

    def _dispatch(self, call, *, confirmed):
        if self.failures >= self.failure_limit:
            raise Refusal('Safety lock engaged. Restart required, sir.')
        if not isinstance(call, dict) or set(call) != {'tool', 'args'} or not isinstance(call['tool'], str):
            return self.refuse('Invalid tool call.')
        name, args = call['tool'], call['args']
        tool = self.registry.get(name)
        if tool is None or tool.tier not in (0, 1):
            return self.refuse('That tool is unavailable, sir.')
        if getattr(tool, 'online', False) and self.mode() != 'ONLINE-RESTRICTED':
            return self.refuse('That tool requires confirmed Online mode, sir.')
        try:
            Draft202012Validator(tool.schema).validate(args)
        except ValidationError:
            return self.refuse('Invalid tool arguments.')
        now = self.clock()
        while self.calls and now - self.calls[0] >= 60:
            self.calls.popleft()
        if len(self.calls) >= self.rate:
            return self.refuse('Tool rate limit reached, sir.')
        if tool.tier == 1 and not confirmed:
            self.pending = (deepcopy(call), now + self.confirmation_seconds)
            self.audit.record(name, args, 'confirmation_requested', tool.tier)
            detail = ', '.join(f'{key}: {value}' for key, value in args.items())
            return f'Shall I perform {name}' + (f' ({detail})' if detail else '') + ', sir? Say yes or cancel within eight seconds.'
        self.calls.append(now)
        self.audit.record(name, args, 'dry_run' if self.dry_run else 'attempt', tool.tier)
        if self.dry_run:
            return f'I would perform {name}, sir. Dry run is enabled.'
        try:
            if self.guard:
                self.guard(name)
            from watchdog import Deadline
            with Deadline(self.deadline_seconds, self._timeout) as deadline:
                result = tool.handler(deepcopy(args))
            if deadline.expired:
                raise Refusal('Tool deadline exceeded; safety lock engaged, sir.')
        except Exception as exc:
            self.failures += 1
            self.audit.record(name, args, 'error', tool.tier)
            raise Refusal('The tool failed safely, sir.') from exc
        self.audit.record(name, args, 'ok', tool.tier)
        self.recent.append(name)
        return result

    def _timeout(self):
        self.failures = self.failure_limit
        self.on_timeout()

    def expire_confirmation(self):
        if self.pending and self.clock() >= self.pending[1]:
            self.pending = None
            self.audit.record('confirmation', {}, 'expired')
            return True
        return False

    def confirm(self, answer):
        pending, self.pending = self.pending, None
        if not pending or self.clock() >= pending[1] or answer.strip().lower().strip('.!?') != 'yes':
            return 'Cancelled, sir.'
        return self._dispatch(pending[0], confirmed=True)
