# -*- coding: utf-8 -*-
"""Nebula GCI — Falcon BMS Ground Control Intercept
By Riesu — contact@falcon-charts.com
License: GNU GPL v3
"""
import sys, logging, os, glob
from logging.handlers import RotatingFileHandler
from datetime import datetime

LOG_DIR = os.path.join(os.path.expanduser("~"),
    "AppData","Local","NebulаGCI","logs") if sys.platform=="win32" \
    else os.path.join(os.path.expanduser("~"),".nebula_gci","logs")
os.makedirs(LOG_DIR, exist_ok=True)

# Clean old logs — keep last 10
old_logs = sorted(glob.glob(os.path.join(LOG_DIR, "nebula_*.log")))
for f in old_logs[:-3]:
    try: os.remove(f)
    except OSError: pass

LOG_FILE = os.path.join(LOG_DIR, f"nebula_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

logging.basicConfig(level=logging.INFO,
    format="[%(asctime)s] [%(levelname)-8s] %(name)s: %(message)s",
    handlers=[
        RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=3, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ])

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore    import Qt
from PyQt6.QtGui     import QIcon
from ui.main_window  import MainWindow
from ui.connection_dialog import ConnectionDialog

def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName("Nebula GCI")
    app.setStyle("Fusion")
    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "nebula.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    w = MainWindow(); w.show()
    # Dialogue connexion au démarrage
    dlg = ConnectionDialog(w._settings, w)
    dlg.connect_requested.connect(w._do_connect)
    dlg.exec()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
