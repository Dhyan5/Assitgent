from safety import Refusal

PROFILES = {'ULTRA-LITE': (700_000_000, 800_000_000),
            'STANDARD': (1_600_000_000, 1_800_000_000), 'CHAT+': (3_000_000_000, 3_200_000_000)}


class Health:
    def __init__(self, config):
        self.config = config

    def battery(self):
        import psutil
        return psutil.sensors_battery()

    def on_battery(self):
        battery = self.battery()
        return battery is not None and not battery.power_plugged

    def heavy(self):
        import psutil
        battery = self.battery()
        if battery and not battery.power_plugged and self.config['profile'] != 'ULTRA-LITE':
            raise Refusal('On battery: restart with the ULTRA-LITE model configuration, sir.')
        if battery and battery.percent < 10 and not battery.power_plugged:
            raise Refusal('Battery is critical; heavy work is paused, sir.')
        temperatures = getattr(psutil, 'sensors_temperatures', lambda: {})()
        if any(item.current >= 85 for readings in temperatures.values() for item in readings):
            raise Refusal('Temperature is too high for inference, sir.')
        limit = PROFILES[self.config['profile']][1]
        if psutil.Process().memory_info().rss >= limit:
            raise Refusal('The selected profile RAM limit has been reached, sir.')
        if psutil.virtual_memory().available < 300_000_000:
            raise Refusal('Available memory is too low, sir.')

    def tool(self, name):
        if name in ('take_screenshot',):
            self.heavy()
