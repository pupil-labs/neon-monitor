from PySide6.QtCore import QObject, Signal, QTimer
from pupil_labs.realtime_api.simple import discover_devices, Device


class CompanionInterface(QObject):
    sig_set_service_enabled = Signal(str, bool)
    sig_search = Signal()
    sig_connect = Signal(str, int)
    sig_disconnect = Signal()

    def __init__(self, worker):
        super().__init__()

        self.sig_set_service_enabled.connect(worker.set_service_enabled)
        self.sig_search.connect(worker.search)
        self.sig_connect.connect(worker.connect_to_device)
        self.sig_disconnect.connect(worker.disconnect_device)

        self.service_signal_map = {
            'scene': worker.scene_frame_ready,
            'eyes': worker.eye_frame_ready,
            'gaze': worker.gaze_data_ready,
            'imu': worker.imu_data_ready,
            'matched_scene_and_gaze': worker.matched_scene_and_gaze_data_ready,
        }

        self.subscription_callbacks = {key: [] for key in self.service_signal_map}

    def subscribe(self, service, slot):
        if slot not in self.subscription_callbacks[service]:
            self.subscription_callbacks[service].append(slot)
            self.service_signal_map[service].connect(slot)

        self.sig_set_service_enabled.emit(service, True)

    def unsubscribe(self, service, slot):
        if slot in self.subscription_callbacks[service]:
            self.subscription_callbacks[service].remove(slot)
            self.service_signal_map[service].disconnect(slot)

        if len(self.subscription_callbacks[service]) == 0:
            self.sig_set_service_enabled.emit(service, False)

    def search(self):
        self.sig_search.emit()

    def connect_to_device(self, *args):
        self.sig_connect.emit(*args)

    def disconnect_device(self):
        self.sig_disconnect.emit()


class CompanionWorker(QObject):
    found_devices = Signal(list)
    device_connected = Signal(dict)
    device_disconnected = Signal()

    scene_frame_ready = Signal(object)
    eye_frame_ready = Signal(object)
    gaze_data_ready = Signal(object)
    imu_data_ready = Signal(object)
    matched_scene_and_gaze_data_ready = Signal(object)

    def __init__(self):
        super().__init__()
        self.device = None
        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(1000//120)
        self.poll_timer.timeout.connect(self.poll)

        self.service_statuses = {
            'scene': False,
            'eyes': False,
            'gaze': False,
            'imu': False,
            'matched_scene_and_gaze': False,
        }

    def search(self):
        devices = discover_devices(search_duration_seconds=3.0)
        device_metas = [self.device_to_dict(d) for d in devices]

        self.found_devices.emit(device_metas)

    def connect_to_device(self, ip, port):
        try:
            self.device = Device(ip, port)
            self.device_connected.emit(self.device_to_dict(self.device))

            if True in self.service_statuses.values():
                self.poll_timer.start()

        except Exception as exc:
            print("Connection failed!")
            print(exc)
            self.device_disconnected.emit()

    def set_service_enabled(self, service, enabled):
        self.service_statuses[service] = enabled

        if True in self.service_statuses.values() and self.device is not None:
            if not self.poll_timer.isActive():
                self.poll_timer.start()

        else:
            self.poll_timer.stop()

    def poll(self):
        if self.service_statuses['imu']:
            imu = self.device.receive_imu_datum(0)
            if imu is not None:
                self.imu_data_ready.emit(imu)

        if self.service_statuses['scene']:
            scene = self.device.receive_scene_video_frame(0)
            if scene is not None:
                self.scene_frame_ready.emit(scene)

        if self.service_statuses['gaze']:
            gaze = self.device.receive_gaze_datum(0)
            if gaze is not None:
                self.gaze_data_ready.emit(gaze)

        if self.service_statuses['matched_scene_and_gaze']:
            scene_and_gaze = self.device.receive_matched_scene_video_frame_and_gaze(0)
            if scene_and_gaze is not None:
                self.matched_scene_and_gaze_data_ready.emit(scene_and_gaze)

    def shutdown(self):
        if self.device is not None:
            self.device.close()
            self.poll_timer.stop()

    def device_to_dict(self, device):
#       calibration = None
#       try:
#           calibration = device.get_calibration()
#       except:
#           pass

        return {
            "phone_ip": device.phone_ip,
            "phone_name": device.phone_name,
            "serial": device.module_serial or device.serial_number_scene_cam,
            "address": device.address,
            "dns_name": device.dns_name,
            "full_name": device.full_name,
            "port": device.port,
#            "calibration": device.get_calibration(),
        }

    def disconnect_device(self):
        if self.device is not None:
            self.device.close()

        self.device_disconnected.emit()
