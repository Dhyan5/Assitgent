from jsonschema import Draft202012Validator
from safety import Refusal, user_text
from tools.registry import call_schema


class Assistant:
    def __init__(self, intent, policy, llm=None, memory=None, chat_sink=None):
        self.intent, self.policy, self.llm = intent, policy, llm
        self.memory, self.chat_sink = memory, chat_sink
        self.streamed = False

    def handle(self, text, *, source='user'):
        try:
            self.streamed = False
            if self.policy.failures >= self.policy.failure_limit:
                raise Refusal('Safety lock engaged. Restart required, sir.')
            if source != 'user':
                return self.policy.refuse('External content cannot originate actions, sir.')
            try:
                text = user_text(text)
            except Refusal as exc:
                return self.policy.refuse(str(exc))
            if self.policy.pending:
                return self.policy.confirm(text)
            call = self.intent.match(text)
            if not call and text.strip().lower() in ('turn it down a bit', 'now turn it down a bit', 'turn it up a bit'):
                if self.memory is None or self.memory.last_volume is None:
                    return 'Please specify a volume percentage, sir.'
                delta = 5 if 'up' in text else -5
                call = {'tool': 'set_volume', 'args': {'level': max(0, min(100, self.memory.last_volume + delta))}}
            if call:
                return self._execute(call)
            if self.llm is None:
                return 'Local conversation is unavailable until a verified model is configured, sir.'
            call = self.llm.route(text)
            Draft202012Validator(call_schema(self.policy.registry)).validate(call)
            if call.get('route') == 'chat':
                # The return value is display-only, even if it resembles a tool call.
                if self.chat_sink and hasattr(self.llm, 'stream_chat'):
                    self.streamed = True
                    parts = []
                    for sentence in self.llm.stream_chat(text, self.memory.messages() if self.memory else []):
                        self.chat_sink(sentence)
                        parts.append(sentence)
                    answer = ' '.join(parts)
                else:
                    answer = self.llm.chat(text)
                if self.memory:
                    self.memory.remember(text, answer)
                return answer
            return self._execute(call)
        except Refusal as exc:
            self.streamed = False
            return str(exc)
        except Exception:
            self.streamed = False
            self.policy.failures += 1
            self.policy.audit.record('request', {}, 'error')
            return 'The request failed safely, sir.'

    def _execute(self, call):
        result = self.policy.dispatch(call)
        if self.memory and call['tool'] == 'set_volume' and not self.policy.dry_run:
            self.memory.last_volume = call['args']['level']
        return result
