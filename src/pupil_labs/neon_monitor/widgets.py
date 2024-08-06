from PySide6.QtCore import (
    Qt, QRect, QSize, QPoint, Signal,
    QTimer,
)

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QComboBox, QPushButton,
    QVBoxLayout, QHBoxLayout, QGridLayout,
    QDockWidget, QScrollArea,
    QLineEdit,
)

from PySide6.QtGui import (
    QPainter, QImage, QPixmap,
)


def qimage_from_frame(frame):
    if frame is None:
        return QImage()

    if len(frame.shape) == 2:
        height, width = frame.shape
        channel = 1
        image_format = QImage.Format_Grayscale8
    else:
        height, width, channel = frame.shape
        image_format = QImage.Format_BGR888

    bytes_per_line = channel * width

    return QImage(frame.data, width, height, bytes_per_line, image_format)


class MonitorWindow(QMainWindow):
    closed = Signal()

    def __init__(self):
        super().__init__()

        self.setMinimumSize(400, 400)
        self.resize(1200, 800)
        self.setLayout(QVBoxLayout())

        self.controls_widget = ControlsWidget()
        self.controls_widget.setDisabled(True)

        self.make_dock(CompanionLineForm(), "Device", Qt.DockWidgetArea.TopDockWidgetArea)
        self.make_dock(self.controls_widget, "Controls", Qt.DockWidgetArea.RightDockWidgetArea)

        self.scene_view = GazeOnSceneView()
        self.setCentralWidget(self.scene_view)
        self.statusBar().showMessage("Searching for devices...")

        self.recording_check_timer = QTimer()
        self.recording_check_timer.setInterval(1000)
        self.recording_check_timer.timeout.connect(self.update_recording_status)
        self.recording_check_timer.start()

        app = QApplication.instance()
        app.device_connected.connect(self.on_device_connected)
        app.device_disconnected.connect(self.on_device_disconnected)
        app.searcher.found_devices.connect(self.on_devices_found)

    def update_recording_status(self):
        app = QApplication.instance()
        if app.device is None:
            return

        recording = app.device._status.recording
        is_recording = recording is not None and recording.action == "START"
        self.controls_widget.set_recording_state(is_recording)

    def on_devices_found(self, devices):
        if len(devices) == 0:
            self.statusBar().showMessage("No devices discovered. Please enter address manually.")
        else:
            self.statusBar().showMessage(f"Discovered {len(devices)} device(s)")

    def on_device_connected(self, device):
        self.statusBar().showMessage(f"Waiting for stream from {device.address}:{device.port}...")
        device.matched_scene_and_gaze_data_ready.connect(self.on_scene_and_gaze_ready)
        self.controls_widget.setDisabled(False)

    def on_device_disconnected(self):
        self.statusBar().showMessage("Disconnected.")
        self.controls_widget.setDisabled(True)

    def on_scene_and_gaze_ready(self, scene_and_gaze):
        self.statusBar().showMessage(f"Scene timestamp: {scene_and_gaze.frame.timestamp_unix_seconds}")

    def closeEvent(self, event):
        super().closeEvent(event)
        self.closed.emit()

    def make_dock(self, widget, name, dock_area=None):
        dock = DockWidget(self, widget, name)

        if dock_area is None or dock_area == Qt.DockWidgetArea.NoDockWidgetArea:
            dock.setFloating(True)
            dock.show()
        else:
            self.addDockWidget(dock_area, dock)

        return dock

    def keyPressEvent(self, event):
        if event.text() >= "0" and event.text() <= "9":
            print(event)
            app = QApplication.instance()
            app.send_event(int(event.text()))


class DockWidget(QDockWidget):
    def __init__(self, parent, widget, name):
        super().__init__(name, parent)

        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setContentsMargins(0, 0, 0, 0)
        self.setWidget(widget)

        features = QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable
        self.setFeatures(features)


class ScaledImageView(QWidget):
    def __init__(self):
        super().__init__()

        self._image = None
        self.render_rect = None
        self.margin = 0
        self.setMinimumSize(32, 32)
        self.last_image_size = None

    def resizeEvent(self, event):
        self.update_rect()

    def update_rect(self):
        if self._image is None:
            return

        self.render_rect = self.fit_rect(self._image.size())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(0, 0, self.width(), self.height(), self.palette().color(self.backgroundRole()))

        if self._image is None or self.render_rect is None:
            return

        if isinstance(self._image, QImage):
            painter.drawImage(self.render_rect, self._image)

        elif isinstance(self._image, QPixmap):
            painter.drawPixmap(self.render_rect, self._image)

    def set_image(self, image):
        self.image = image

        if self.image is None:
            return

        if self.last_image_size != self.image.size():
            self.update_rect()
            self.last_image_size = self.image.size()

        self.update()

    def fit_rect(self, source_size):
        if source_size.height() == 0:
            return QRect(0, 0, 1, 1)

        source_ratio = source_size.width() / source_size.height()
        target_ratio = self.width() / self.height()

        resultSize = QSize()

        if source_ratio > target_ratio:
            resultSize.setWidth(self.width() - self.margin * 2)
            resultSize.setHeight(source_size.height() * (resultSize.width() / source_size.width()))

        else:
            resultSize.setHeight(self.height() - self.margin * 2)
            resultSize.setWidth(source_size.width() * (resultSize.height() / source_size.height()))

        resultPos = QPoint(
            (self.width() - resultSize.width()) / 2.0,
            (self.height() - resultSize.height()) / 2.0
        )

        return QRect(resultPos, resultSize)

    @property
    def image(self):
        return self._image

    @image.setter
    def image(self, value):
        self._image = value
        self.update_rect()
        self.update()


