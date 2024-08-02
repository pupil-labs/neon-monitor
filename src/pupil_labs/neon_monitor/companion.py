from PySide6.QtCore import QObject, Signal, QThread, QTimer
from pupil_labs.realtime_api.simple import discover_devices


class CompanionSearcher(QObject):
    found_devices = Signal(list)
    _search_sig = Signal()

    def __init__(self):
        super().__init__()

        self.worker = CompanionSearchWorker()
        self.worker_thread = QThread()
        self.worker.moveToThread(self.worker_thread)
        self._search_sig.connect(self.worker.search)
        self.worker.found_devices.connect(self.found_devices.emit)

        self.worker_thread.start()

    def search(self):
        self._search_sig.emit()

    def shutdown(self):
        self.worker_thread.quit()


class CompanionSearchWorker(QObject):
    found_devices = Signal(list)

    def search(self):
        devices = discover_devices(search_duration_seconds=3.0)
        device_metas = [self.device_to_dict(d) for d in devices]

        self.found_devices.emit(device_metas)

    def device_to_dict(self, device):
        return {
            "phone_ip": device.phone_ip,
            "phone_name": device.phone_name,
            "serial": device.module_serial or device.serial_number_scene_cam,
            "address": device.address,
            "dns_name": device.dns_name,
            "full_name": device.full_name,
            "port": device.port,
        }


class Companion(QObject):
    matched_scene_and_gaze_data_ready = Signal(object)

    def __init__(self, device):
        super().__init__()

        self.device = device
        self.refresh_timer = QTimer()
        self.refresh_timer.setInterval(1000 // 60)
        self.refresh_timer.timeout.connect(self.refresh)
        self.refresh_timer.start()

    def refresh(self):
        scene_and_gaze = self.device.receive_matched_scene_video_frame_and_gaze(0)
        if scene_and_gaze is not None:
            self.matched_scene_and_gaze_data_ready.emit(scene_and_gaze)

    def __getattr__(self, attr):
        return getattr(self.device, attr)
