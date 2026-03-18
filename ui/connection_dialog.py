# -*- coding: utf-8 -*-
"""
Fenêtre de connexion v3 — TRTT comme source principale
  - TRTT : vue GCI complète de tous les contacts (source principale)
  - Shared Memory : position ownship (optionnel, si le GCI vole aussi)
  - IVC : radio TeamSpeak (optionnel)
  - IP par défaut : 127.0.0.1 (même PC que BMS)
"""
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                              QLineEdit, QPushButton, QGroupBox, QCheckBox,
                              QSpinBox, QFormLayout, QFrame, QMessageBox)
from PyQt6.QtCore    import Qt, pyqtSignal
from PyQt6.QtGui     import QFont

STYLE = """
QDialog { background:#050d05; color:#44aa66; }
QGroupBox {
    color:#00d4ff; border:1px solid #0d3d0d; border-radius:4px;
    margin-top:8px; font-family:Consolas; font-size:11pt; font-weight:bold;
}
QGroupBox::title { subcontrol-origin:margin; left:10px; padding:0 4px; }
QLabel { color:#44aa66; font-family:Consolas; font-size:10pt; }
QLineEdit, QSpinBox {
    background:#071510; color:#aaffcc; border:1px solid #0d3d0d;
    border-radius:3px; padding:5px; font-family:Consolas; font-size:10pt;
    selection-background-color:#0d5a3a;
}
QLineEdit:focus, QSpinBox:focus { border:1px solid #00d4ff; }
QPushButton {
    background:#071510; color:#44aa66; border:1px solid #0d5a3a;
    border-radius:3px; padding:7px 20px; font-family:Consolas; font-size:10pt;
}
QPushButton:hover { background:#0d3d2a; color:#aaffcc; }
QPushButton#btn_ok {
    background:#0d3d2a; color:#00ff88; border:1px solid #00d4ff; font-weight:bold;
}
QPushButton#btn_ok:hover { background:#0d5a3a; }
QCheckBox { color:#44aa66; font-family:Consolas; font-size:10pt; }
QCheckBox::indicator {
    border:1px solid #0d5a3a; background:#071510; width:14px; height:14px;
}
QCheckBox::indicator:checked { background:#0d5a3a; }
"""


class ConnectionDialog(QDialog):
    connect_requested = pyqtSignal(dict)

    def __init__(self, settings=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("BMS GCI Radar — Connexion")
        self.setStyleSheet(STYLE)
        self.setFixedSize(460, 480)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self._s = settings or {}
        self._build()
        self._load()

    def _build(self):
        lay = QVBoxLayout(self); lay.setSpacing(10); lay.setContentsMargins(16,16,16,16)

        # Titre
        t = QLabel("◈  BMS GCI RADAR")
        t.setFont(QFont("Consolas", 14, QFont.Weight.Bold))
        t.setStyleSheet("color:#00d4ff; letter-spacing:2px;")
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(t)
        sub = QLabel("TRTT = source principale (vue GCI de tous les contacts)\n"
                     "Bullseye et route importés depuis le fichier mission .ini")
        sub.setStyleSheet("color:#1a5a2a; font-size:9pt; font-family:Consolas;")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(sub)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color:#0d3d0d;"); lay.addWidget(sep)

        # ── TRTT (source principale) ──
        grp = QGroupBox("TRTT — Tacview Real-Time (source principale)")
        f   = QFormLayout(grp); f.setSpacing(8)
        self.e_host = QLineEdit()
        self.e_host.setPlaceholderText("127.0.0.1 (même PC) ou IP distante")
        f.addRow("IP du PC BMS :", self.e_host)
        self.e_port = QSpinBox(); self.e_port.setRange(1,65535); self.e_port.setValue(42674)
        f.addRow("Port TRTT :", self.e_port)
        self.e_pass = QLineEdit()
        self.e_pass.setPlaceholderText("(vide si pas de mot de passe)")
        self.e_pass.setEchoMode(QLineEdit.EchoMode.Password)
        f.addRow("Mot de passe :", self.e_pass)
        # Info BMS config
        info = QLabel("BMS User.cfg requis : set g_bTacviewRealTime 1")
        info.setStyleSheet("color:#aa8822; font-size:8pt; font-family:Consolas;")
        f.addRow("", info)
        lay.addWidget(grp)

        # ── Shared Memory (optionnel) ──
        grp_sm = QGroupBox("Optionnel")
        f_sm   = QFormLayout(grp_sm); f_sm.setSpacing(8)
        lay.addWidget(grp_sm)  # empty optional section

        # ── IVC ──
        grp2 = QGroupBox("IVC / Radio BMS")
        f2   = QFormLayout(grp2); f2.setSpacing(8)
        self.chk_ivc = QCheckBox("Activer IVC (lit la SharedMemory BMS)")
        f2.addRow("", self.chk_ivc)
        lbl_info = QLabel("Lit UHF/VHF depuis BMS — aucune config réseau requise")
        lbl_info.setStyleSheet("color:#557755; font-size:9pt; font-style:italic;")
        f2.addRow("", lbl_info)
        lay.addWidget(grp2)

        # Boutons
        bl = QHBoxLayout()
        bq = QPushButton("Quitter"); bq.clicked.connect(self.reject)
        self.btn_ok = QPushButton("⚡  CONNECTER"); self.btn_ok.setObjectName("btn_ok")
        self.btn_ok.setDefault(True); self.btn_ok.clicked.connect(self._ok)
        bl.addWidget(bq); bl.addStretch(); bl.addWidget(self.btn_ok)
        lay.addLayout(bl)

    def _load(self):
        s = self._s
        self.e_host.setText(s.get("bms_host", "") or "127.0.0.1")
        self.e_port.setValue(s.get("bms_port", 42674))
        self.e_pass.setText(s.get("bms_pass", ""))
        
        self.chk_ivc.setChecked(s.get("ivc_enabled", False))
        

    def _ok(self):
        host = self.e_host.text().strip() or "127.0.0.1"
        self.connect_requested.emit({
            "bms_host":    host,
            "bms_port":    self.e_port.value(),
            "bms_pass":    self.e_pass.text(),
            
            "ivc_enabled": self.chk_ivc.isChecked(),
            
            
        })
        self.accept()
