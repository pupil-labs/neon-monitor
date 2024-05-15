from PySide6.QtCore import Qt, QRect, QSize, QPoint, Signal

from PySide6.QtWidgets import (
    QApplication, QWidget,
    QLabel, QComboBox, QPushButton, QToolButton,
    QHBoxLayout,
    QGraphicsDropShadowEffect,
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
            resultSize.setWidth(self.width() - self.margin*2)
            resultSize.setHeight(source_size.height() * (resultSize.width() / source_size.width()))

        else:
            resultSize.setHeight(self.height() - self.margin*2)
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
        app.companion.subscribe('matched_scene_and_gaze', self.on_scene_and_gaze_ready)
        app.companion_worker.device_connected.connect(self.on_device_connected)
        app.companion_worker.device_disconnected.connect(self.update)

        self.status_label = QLabel("Please connect to a device.", self)
        self.text_effect = QGraphicsDropShadowEffect()
        self.text_effect.setOffset(1)
        self.status_label.setGraphicsEffect(self.text_effect)

        self.pen = None
        self.scale = 1.0
        self.offset = QPoint(0, 0)

    def resizeEvent(self, event):
        self.status_label.move(10, self.height() - 25)
        self.status_label.resize(self.width(), self.status_label.height())

    def on_device_connected(self, device):
        self.status_label.setText(f"Waiting for stream from {device['address']}:{device['port']}...")

    def on_scene_and_gaze_ready(self, scene_and_gaze):
        self.gaze = scene_and_gaze.gaze
        self.image = qimage_from_frame(scene_and_gaze.frame.bgr_pixels)
        self.status_label.setText(f"Scene timestamp: {scene_and_gaze.frame.timestamp_unix_seconds}")

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

        self.layout().addWidget(QLabel("Device:"))
        self.layout().addWidget(self.device_combo, 1)
        self.layout().addWidget(self.connect_button)

        app = QApplication.instance()
        app.companion_worker.device_connected.connect(self.on_device_connected)
        app.companion_worker.device_disconnected.connect(self.on_device_disconnected)

        self.device_combo.initiate_refresh()


    def on_device_connected(self):
        self.connect_button.setText("Disconnect")
        self.device_combo.setEnabled(False)

    def on_device_disconnected(self):
        self.connect_button.setText("Connect")
        self.device_combo.setEnabled(True)


    def toggle_connection(self):
        app = QApplication.instance()
        if app.companion_device is None:
            device_info = self.device_combo.selected_device
            app.companion.connect_to_device(device_info["address"], device_info["port"])

        else:
            app.companion.disconnect_device()


class DeviceCombo(QWidget):
    searching_changed = Signal(bool)

    def __init__(self):
        super().__init__()

        self.setLayout(QHBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)

        self.combo = QComboBox()
        self.combo.addItem("Manual Entry")

        self.refresh_button = QToolButton()
        self.refresh_button.setText("🔍")
        self.refresh_button.clicked.connect(self.initiate_refresh)

        self.layout().addWidget(self.combo)
        self.layout().addWidget(self.refresh_button)

        self.combo.currentIndexChanged.connect(self.on_index_changed)

        QApplication.instance().companion_worker.found_devices.connect(self.on_devices_found)


    def initiate_refresh(self):
        self.setEnabled(False)
        self.searching_changed.emit(True)
        QApplication.instance().companion.search()
        self.combo.setItemText(self.combo.currentIndex(), "Searching...")


    def on_devices_found(self, devices):
        self.combo.clear()

        self.combo.addItem("Manual Entry")
        for device in devices:
            self.combo.addItem(f'{device["phone_name"]} - {device["address"]}:{device["port"]}', device)

        self.combo.setCurrentIndex(self.combo.count()-1)

        self.setEnabled(True)
        self.searching_changed.emit(False)


    def on_index_changed(self, index):
        selected = self.combo.currentData()

        self.combo.setEditable(selected is None)
        if self.combo.isEditable():
            self.combo.setItemText(0, "")

        else:
            self.combo.setItemText(0, "Manual Entry")

    @property
    def selected_device(self):
        if not self.isEnabled():
            return None

        if self.combo.currentData() is not None:
            return self.combo.currentData()
        else:
            info = self.combo.currentText().split(":")
            ip = info[0]
            if len(info) > 1:
                port = int(info[1])
            else:
                port = 8080

            return {
                "address": ip,
                "port": port
            }
