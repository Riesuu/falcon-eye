# -*- coding: utf-8 -*-
"""
FlightStrip — strip horizontal, redimensionnable, flottant
Style GCI militaire — layout paysage comme les vrais strips papier
"""
from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QLabel,
                              QSizeGrip, QFrame)
from PyQt6.QtCore    import Qt, QPoint, QSize, pyqtSignal
from PyQt6.QtGui     import QFont, QColor, QPainter, QPen, QBrush

COUNTRY_COLORS = {
    "ROK":  "#00e5ff",
    "DPRK": "#ff4444",
    "JPN":  "#44cc66",
    "USA":  "#44aaff",
}
DEFAULT_COLOR = "#666666"


class FlightStrip(QWidget):
    """Strip horizontal flottant, déplaçable et redimensionnable."""

    def __init__(self, icao: str, apt_data: dict, parent=None):
        super().__init__(parent,
            Qt.WindowType.Tool |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.icao  = icao
        self.apt   = apt_data
        self._drag = None
        self._col  = QColor(COUNTRY_COLORS.get(apt_data.get("country", ""), DEFAULT_COLOR))
        self._build_ui()
        self.setMinimumSize(500, 58)
        self.resize(680, 64)

    # ── Construction UI ───────────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(0)

        # Fond principal
        self.frame = QFrame()
        self.frame.setObjectName("sf")
        self.frame.setStyleSheet("""
            QFrame#sf {
                background: #040e05;
                border: 1px solid #1a4a1a;
                border-radius: 2px;
            }
        """)
        root.addWidget(self.frame)

        row = QHBoxLayout(self.frame)
        row.setContentsMargins(12, 6, 8, 6)
        row.setSpacing(0)

        # ── [ICAO] ──
        lbl_icao = QLabel(self.icao)
        lbl_icao.setFont(QFont("Consolas", 16, QFont.Weight.Bold))
        lbl_icao.setStyleSheet(f"color:{self._col.name()}; min-width:68px;")
        row.addWidget(lbl_icao)
        row.addWidget(self._sep())

        # ── [Nom] ──
        lbl_name = QLabel(self.apt.get("name", "—"))
        lbl_name.setFont(QFont("Consolas", 11))
        lbl_name.setStyleSheet("color:#33cc55; min-width:100px; max-width:180px;")
        row.addWidget(lbl_name)
        row.addWidget(self._sep())

        # ── [TACAN / ELEV] ──
        tacan = self.apt.get("tacan", "—") or "—"
        elev  = self.apt.get("elev_ft", "?")
        col_tacan = QVBoxLayout()
        col_tacan.setSpacing(1)
        col_tacan.setContentsMargins(8, 0, 8, 0)
        col_tacan.addWidget(self._kv("TCN", tacan,        "#ffdd88"))
        col_tacan.addWidget(self._kv("ELV", f"{elev}FT", "#aaffcc"))
        row.addLayout(col_tacan)
        row.addWidget(self._sep())

        # ── [Pistes] ──
        rwys = self.apt.get("runways", [])
        col_rwy = QVBoxLayout()
        col_rwy.setSpacing(1)
        col_rwy.setContentsMargins(8, 0, 8, 0)
        if rwys:
            for r in rwys[:2]:
                col_rwy.addWidget(self._kv(r[3], f"{r[1]}FT", "#aaffcc"))
        else:
            col_rwy.addWidget(self._kv("RWY", "—", "#aaffcc"))
        row.addLayout(col_rwy)
        row.addWidget(self._sep())

        # ── [Fréquences] ──
        freqs   = self.apt.get("freqs", {})
        col_frq = QVBoxLayout()
        col_frq.setSpacing(1)
        col_frq.setContentsMargins(8, 0, 8, 0)
        priority = ["TWR", "APP", "GND", "ATIS"]
        shown = 0
        for k in priority:
            if k in freqs and shown < 3:
                col_frq.addWidget(self._kv(k, freqs[k], "#88ccff"))
                shown += 1
        for k, v in freqs.items():
            if k not in priority and shown < 3:
                col_frq.addWidget(self._kv(k, v, "#88ccff"))
                shown += 1
        if shown == 0:
            col_frq.addWidget(self._kv("---", "---", "#444444"))
        row.addLayout(col_frq)
        row.addStretch(1)

        # ── Bouton fermer ──
        btn = _CloseBtn(self._col)
        btn.clicked_signal.connect(self.close)
        row.addWidget(btn, 0, Qt.AlignmentFlag.AlignVCenter)

        # ── SizeGrip invisible ──
        grip = QSizeGrip(self)
        grip.setFixedSize(14, 14)
        grip.setStyleSheet("QSizeGrip { background: transparent; }")
        grip_row = QHBoxLayout()
        grip_row.setContentsMargins(0, 0, 0, 0)
        grip_row.addStretch()
        grip_row.addWidget(grip)
        root.addLayout(grip_row)

    def _sep(self):
        f = QFrame()
        f.setFrameShape(QFrame.Shape.VLine)
        f.setFixedWidth(1)
        f.setStyleSheet(f"background: {self._col.darker(250).name()}; margin: 5px 5px;")
        return f

    def _kv(self, key: str, val: str, val_color: str) -> QWidget:
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(5)
        lk = QLabel(f"{key:<4}")
        lk.setFont(QFont("Consolas", 8))
        lk.setStyleSheet("color:#1a5a2a;")
        lk.setFixedWidth(30)
        lv = QLabel(val)
        lv.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
        lv.setStyleSheet(f"color:{val_color};")
        h.addWidget(lk)
        h.addWidget(lv)
        return w

    def paintEvent(self, e):
        super().paintEvent(e)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = QColor(self._col); c.setAlpha(210)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(c))
        p.drawRect(4, 4, 5, self.height() - 8)

    # ── Drag ──────────────────────────────────────────────────────────────────
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag and (e.buttons() & Qt.MouseButton.LeftButton):
            self.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, e):
        self._drag = None


class _CloseBtn(QWidget):
    clicked_signal = pyqtSignal()

    def __init__(self, accent: QColor, parent=None):
        super().__init__(parent)
        self._c  = accent
        self._hov = False
        self.setFixedSize(22, 22)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def enterEvent(self, e):  self._hov = True;  self.update()
    def leaveEvent(self, e):  self._hov = False; self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked_signal.emit()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = self._c.lighter(150) if self._hov else self._c.darker(120)
        p.setPen(QPen(c, 2.0))
        m = 6
        p.drawLine(m, m, self.width()-m, self.height()-m)
        p.drawLine(self.width()-m, m, m, self.height()-m)
