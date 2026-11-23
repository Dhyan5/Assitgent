"""Visible mic state is mandatory for voice mode."""
from threading import Thread, Event
from safety import Refusal


class Tray:
    def __init__(self, quit_callback):
        import pystray
        self.pystray = pystray
        self.icon = pystray.Icon('JARVIS', self._image('idle'), 'JARVIS: OFFLINE / idle',
                                 menu=pystray.Menu(pystray.MenuItem('Exit JARVIS', quit_callback)))
        ready = Event()
        def show(icon):
            icon.visible = True
            ready.set()
        self.thread = Thread(target=self.icon.run, kwargs={'setup': show}, name='jarvis-tray', daemon=True)
        self.thread.start()
        if not ready.wait(5):
            self.icon.stop()
            raise Refusal('Tray did not become visible; microphone remains closed.')

    @staticmethod
    def _image(state):
        from PIL import Image, ImageDraw
        image = Image.new('RGB', (32, 32), '#151922')
        color = {'listening': '#f52236', 'thinking': '#ffbb33', 'speaking': '#55aaff',
                 'ONLINE-RESTRICTED': '#ff8800', 'idle': '#40bb80'}.get(state, '#999999')
        ImageDraw.Draw(image).ellipse((5, 5, 27, 27), fill=color)
        return image

    def state(self, state, mode='OFFLINE'):
        self.icon.icon = self._image(state)
        self.icon.title = f'JARVIS: {mode} / {state}'

    def close(self):
        self.icon.stop()