class GazeOnSceneView(ScaledImageView):
    def __init__(self):
        super().__init__()

        app = QApplication.instance()
        app.device_connected.connect(self.on_device_connected)
        app.device_disconnected.connect(self.update)

        self.pen = None
        self.scale = 1.0
        self.offset = QPoint(0, 0)

    def on_device_connected(self, device):
        device.matched_scene_and_gaze_data_ready.connect(self.on_scene_and_gaze_ready)

    def on_scene_and_gaze_ready(self, scene_and_gaze):
        self.gaze = scene_and_gaze.gaze
        self.image = qimage_from_frame(scene_and_gaze.frame.bgr_pixels)

    def update_rect(self):
        super().update_rect()
        if self._image is None:
            return

        self.scale = self.render_rect.width() / self._image.width()
        self.offset = self.render_rect.topLeft()

    def paintEvent(self, event):
        super().paintEvent(event)

        painter = QPainter(self)

        if self._image is None:
            return

        if self.pen is None:
            self.pen = painter.pen()
            self.pen.setColor(Qt.red)
            self.pen.setWidth(5)

        painter.setPen(self.pen)

        painter.translate(self.offset)
        painter.scale(self.scale, self.scale)
        painter.drawEllipse(QPoint(self.gaze.x, self.gaze.y), 30, 30)


class CompanionLineForm(QWidget):
    def __init__(self):
        super().__init__()

        self.setLayout(QHBoxLayout())

        self.device_combo = DeviceCombo()
        self.device_combo.searching_changed.connect(lambda searching: self.setEnabled(not searching))

        self.connect_button = QPushButton("Connect")
        self.connect_button.clicked.connect(self.toggle_connection)

        self.layout().addWidget(self.device_combo, 1)
        self.layout().addWidget(self.connect_button)

        app = QApplication.instance()
        app.device_connected.connect(self.on_device_connected)
        app.device_disconnected.connect(self.on_device_disconnected)

        self.device_combo.initiate_refresh()

    def on_device_connected(self, device):
        self.connect_button.setText("Disconnect")
        self.device_combo.setEnabled(False)

    def on_device_disconnected(self):
        self.connect_button.setText("Connect")
        self.device_combo.setEnabled(True)

    def toggle_connection(self):
        app = QApplication.instance()
        if app.device is None:
            device_info = self.device_combo.selected_device
            app.connect_to_device(device_info["address"], device_info["port"])

        else:
            app.disconnect_device()


class DeviceCombo(QComboBox):
    searching_changed = Signal(bool)

    def __init__(self):
        super().__init__()

        self.addItem("Manual Entry")

        self.currentIndexChanged.connect(self.on_index_changed)
        QApplication.instance().searcher.found_devices.connect(self.on_devices_found)

    def initiate_refresh(self):
        self.setEnabled(False)
        self.searching_changed.emit(True)
        QApplication.instance().searcher.search()
        self.setItemText(self.currentIndex(), "Searching...")

    def on_devices_found(self, devices):
        self.clear()
        self.addItem("🗘 Refresh List")
        self.addItem("Manual Entry")
        self.insertSeparator(2)

        for device in devices:
            self.addItem(f'{device["phone_name"]} - {device["address"]}:{device["port"]}', device)

        self.setCurrentIndex(3)

        self.setEnabled(True)
        self.searching_changed.emit(False)

    def on_index_changed(self, index):
        if self.currentIndex() == 0 and self.count() > 1:
            self.initiate_refresh()
            return

        selected = self.currentData()
        self.setEditable(selected is None)
        if self.isEditable():
            self.setItemText(1, "")

        else:
            self.setItemText(1, "Manual Entry")

    @property
    def selected_device(self):
        if not self.isEnabled():
            return None

        if self.currentData() is not None:
            return self.currentData()
        else:
            info = self.currentText().split(":")
            ip = info[0]
            if len(info) > 1:
                port = int(info[1])
            else:
                port = 8080

            return {
                "address": ip,
                "port": port
            }


class ControlsWidget(QWidget):
    def __init__(self):
        super().__init__()

        self.setLayout(QVBoxLayout())

        self.record_button = QPushButton("Record")

        self.event_list = EventListWidget()

        scroll_area = QScrollArea()
        scroll_area.setStyleSheet("QScrollArea { border: none; }")
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setWidget(self.event_list)
        scroll_area.setWidgetResizable(True)

        self.layout().addWidget(self.record_button)
        self.layout().addWidget(scroll_area)
        self.layout().addWidget(QWidget(), 1)

        self.record_button.clicked.connect(self.on_record_clicked)
        self._is_recording = False

    def set_recording_state(self, is_recording):
        self._is_recording = is_recording
        if not self._is_recording:
            self.record_button.setText("Record")
        else:
            self.record_button.setText("STOP")

    def on_record_clicked(self):
        app = QApplication.instance()
        if self._is_recording:
            app.device.recording_stop_and_save()
        else:
            app.device.recording_start()


class EventListWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setLayout(QGridLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)

        app = QApplication.instance()

        for idx in range(10):
            idx_p = (idx + 1) % 10

            button = QPushButton(f"{idx_p}")
            line_edit = QLineEdit(f"Event {idx_p}")

            self.layout().addWidget(button, idx, 0)
            self.layout().addWidget(line_edit, idx, 1)

            button.clicked.connect(lambda _, event_id=idx_p: app.send_event(event_id))
            line_edit.textChanged.connect(lambda text, event_id=idx_p, widget=line_edit: app.set_event_text(event_id, text))

            app.set_event_text(idx_p, line_edit.text())
