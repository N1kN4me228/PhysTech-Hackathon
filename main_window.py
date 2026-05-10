from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QIcon, QMovie
from PyQt6.QtWidgets import (
    QApplication, QDialog, QLabel, QMainWindow, QMenu, QSizePolicy, QSystemTrayIcon, QVBoxLayout, QWidget
)
from utils import resource_path
from config import APP_ICON
import numpy
import pyqtgraph
import serial
import time


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('DobryTeam')
        self.setWindowIcon(QIcon(APP_ICON))

        layout = QVBoxLayout()

        title_s = 'QLabel { border-image: url(URL); }'
        title_s = title_s.replace('URL', resource_path('images/Толчки-в-реальном-времени.png').replace('\\', '/'))
        self.title = QLabel()
        self.title.setFixedSize(700, 70)
        self.title.setStyleSheet(title_s)
        layout.addWidget(self.title, stretch=1, alignment=Qt.AlignmentFlag.AlignCenter)

        self.graphWidget = pyqtgraph.PlotWidget()
        self.graphWidget.setBackground('w')
        self.graphWidget.showGrid(x=True, y=True)
        layout.addWidget(self.graphWidget, stretch=7)

        self.max_points = 200  # Сколько точек одновременно отображать на экране
        self.y_data = numpy.zeros(self.max_points)  # Создаем массив из нулей
        self.x_data = numpy.arange(self.max_points)  # Создаем массив [0, 1, 2, ..., 199]
        self.data_line = self.graphWidget.plot(self.x_data, self.y_data, pen=pyqtgraph.mkPen('r', width=2))

        self.ser = None

        self.timer = QTimer()
        self.timer.setInterval(50)
        # noinspection PyUnresolvedReferences
        self.timer.timeout.connect(self.update_plot_data)
        self.timer.start()

        self.signal = QLabel()
        self.signal.setFixedSize(700, 100)
        self.signal.setProperty('earthquake', 'yes')

        icon = QIcon(resource_path('images/Логотип-Гора.ico'))
        self.tray_icon = QSystemTrayIcon(icon, self)

        tray_menu = QMenu()
        show_action = QAction("Развернуть", self)
        quit_action = QAction("Выход", self)

        # noinspection PyUnresolvedReferences
        show_action.triggered.connect(self.show)
        # noinspection PyUnresolvedReferences
        quit_action.triggered.connect(QApplication.instance().quit)

        tray_menu.addAction(show_action)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()

        # noinspection PyUnresolvedReferences
        self.tray_icon.activated.connect(self.on_tray_icon_activated)

        layout.addWidget(self.signal, stretch=1, alignment=Qt.AlignmentFlag.AlignCenter)

        self.info_label = QLabel()
        self.info_label.setProperty('instance', 'connecting')
        self.info_label.setFixedSize(700, 100)

        self.status_label = QLabel()
        self.status_label.setProperty('instance', 'off')
        self.status_label.setFixedSize(700, 100)

        self.info_label.setObjectName("infoLabel")
        self.status_label.setObjectName("statusLabel")
        self.signal.setObjectName("signalLabel")

        self.info_label.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed
        )
        self.status_label.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed
        )

        full_stylesheet = ''

        with open(resource_path('style/app.qss'), 'r', encoding='utf-8') as f:
            info_s = f.read()
            info_s = info_s.replace('YES', resource_path('images/Землетрясения-нет.png').replace('\\', '/'))
            info_s = info_s.replace('NO', resource_path('images/Зафиксированны-точки.png').replace('\\', '/'))
            full_stylesheet += info_s

        with open(resource_path('style/info_label.qss'), 'r', encoding='utf-8') as f:
            info_s = f.read()
            info_s = info_s.replace('CONNECTING', resource_path('images/Подключение.png').replace('\\', '/'))
            info_s = info_s.replace('CONNECTED', resource_path('images/Связь-установлена.png').replace('\\', '/'))
            full_stylesheet += info_s

        with open(resource_path('style/status_label.qss'), 'r', encoding='utf-8') as f:
            status_s = f.read()
            status_s = status_s.replace('PATH_TO_IMAGE', resource_path('images/Ошибка-порта.png').replace('\\', '/'))
            full_stylesheet += status_s

        self.setStyleSheet(full_stylesheet)

        layout.addWidget(self.info_label, stretch=0, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label, stretch=0, alignment=Qt.AlignmentFlag.AlignCenter)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        # Принудительно обновляем стили при запуске, чтобы подхватились картинки
        self.refresh_style(self.info_label)
        self.refresh_style(self.status_label)

        self.centralWidget().updateGeometry()

    def update_plot_data(self):
        # 1. Если порта нет - создаем
        if self.ser is None:
            try:
                self.ser = serial.Serial('COM5', 115200, timeout=0.01, dsrdtr=False)
                self.ser.dtr = True
                self.info_label.setProperty('instance', 'connecting')
                self.status_label.setProperty('instance', 'off')
                self.refresh_style(self.info_label)
                self.refresh_style(self.status_label)
                return
            except Exception:
                self.status_label.setProperty('instance', 'on')
                self.refresh_style(self.status_label)
                return

        # 2. Если порт закрыт - уходим
        if not self.ser.is_open:
            return

        # 3. Читаем данные
        try:
            if self.ser.in_waiting > 0:
                last_valid_acceleration = None
                last_status = '0'

                while self.ser.in_waiting > 0:
                    raw_line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                    if ',' in raw_line:
                        parts = raw_line.split(',')
                        if len(parts) == 2:
                            try:
                                last_valid_acceleration = float(parts[0])
                                last_status = parts[1]
                            except ValueError:
                                continue

                # 4. Если мы получили хоть одно число - ЗНАЧИТ СВЯЗЬ ТОЧНО ЕСТЬ
                if last_valid_acceleration is not None:
                    # 1. Обновляем данные графика
                    self.y_data = numpy.roll(self.y_data, -1)
                    self.y_data[-1] = last_valid_acceleration
                    self.data_line.setData(self.x_data, self.y_data)

                    # 2. СИЛОВОЕ ОБНОВЛЕНИЕ СТАТУСА
                    self.info_label.setProperty('instance', 'connected')
                    self.status_label.setProperty('instance', 'off')

                    # Пингуем систему стилей (через твой метод refresh_style)
                    self.refresh_style(self.info_label)
                    self.refresh_style(self.status_label)

                    # Принудительная перерисовка
                    self.info_label.update()

                    # 3. Логика пуш-уведомлений
                    if last_status == '1':
                        curr = time.time()
                        if not hasattr(self, 'last_push_time'):
                            self.last_push_time = 0
                        if curr - self.last_push_time > 5:
                            self.send_push()
                            self.alert()
                            self.centralWidget().update()
                            self.last_push_time = curr
        except Exception as e:
            print(f'Ошибка связи: {e}')
            self.ser = None

    def alert(self):
        self.signal.setProperty('earthquake', 'no')
        self.refresh_style(self.signal)

        self.signal.updateGeometry()  # Говорим лейауту: "мои размеры могли измениться"
        self.signal.repaint()  # Немедленно перерисовываем пиксели (сильнее чем update)
        QApplication.processEvents()

        dialog = QDialog(self)
        dialog.setWindowTitle('ОПОВЕЩЕНИЕ')

        layout = QVBoxLayout()

        gif = QLabel()
        self.movie = QMovie(resource_path('images/earthquake.gif'))
        # noinspection PyUnresolvedReferences
        self.movie.frameChanged.connect(gif.repaint)
        gif.setMovie(self.movie)
        self.movie.start()

        gif.setVisible(True)
        layout.addWidget(gif, alignment=Qt.AlignmentFlag.AlignCenter)

        text_s = 'QLabel { border-image: url(URL); }'
        text_s = text_s.replace('URL', resource_path('images/Внимание.png').replace('\\', '/'))
        text = QLabel()
        text.setFixedSize(500, 200)
        text.setStyleSheet(text_s)
        layout.addWidget(text, alignment=Qt.AlignmentFlag.AlignCenter)

        dialog.setLayout(layout)
        dialog.show()

    def on_tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self.show()

    def closeEvent(self, event):
        if self.tray_icon.isVisible():
            self.hide()
            event.ignore()
            self.tray_icon.showMessage(
                'Приложение свёрнуто',
                'Я всё еще работаю в фоновом режиме!',
                QSystemTrayIcon.MessageIcon.Information,
                2000
            )

    def delayed_notification(self):
        QTimer.singleShot(3000, self.send_push)

    def send_push(self):
        self.tray_icon.showMessage(
            'ВНИМАНИЕ! ЗЕМЛЕТРЯСЕНИЕ',
            'Зафиксированы толчки. Сохраняйте спокойствие',
            QSystemTrayIcon.MessageIcon.Warning,
            3000
        )

    @staticmethod
    def refresh_style(widget):
        widget.style().unpolish(widget)
        widget.style().polish(widget)
