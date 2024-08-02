from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Signal

from pupil_labs.realtime_api.simple import Device

from pupil_labs.neon_monitor.widgets import MonitorWindow
from pupil_labs.neon_monitor.companion import CompanionSearcher, Companion


class MonitorApp(QApplication):
    device_connected = Signal(object)
    device_disconnected = Signal()

    def __init__(self):
        super().__init__()
        self.setApplicationDisplayName("Neon Monitor")
        self.setQuitOnLastWindowClosed(False)

        self.searcher = CompanionSearcher()

        self.device = None

        self.main_window = MonitorWindow()
        self.main_window.closed.connect(self.on_window_closed)

    def exec(self):
        self.main_window.show()
        super().exec()

    def on_window_closed(self):
        self.disconnect_device()
        self.searcher.shutdown()
        self.quit()

    def connect_to_device(self, ip, port):
        self.device = Companion(Device(ip, port))
        self.device_connected.emit(self.device)

    def disconnect_device(self):
        if self.device is not None:
            self.device.close()
            self.device_disconnected.emit()
            self.device = None


def main():
    app = MonitorApp()
    app.exec()


if __name__ == "__main__":
    main()
