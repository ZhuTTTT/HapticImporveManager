import sys

from PySide6.QtWidgets import QApplication

from ui.main_window import create_main_window


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("HapticImproveManager")
    win = create_main_window()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
