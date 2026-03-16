# -*- coding: utf-8 -*-
"""IVC Panel v2"""
import logging
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QFrame, QScrollArea)
from PyQt6.QtCore    import Qt, QTimer
from PyQt6.QtGui     import QFont
logger = logging.getLogger(__name__)

STYLE = """
QWidget#ivc { background:#030e05; border-left:1px solid #0d3d0d; }
QLabel { color:#2a7a4a; font-family:Consolas; font-size:10pt; }
QScrollArea { border:none; background:transparent; }
QFrame#ch { background:#071510; border:1px solid #0d3d0d; border-radius:3px; margin:1px; }
"""

class IVCPanel(QWidget):
    def __init__(self, ivc, parent=None):
        super().__init__(parent); self.ivc = ivc
        self.setObjectName("ivc"); self.setStyleSheet(STYLE); self.setFixedWidth(230)
        lay = QVBoxLayout(self); lay.setContentsMargins(6,6,6,6); lay.setSpacing(4)
        hdr = QLabel("◈ IVC / RADIO")
        hdr.setFont(QFont("Consolas",11,QFont.Weight.Bold))
        hdr.setStyleSheet("color:#00d4ff;"); lay.addWidget(hdr)
        self.lbl_st = QLabel("● DÉCONNECTÉ"); self.lbl_st.setStyleSheet("color:#ff4444; font-size:9pt;")
        lay.addWidget(self.lbl_st)
        sc = QScrollArea(); sc.setWidgetResizable(True)
        sc.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.ch_w = QWidget(); self.ch_l = QVBoxLayout(self.ch_w)
        self.ch_l.setContentsMargins(0,0,0,0); self.ch_l.setSpacing(2); self.ch_l.addStretch()
        sc.setWidget(self.ch_w); lay.addWidget(sc)
        self.lbl_tx = QLabel(); self.lbl_tx.setStyleSheet("color:#ff9900; font-size:9pt;")
        lay.addWidget(self.lbl_tx)
        t = QTimer(self); t.timeout.connect(self._refresh); t.start(1500)

    def _refresh(self):
        if not self.ivc or not self.ivc.connected:
            self.lbl_st.setText("● DÉCONNECTÉ"); self.lbl_st.setStyleSheet("color:#666; font-size:9pt;"); return
        try:
            channels = self.ivc.get_channels(); talking = self.ivc.get_talking()
            # Remove all channel widgets (keep only the stretch at the end)
            while self.ch_l.count() > 1:
                item = self.ch_l.takeAt(0)
                w = item.widget()
                if w:
                    w.setParent(None)
                    w.deleteLater()
            for ch in channels:
                fr = QFrame(); fr.setObjectName("ch")
                fl = QVBoxLayout(fr); fl.setContentsMargins(6,4,6,4); fl.setSpacing(1)
                nm = QLabel(ch.get("name","?")[:26])
                nm.setStyleSheet("color:#44aa66; font-weight:bold; font-size:10pt;")
                fl.addWidget(nm)
                freq = ch.get("freq","")
                if freq:
                    fq = QLabel(freq); fq.setStyleSheet("color:#ffdd00; font-size:9pt;"); fl.addWidget(fq)
                for pilot in ch.get("pilots",[]):
                    pn = pilot.get("name","?")[:22]; is_tx = pn == talking
                    pl = QLabel(("▶ " if is_tx else "  ") + pn)
                    pl.setStyleSheet("color:#00ff88; font-weight:bold;" if is_tx else "color:#2a7a4a;")
                    fl.addWidget(pl)
                self.ch_l.insertWidget(self.ch_l.count()-1, fr)
            self.lbl_st.setText("● CONNECTÉ"); self.lbl_st.setStyleSheet("color:#00ff88; font-size:9pt;")
            self.lbl_tx.setText(f"▶ TX: {talking}" if talking else "")
        except Exception as e:
            logger.warning(f"IVC refresh: {e}")
