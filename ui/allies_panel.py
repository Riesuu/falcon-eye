# -*- coding: utf-8 -*-
"""
AlliesPanel — Fenêtre flottante liste des avions alliés en vol
Style : tableau compact, callsign / type / alt / speed / hdg
"""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QTableWidget, QTableWidgetItem, QHeaderView,
                              QPushButton, QFrame)
from PyQt6.QtCore    import Qt, QTimer
from PyQt6.QtGui     import QFont, QColor

STYLE = """
QWidget#allies {
    background: #050d05;
    border: 1px solid #0d3d0d;
    border-radius: 4px;
}
QLabel#title {
    color: #00d4ff;
    font-family: Consolas; font-size: 11pt; font-weight: bold;
    padding: 4px 8px;
}
QLabel#sub {
    color: #1a5a2a; font-family: Consolas; font-size: 8pt; padding: 0 8px 4px;
}
QTableWidget {
    background: #050d05;
    color: #44aa66;
    font-family: Consolas; font-size: 9pt;
    gridline-color: #0d2a0d;
    border: none;
    selection-background-color: #0d3d2a;
}
QHeaderView::section {
    background: #071510;
    color: #2a7a4a;
    font-family: Consolas; font-size: 8pt; font-weight: bold;
    border: none;
    border-bottom: 1px solid #0d3d0d;
    padding: 3px 6px;
}
QScrollBar:vertical {
    background: #050d05; width: 8px;
}
QScrollBar::handle:vertical { background: #0d3d0d; }
QPushButton#close_btn {
    background: transparent; color: #ff4444;
    border: none; font-family: Consolas; font-size: 10pt;
    padding: 2px 6px;
}
QPushButton#close_btn:hover { color: #ff8888; }
"""


class AlliesPanel(QWidget):
    def __init__(self, get_tracks_fn, parent=None):
        super().__init__(parent)
        self.get_tracks = get_tracks_fn
        self.setObjectName("allies")
        self.setStyleSheet(STYLE)
        self.setWindowTitle("Allies en vol")
        self.setFixedWidth(340)
        self._build_ui()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(1000)

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Header
        hdr = QFrame(); hdr.setObjectName("allies")
        hdr.setStyleSheet("QFrame{background:#071510;border-bottom:1px solid #0d3d0d;}")
        hdr_lay = QHBoxLayout(hdr)
        hdr_lay.setContentsMargins(8, 4, 4, 4)

        title = QLabel("◈ ALLIÉS EN VOL"); title.setObjectName("title")
        hdr_lay.addWidget(title)
        hdr_lay.addStretch()

        self.lbl_count = QLabel("0 piste(s)")
        self.lbl_count.setStyleSheet("color:#2a6a3a;font-family:Consolas;font-size:9pt;padding:0 8px;")
        hdr_lay.addWidget(self.lbl_count)

        lay.addWidget(hdr)

        sub = QLabel("Callsign · Type · Alt (FL) · Speed (kt) · HDG")
        sub.setObjectName("sub"); lay.addWidget(sub)

        # Tableau
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["CALLSIGN", "TYPE", "FL", "KT", "HDG", "ID"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(2, 55)
        self.table.setColumnWidth(3, 55)
        self.table.setColumnWidth(4, 50)
        self.table.setColumnWidth(5, 80)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet(STYLE + """
            QTableWidget::item:alternate { background: #060f06; }
        """)
        lay.addWidget(self.table)

        # Légende bas
        leg = QFrame()
        leg.setStyleSheet("QFrame{background:#030a03;border-top:1px solid #0d2a0d;}")
        leg_lay = QHBoxLayout(leg)
        leg_lay.setContentsMargins(8, 3, 8, 3)
        for txt, col in [("■ FRIEND", "#00d4ff"), ("■ HUMAN", "#ffffff"),
                          ("■ NEUTRAL", "#aaaaaa"), ("■ ASSUMED", "#44aaff")]:
            l = QLabel(txt)
            l.setStyleSheet(f"color:{col};font-family:Consolas;font-size:8pt;")
            leg_lay.addWidget(l)
        leg_lay.addStretch()
        lay.addWidget(leg)

    def _refresh(self):
        try:
            tracks = self.get_tracks()
        except Exception:
            return

        allies = [
            t for t in tracks.values()
            if t.alive and t.is_air and t.lat != 0
            and t.coalition in ("Blue", "Allies")
        ]
        allies.sort(key=lambda t: (not t.is_human, t.display_label))

        self.lbl_count.setText(f"{len(allies)} piste(s)")
        self.table.setRowCount(len(allies))

        for row, t in enumerate(allies):
            fl  = f"{t.alt_ft // 100:03d}"
            spd = f"{t.speed_kts}"
            hdg = f"{int(t.hdg):03d}°"

            items = [
                t.display_label,
                t.name[:14] or "—",
                fl, spd, hdg,
                t.id_code[:12],
            ]
            col = QColor(t.color)
            for col_idx, val in enumerate(items):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter |
                                      (Qt.AlignmentFlag.AlignLeft if col_idx <= 1
                                       else Qt.AlignmentFlag.AlignHCenter))
                # Callsign en couleur piste, reste atténué
                if col_idx == 0:
                    item.setForeground(col.lighter(130) if t.is_human else col)
                    if t.is_human:
                        f = QFont("Consolas", 9, QFont.Weight.Bold)
                        item.setFont(f)
                else:
                    item.setForeground(col.darker(110))
                self.table.setItem(row, col_idx, item)

            self.table.setRowHeight(row, 20)

    def closeEvent(self, e):
        self._timer.stop()
        e.accept()

    def showEvent(self, e):
        self._timer.start(1000)
        self._refresh()
        super().showEvent(e)
