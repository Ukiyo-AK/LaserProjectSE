from PyQt6.QtWidgets import QApplication
from app.main_window import MainWindow
import sys

def main() -> None:
    app = QApplication(sys.argv)
    wnd = MainWindow()
    wnd.resize(1200, 800)
    wnd.show()
    app.exec()

if __name__ == "__main__":
    main()


#python -m PyInstaller --onefile --noconsole --add-data "app;app" --icon=icon.ico main.py