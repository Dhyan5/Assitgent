from collections import deque
from schemas import checked
from safety import Refusal
import time


class Memory:
    def __init__(self, max_chars=2400):
        self.turns, self.max_chars, self.last_volume = deque(maxlen=6), max_chars, None

    def remember(self, user, answer):
        self.turns.append((user[:600], answer[:600]))
        while sum(len(a)+len(b) for a, b in self.turns) > self.max_chars:
            self.turns.popleft()

    def clear(self):
        self.turns.clear()
        self.last_volume = None

    def messages(self):
        return [dict(role=role, content=text) for turn in self.turns
                for role, text in zip(('user', 'assistant'), turn)]


class SessionTools:
    def __init__(self, memory, speak, stop, clock=time.monotonic):
        self.memory, self.speak, self.stop, self.clock = memory, speak, stop, clock
        self.timers, self.policy = [], None

    @checked('set_timer')
    def set_timer(self, args):
        if len(self.timers) >= 10:
            raise Refusal('Ten reminders are already active, sir.')
        self.timers.append((self.clock() + args['seconds'], args['label']))
        return 'Reminder set for this session, sir.'

    def tick(self):
        due = [item for item in self.timers if item[0] <= self.clock()]
        self.timers = [item for item in self.timers if item[0] > self.clock()]
        for _, label in due:
            self.speak('Reminder, sir. ' + label)

    def next_deadline(self):
        return min((item[0] for item in self.timers), default=float('inf'))

    @checked('stop_speaking')
    def stop_speaking(self, args):
        self.stop()
        return 'Speech stopped, sir.'

    @checked('forget_conversation')
    def forget_conversation(self, args):
        self.memory.clear()
        return 'Conversation forgotten, sir.'

    @checked('what_did_you_do')
    def what_did_you_do(self, args):
        return 'Recent actions: ' + ', '.join(self.policy.recent) if self.policy and self.policy.recent else 'No recent actions, sir.'
