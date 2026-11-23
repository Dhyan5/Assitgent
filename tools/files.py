from datetime import datetime, timezone
from io import BytesIO
from uuid import uuid4
from schemas import checked
from safety import Refusal


class FileTools:
    def __init__(self, files):
        self.files, self.last_action = files, None

    @checked('list_folder')
    def list_folder(self, args):
        return ', '.join(self.files.names()) or 'The approved folder is empty, sir.'

    @checked('read_file')
    def read_file(self, args):
        # Direct output only. Never send file content into intent or model routing.
        return 'Untrusted note content follows. ' + self.files.read(args['name'])

    @checked('create_note')
    def create_note(self, args):
        self.files.write(args['name'], args['text'] + '\n', new=True)
        self.last_action = args['name']
        return 'The new note is ready, sir.'

    @checked('append_note')
    def append_note(self, args):
        self.files.write(args['name'], '\n' + args['text'] + '\n')
        self.last_action = args['name']
        return 'The note has been appended, sir.'

    @checked('undo_last_note_action')
    def undo_last_note_action(self, args):
        if self.last_action is None:
            raise Refusal('There is no note action to correct, sir.')
        self.files.write(self.last_action, '\nCorrection: disregard the preceding assistant note action. '
                         + datetime.now(timezone.utc).isoformat() + '\n')
        self.last_action = None
        return 'I appended a correction; the original text remains, sir.'

    @checked('take_screenshot')
    def take_screenshot(self, args):
        from PIL import ImageGrab
        image = ImageGrab.grab()
        image.thumbnail((1920, 1080))
        buffer = BytesIO()
        image.save(buffer, format='PNG')
        self.files.image('screenshot-' + uuid4().hex + '.png', buffer.getvalue())
        return 'Screenshot saved in the approved folder, sir.'
