from PyQt6.QtWidgets import QApplication
from main_window import MainWindow
import ctypes
import sys
import faulthandler

faulthandler.enable()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    myappid = 'dobryteam.earthquake.v1'
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

    window = MainWindow()
    window.show()
    app.exec()