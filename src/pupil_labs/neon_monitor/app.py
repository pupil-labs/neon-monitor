from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout
from PySide6.QtCore import QThread, Signal

from pupil_labs.neon_monitor.widgets import GazeOnSceneView, CompanionLineForm
from pupil_labs.neon_monitor.companion_worker import CompanionWorker, CompanionInterface


class MonitorWindow(QWidget):
    closed = Signal()

    def __init__(self):
        super().__init__()

        self.setMinimumSize(400, 400)
        self.setLayout(QVBoxLayout())

        self.companion_form = CompanionLineForm()
        self.scene_view = GazeOnSceneView()

        self.layout().addWidget(self.companion_form)
        self.layout().addWidget(self.scene_view, 1)

    def closeEvent(self, event):
        super().closeEvent(event)
        self.closed.emit()


class MonitorApp(QApplication):
    shutting_down = Signal()

    def __init__(self):
        super().__init__()
        self.setApplicationDisplayName("Neon Monitor")
        self.setQuitOnLastWindowClosed(False)

        self.companion_worker = CompanionWorker()
        self.companion_thread = QThread()
        self.companion_worker.moveToThread(self.companion_thread)
        self.companion_worker.device_connected.connect(self.on_device_connected)
        self.companion_worker.device_disconnected.connect(self.on_device_disconnected)
        self.shutting_down.connect(self.companion_worker.shutdown)
        self.companion = CompanionInterface(self.companion_worker)

        self.companion_device = None

        self.main_window = MonitorWindow()
        self.main_window.closed.connect(self.on_window_closed)

    def exec(self):
        self.companion_thread.start()
        self.main_window.show()
        super().exec()

    def on_device_connected(self, device):
        self.companion_device = device

    def on_device_disconnected(self):
        self.companion_device = None

    def on_window_closed(self):
        self.shutting_down.emit()
        self.companion_thread.quit()
        self.companion_thread.wait()
        self.quit()


def main():
    app = MonitorApp()
    app.exec()


if __name__ == "__main__":
    main()
