# -*- coding: utf-8 -*-
"""
BRAAWindow — Fenêtre BRAA dynamique (inspiré LotATC)
Usage:
  - Ctrl+Clic sur un allié → le marque comme "référence"
  - Clic sur une menace → calcule BRAA depuis référence vers menace
  - La fenêtre se met à jour en temps réel avec les positions des deux pistes
"""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtCore    import Qt, QPoint, QTimer
from PyQt6.QtGui     import QFont, QColor

from core.data import haversine_nm, bearing_deg

STYLE = """
QWidget#braa_frame {
    background: #020d04;
    border: 1px solid #00aa44;
    border-top: 3px solid #00ff88;
    border-radius: 4px;
}
QLabel { font-family: Consolas; background: transparent; }
QPushButton#close_btn {
    background: transparent; color: #555; border: none;
    font-family: Consolas; font-size: 9pt;
    max-width: 18px;
}
QPushButton#close_btn:hover { color: #ff4444; }
QPushButton#lock_btn {
    background: #071510; color: #00aa44; border: 1px solid #0d3d0d;
    font-family: Consolas; font-size: 8pt; border-radius: 2px;
    padding: 1px 6px;
}
QPushButton#lock_btn:checked { color: #00ff88; border-color: #00ff88; background: #0a2a18; }
"""


class BRAAWindow(QWidget):
    """
    Fenêtre flottante affichant le BRAA dynamique entre deux pistes.
    Instancier, puis appeler update_tracks(tracks) régulièrement.
    """

    def __init__(self, from_uid: str, to_uid: str,
                 from_label: str, to_label: str,
                 from_color: str, to_color: str,
                 get_tracks_fn, parent=None):
        super().__init__(parent, Qt.WindowType.Tool |
                         Qt.WindowType.WindowStaysOnTopHint |
                         Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.from_uid   = from_uid
        self.to_uid     = to_uid
        self.from_label = from_label
        self.to_label   = to_label
        self.from_color = from_color
        self.to_color   = to_color
        self.get_tracks = get_tracks_fn
        self._drag_pos: QPoint | None = None

        self._build_ui()
        self.adjustSize()

        # Auto-refresh
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(500)
        self._refresh()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(0)

        frame = QWidget()
        frame.setObjectName("braa_frame")
        frame.setStyleSheet(STYLE)
        outer.addWidget(frame)

        lay = QVBoxLayout(frame)
        lay.setContentsMargins(10, 8, 10, 10)
        lay.setSpacing(4)

        # ── Header ──
        hdr = QHBoxLayout()
        lbl_title = QLabel("◈ BRAA")
        lbl_title.setStyleSheet("color:#00ff88; font-size:11pt; font-weight:bold;")
        hdr.addWidget(lbl_title)
        hdr.addStretch()
        btn_close = QPushButton("✕"); btn_close.setObjectName("close_btn")
        btn_close.clicked.connect(self.close)
        hdr.addWidget(btn_close)
        lay.addLayout(hdr)

        # ── De / Vers ──
        ref_row = QHBoxLayout()
        lbl_from_key = QLabel("FROM  ")
        lbl_from_key.setStyleSheet("color:#2a6a3a; font-size:9pt;")
        self.lbl_from = QLabel(self.from_label)
        self.lbl_from.setStyleSheet(f"color:{self.from_color}; font-size:9pt; font-weight:bold;")
        ref_row.addWidget(lbl_from_key); ref_row.addWidget(self.lbl_from); ref_row.addStretch()
        lay.addLayout(ref_row)

        tgt_row = QHBoxLayout()
        lbl_to_key = QLabel("TO    ")
        lbl_to_key.setStyleSheet("color:#2a6a3a; font-size:9pt;")
        self.lbl_to = QLabel(self.to_label)
        self.lbl_to.setStyleSheet(f"color:{self.to_color}; font-size:9pt; font-weight:bold;")
        tgt_row.addWidget(lbl_to_key); tgt_row.addWidget(self.lbl_to); tgt_row.addStretch()
        lay.addLayout(tgt_row)

        # ── Séparateur ──
        sep = QWidget(); sep.setFixedHeight(1)
        sep.setStyleSheet("background:#00aa44; margin:2px 0;")
        lay.addWidget(sep)

        # ── BRAA value ──
        self.lbl_braa = QLabel("---/---/---/---")
        self.lbl_braa.setStyleSheet("color:#00ff88; font-size:16pt; font-weight:bold; letter-spacing:2px;")
        self.lbl_braa.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.lbl_braa)

        # ── Legend ──
        leg = QLabel("BRG  /  RNG  /  ALT  /  SPD")
        leg.setStyleSheet("color:#1a5a2a; font-size:8pt;")
        leg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(leg)

        # ── Infos secondaires ──
        self.lbl_detail = QLabel("")
        self.lbl_detail.setStyleSheet("color:#44aa66; font-size:8pt;")
        self.lbl_detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.lbl_detail)

        # ── Reciprocal ──
        self.lbl_rec = QLabel("")
        self.lbl_rec.setStyleSheet("color:#1a6a3a; font-size:8pt;")
        self.lbl_rec.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.lbl_rec)

    def _refresh(self):
        try:
            tracks = self.get_tracks()
        except Exception:
            return

        t_from = tracks.get(self.from_uid)
        t_to   = tracks.get(self.to_uid)

        if not t_from or not t_from.alive or not t_from.lat:
            self.lbl_braa.setText("LOST")
            self.lbl_braa.setStyleSheet("color:#ff4444; font-size:16pt; font-weight:bold;")
            return
        if not t_to or not t_to.alive or not t_to.lat:
            self.lbl_braa.setText("LOST TGT")
            self.lbl_braa.setStyleSheet("color:#ffaa00; font-size:16pt; font-weight:bold;")
            return

        self.lbl_braa.setStyleSheet("color:#00ff88; font-size:16pt; font-weight:bold; letter-spacing:2px;")

        brg  = bearing_deg(t_from.lat, t_from.lon, t_to.lat, t_to.lon)
        rng  = haversine_nm(t_from.lat, t_from.lon, t_to.lat, t_to.lon)
        alt_fl = t_to.alt_ft // 100
        spd  = t_to.speed_kts
        rec  = (brg + 180) % 360

        self.lbl_braa.setText(f"{int(brg):03d} / {rng:5.1f} / {alt_fl:03d} / {spd}")
        self.lbl_detail.setText(f"HDG {int(t_to.hdg):03d}°  ·  {t_to.name[:12] or '—'}")
        self.lbl_rec.setText(f"REC  {int(rec):03d}°")

        # Mise à jour labels si callsigns changent
        self.lbl_from.setText(t_from.display_label)
        self.lbl_to.setText(t_to.display_label)

    # ── Drag ──────────────────────────────────────────────────────────────────
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._drag_pos and (e.buttons() & Qt.MouseButton.LeftButton):
            self.move(e.globalPosition().toPoint() - self._drag_pos)
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        self._drag_pos = None
        super().mouseReleaseEvent(e)

    def closeEvent(self, e):
        self._timer.stop()
        e.accept()
