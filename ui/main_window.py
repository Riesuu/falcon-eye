# -*- coding: utf-8 -*-
"""
Falcon-Eye — By Riesu (contact@falcon-charts.com) — GPL v3
- Bouton CONNECTER remplacé par DÉCO quand connecté (un seul bouton)
- Toggles séparés : Aéroports / ICAO / Nom
- Pas de module dessin
- Panneau flottant Alliés en vol
- Options couleurs
- Status bar complète
"""
import asyncio, threading, logging, json, os
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QToolBar, QStatusBar, QLabel, QPushButton, QCheckBox, QComboBox,
    QFileDialog, QFrame, QDialog, QScrollArea,
    QSplitter, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer, QObject, pyqtSignal, pyqtSlot
from PyQt6.QtGui  import QFont

from ui.radar_widget   import RadarWidget
from ui.connection_dialog import ConnectionDialog
from ui.allies_panel   import AlliesPanel

logger = logging.getLogger(__name__)
SETTINGS_FILE = os.path.join(os.path.expanduser("~"), ".bms_gci4_settings.json")

STYLE = """
QMainWindow, QWidget#central { background: #050d05; }

QToolBar {
    background: #071510;
    border-bottom: 1px solid #0d3d0d;
    spacing: 3px; padding: 2px 8px;
}
QToolBar QLabel { color: #2a7a4a; font-family: Consolas; font-size: 10pt; }

QPushButton {
    background: #071510; color: #44aa66;
    border: 1px solid #0d3d0d; border-radius: 3px;
    padding: 4px 10px; font-family: Consolas; font-size: 10pt;
    min-width: 60px;
}
QPushButton:hover   { background: #0d3d2a; color: #aaffcc; }
QPushButton:pressed { background: #0a2a1a; }
QPushButton#btn_connect { color: #00ff88; border-color: #00aa44; font-weight: bold; }
QPushButton#btn_disconn { color: #ff6666; border-color: #aa2222; font-weight: bold; }
QPushButton#btn_import  { color: #aaddff; border-color: #2266aa; }
QPushButton#btn_options { color: #ffdd88; border-color: #aa8822; }
QPushButton#btn_allies  { color: #aaffcc; border-color: #00aa66; }

QComboBox {
    background: #071510; color: #44aa66;
    border: 1px solid #0d3d0d; border-radius: 3px;
    padding: 3px 8px; font-family: Consolas; font-size: 10pt;
    min-width: 80px;
}
QComboBox::drop-down { border: none; }
QComboBox QAbstractItemView {
    background: #071510; color: #44aa66;
    selection-background-color: #0d3d2a;
    font-family: Consolas; font-size: 10pt;
}
QCheckBox {
    color: #2a7a4a; font-family: Consolas; font-size: 10pt; spacing: 5px;
}
QCheckBox::indicator {
    border: 1px solid #0d3d0d; background: #071510;
    width: 13px; height: 13px; border-radius: 2px;
}
QCheckBox::indicator:checked { background: #0d5a2a; border-color: #00aa44; }

QStatusBar {
    background: #020a03; color: #1a5a2a;
    border-top: 1px solid #0d3d0d;
    font-family: Consolas; font-size: 9pt;
}
QStatusBar QLabel {
    color: #2a6a3a; font-family: Consolas; font-size: 9pt; padding: 0 5px;
}
QSplitter::handle { background: #0d3d0d; width: 1px; }
QToolBar::separator { background: #0d3d0d; width: 1px; margin: 3px 4px; }
QToolTip { background:#071510; color:#aaffcc; border:1px solid #0d3d2a;
           font-family:Consolas; font-size:9pt; }

/* Options */
QDialog#options_dlg { background: #050d05; }
QDialog#options_dlg QLabel { color: #44aa66; font-family: Consolas; font-size: 9pt; }
QScrollArea { background: #050d05; border: none; }
QScrollArea QWidget { background: #050d05; }
"""


class _Bridge(QObject):
    tracks_updated  = pyqtSignal(dict)
    ownship_updated = pyqtSignal(dict)
    bms_status      = pyqtSignal(bool, str)
    ivc_status      = pyqtSignal(bool, str)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Falcon-Eye")
        self.setMinimumSize(1000, 720)
        self.resize(1440, 900)
        self.setStyleSheet(STYLE)

        self._settings  = self._load_settings()
        self._bridge    = _Bridge()
        self._loop      = None
        self._trtt      = None
        
        self._ivc       = None
        self._connected = False
        self._ivc_conn  = False
        
        self._allies_panel: AlliesPanel  = None
        self._tracks: dict = {}

        self._setup_ui()
        self._connect_signals()
        self._start_async_loop()

        # SM timer removed (GCI doesn't need ownship)
        self._clock_timer = QTimer(self); self._clock_timer.timeout.connect(self._update_clock); self._clock_timer.start(1000)

    # ── UI ────────────────────────────────────────────────────────────────────
    def _setup_ui(self):
        # ── Toolbar 1 ─────────────────────────────────────────────────────────
        tb1 = QToolBar("Principal"); tb1.setMovable(False)
        self.addToolBar(tb1)

        # Bouton unique : CONNECTER ou DÉCO selon état
        self.btn_conn = QPushButton("⚡ CONNECTER")
        self.btn_conn.setObjectName("btn_connect")
        self.btn_conn.clicked.connect(self._on_conn_btn)
        tb1.addWidget(self.btn_conn)
        tb1.addSeparator()

        self.btn_import = QPushButton("📂 MISSION")
        self.btn_import.setObjectName("btn_import")
        self.btn_import.clicked.connect(self._import_mission)
        tb1.addWidget(self.btn_import)
        tb1.addSeparator()

        tb1.addSeparator()

        btn_bull = QPushButton("◎ BULL"); btn_bull.clicked.connect(self._center_bull)
        btn_home = QPushButton("🏠 KOREA"); btn_home.clicked.connect(lambda: self.radar.center_on(37.5, 127.5))
        tb1.addWidget(btn_bull); tb1.addWidget(btn_home)
        tb1.addSeparator()

        self.btn_allies = QPushButton("✈ ALLIÉS")
        self.btn_allies.setObjectName("btn_allies")
        self.btn_allies.clicked.connect(self._show_allies)
        tb1.addWidget(self.btn_allies)

        btn_radio = QPushButton("📻 RADIO")
        btn_radio.clicked.connect(lambda: self.radar._js("toggleRadio();"))
        tb1.addWidget(btn_radio)

        btn_braa = QPushButton("📐 BRAA")
        btn_braa.setToolTip("Outil BRAA: clic-droit allié → clic gauche bogey")
        btn_braa.clicked.connect(lambda: self.radar._js("toggleBraaWin();"))
        tb1.addWidget(btn_braa)

        self.btn_options = QPushButton("⚙ OPTIONS")
        self.btn_options.setObjectName("btn_options")
        self.btn_options.clicked.connect(self._show_options)
        tb1.addWidget(self.btn_options)


        # ── Toolbar 2 : Layers ─────────────────────────────────────────────────
        tb2 = QToolBar("Layers"); tb2.setMovable(False)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, tb2)
        tb2.addWidget(_lbl(" LAYERS:"))
        self._layer_chks = {}

        layer_defs = [
            ("missiles",   "AAM"),
            ("labels",     "APT"),  ("apt_icao", "ICAO"), ("apt_name", "NOM"),
            ("runways",    "RWY"),
            ("trails",     "TRAIL"),
            ("velocity",   "VEC"),
            ("sam_rings",  "SAM"), ("flot", "FLOT"),
            ("route",      "ROUTE"),
            ("dmz",        "DMZ"),
        ]
        for layer, lbl3 in layer_defs:
            chk = QCheckBox(lbl3)
            chk.setChecked(True)
            chk.toggled.connect(lambda checked, l=layer: self.radar.toggle_layer(l, checked))
            self._layer_chks[layer] = chk
            tb2.addWidget(chk)

        # ── Central ────────────────────────────────────────────────────────────
        central = QWidget(); central.setObjectName("central")
        self.setCentralWidget(central)
        h_lay = QHBoxLayout(central)
        h_lay.setContentsMargins(0,0,0,0); h_lay.setSpacing(0)
        self.radar = RadarWidget()
        h_lay.addWidget(self.radar, 1)

        # ── Status bar ─────────────────────────────────────────────────────────
        sb = QStatusBar(); self.setStatusBar(sb)
        sb.setSizeGripEnabled(True)

        self._dot_bms = QLabel("●")
        self._dot_bms.setStyleSheet("color:#555555; font-size:12pt; padding:0 2px;")
        sb.addWidget(self._dot_bms)
        self.lbl_bms = _slbl("BMS : DÉCO", "#555555")
        sb.addWidget(self.lbl_bms)
        sb.addWidget(_vsep())

        self._dot_ivc = QLabel("●")
        self._dot_ivc.setStyleSheet("color:#555555; font-size:12pt; padding:0 2px;")
        sb.addWidget(self._dot_ivc)
        self.lbl_ivc_sb = _slbl("IVC : DÉCO", "#555555")
        sb.addWidget(self.lbl_ivc_sb)
        sb.addWidget(_vsep())

        self.lbl_tracks = _slbl("BLU:0  RED:0  AAM:0  HUM:0", "#2a6a3a")
        sb.addWidget(self.lbl_tracks)
        sb.addWidget(_vsep())

        self.lbl_mission = _slbl("Mission: —", "#2a4a6a")
        sb.addWidget(self.lbl_mission)
        sb.addWidget(_vsep())

        lbl_pan = _slbl("[ Drag: déplacer  |  Roulette: zoom  |  Clic-D: mesure  |  Clic allié: strip ]", "#1a3a2a")
        sb.addWidget(lbl_pan)

        self.lbl_cursor = _slbl("---.----°N  ---.----°E", "#1a4a2a")
        sb.addPermanentWidget(self.lbl_cursor)
        sb.addPermanentWidget(_vsep())
        self.lbl_clock = _slbl("00:00:00Z", "#1a5a3a")
        sb.addPermanentWidget(self.lbl_clock)

    def _connect_signals(self):
        self._bridge.tracks_updated.connect(self._on_tracks)
        self._bridge.ownship_updated.connect(self._on_ownship)
        self._bridge.bms_status.connect(self._on_bms_status)
        self._bridge.ivc_status.connect(self._on_ivc_status)
        self.radar.cursor_moved.connect(self._on_cursor)
        self.radar.track_id_changed.connect(self._on_track_id_change)
        self.radar.radio_join_channel.connect(self._on_radio_join)

    def _on_track_id_change(self, uid: str, id_code: str):
        """Applique le changement d'ID depuis le menu clic-droit."""
        if self._trtt:
            self._trtt.set_track_id(uid, id_code)

    def _on_radio_join(self, channel_id: str):
        """Join IVC channel when user clicks in radio panel."""
        if self._ivc and self._ivc.connected:
            import logging
            logging.getLogger(__name__).info(f"IVC join channel: {channel_id}")
            self._ivc.join_channel(channel_id)

    # ── Bouton connexion unique ───────────────────────────────────────────────
    def _on_conn_btn(self):
        if self._connected:
            self._disconnect()
        else:
            self._show_conn_dlg()

    def _update_conn_btn(self):
        if self._connected:
            self.btn_conn.setText("✕ DÉCONNECTER")
            self.btn_conn.setObjectName("btn_disconn")
        else:
            self.btn_conn.setText("⚡ CONNECTER")
            self.btn_conn.setObjectName("btn_connect")
        # Forcer le recalcul du style
        self.btn_conn.style().unpolish(self.btn_conn)
        self.btn_conn.style().polish(self.btn_conn)

    # ── Connexion ─────────────────────────────────────────────────────────────
    def _show_conn_dlg(self):
        dlg = ConnectionDialog(self._settings, self)
        dlg.connect_requested.connect(self._do_connect)
        dlg.exec()

    def _do_connect(self, settings: dict):
        self._settings = settings
        self._save_settings(settings)
        asyncio.run_coroutine_threadsafe(
            self._async_trtt(settings["bms_host"], settings["bms_port"],
                             settings.get("bms_pass", "")),
            self._loop
        )
        if settings.get("ivc_enabled"):
            self._connect_ivc()

    async def _async_trtt(self, host, port, pw):
        from core.trtt_client import TRTTClient
        self._trtt = TRTTClient(on_update=lambda t: self._bridge.tracks_updated.emit(t))
        self.radar.trtt = self._trtt
        self._bridge.bms_status.emit(False, f"Connexion {host}:{port}…")
        ok = await self._trtt.connect(host, port, pw)
        if ok:
            self._connected = True
            self._bridge.bms_status.emit(True, f"{host}:{port}")
            await self._trtt.run()
            self._connected = False
            self._bridge.bms_status.emit(False, "déconnecté")
        else:
            self._bridge.bms_status.emit(False, f"Échec {host}:{port}")

    def _connect_ivc(self, host=None, port=None):
        """Connect IVC — reads UHF/VHF from BMS SharedMemory (no TS3 needed)."""
        from core.ivc_client import IVCClient

        # Stop any existing IVC session
        if self._ivc:
            self._ivc.disconnect()
            self._ivc = None
        if hasattr(self, "_ivc_poll_timer") and self._ivc_poll_timer:
            self._ivc_poll_timer.stop()

        self._ivc = IVCClient()
        result = self._ivc.connect()
        if result.get("status") == "ok":
            self._ivc_conn = True
            self._bridge.ivc_status.emit(True, "IVC BMS")
            # Poll SharedMemory every second for freq updates
            self._ivc_poll_timer = QTimer(self)
            self._ivc_poll_timer.timeout.connect(self._poll_ivc)
            self._ivc_poll_timer.start(2000)
        else:
            msg = result.get("message", "BMS non détecté")
            self._bridge.ivc_status.emit(False, msg)
            # Retry every 5s until BMS starts
            self._ivc_poll_timer = QTimer(self)
            self._ivc_poll_timer.timeout.connect(self._retry_ivc)
            self._ivc_poll_timer.start(5000)

    def _poll_ivc(self):
        """Poll BMS SharedMemory every 2s for UHF/VHF frequency updates."""
        if not self._ivc:
            return
        try:
            channels = self._ivc.get_channels()
            if not self._ivc.connected:
                # Only emit if was previously connected (avoid repeated status updates)
                if getattr(self, '_ivc_was_connected', True):
                    self._bridge.ivc_status.emit(False, "BMS arrêté")
                    self._ivc_was_connected = False
                return
            if not getattr(self, '_ivc_was_connected', False):
                self._bridge.ivc_status.emit(True, "IVC BMS")
                self._ivc_was_connected = True
            active_freq = channels[0]["freq"] if channels else ""
            active_name = channels[0]["name"] if channels else ""
            self.radar.update_ivc(channels, active_freq, active_name)
        except Exception as e:
            logging.getLogger(__name__).warning(f"IVC poll: {e}")

    def _retry_ivc(self):
        """Retry IVC connection every 5s until BMS SharedMemory is available."""
        from core.ivc_client import IVCClient
        if not self._ivc:
            self._ivc = IVCClient()
        result = self._ivc.connect()
        if result.get("status") == "ok":
            self._ivc_conn = True
            self._bridge.ivc_status.emit(True, "IVC BMS")
            if hasattr(self, "_ivc_poll_timer") and self._ivc_poll_timer:
                self._ivc_poll_timer.stop()
            self._ivc_poll_timer = QTimer(self)
            self._ivc_poll_timer.timeout.connect(self._poll_ivc)
            self._ivc_poll_timer.start(2000)

    def _init_sm(self):
        pass

    def _disconnect(self):
        self._connected = False
        if self._trtt:
            asyncio.run_coroutine_threadsafe(self._trtt.disconnect(), self._loop)
            self._trtt = None
        if self._ivc:
            self._ivc.disconnect(); self._ivc = None; self._ivc_conn = False

        self.radar.update_tracks({})
        self._tracks = {}
        self._bridge.bms_status.emit(False, "Déconnecté")
        self._bridge.ivc_status.emit(False, "Déconnecté")
        self._update_conn_btn()

    # ── Panneau allies integre ────────────────────────────────────────────────
    def _show_allies(self):
        """Toggle le panneau alliés intégré (comme IVC) à droite du radar."""
        if self._allies_panel is not None and self._allies_panel.isVisible():
            self._allies_panel.hide()
            self.btn_allies.setText("✈ ALLIES")
            self.btn_allies.setObjectName("btn_allies")
        else:
            if self._allies_panel is None:
                self._allies_panel = AlliesPanel(lambda: self._tracks)
                self.centralWidget().layout().addWidget(self._allies_panel)
            self._allies_panel.show()
            self.btn_allies.setText("✈ ALLIES [ON]")
        self.btn_allies.style().unpolish(self.btn_allies)
        self.btn_allies.style().polish(self.btn_allies)

    # ── Options ───────────────────────────────────────────────────────────────
    def _show_options(self):
        """Open the JS options panel inside the radar map."""
        self.radar._js("openOptions();")
        # Push audio devices seulement si pas encore charges -- evite le flash
        # noir cause par sounddevice/PortAudio qui bloque ~300ms au 1er appel.
        # Les rechargements suivants passent par onRequestAudioDevices() depuis JS.
        if not getattr(self.radar, '_audio_devices_loaded', False):
            self.radar._push_audio_devices()

    # ── Import mission ────────────────────────────────────────────────────────
    def _import_mission(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Importer mission BMS", "", "BMS Mission (*.ini);;Tous (*.*)")
        if not path: return
        try:
            from core.mission_parser import parse_mission_ini
            with open(path, "r", encoding="latin-1") as f:
                mission = parse_mission_ini(f.read())
            self.radar.set_mission(mission)
            bull = mission.get("bullseye")
            n_r  = len(mission.get("route", []))
            n_t  = len(mission.get("threats", []))
            n_ref = len(mission.get("ref_points", []))
            name = os.path.basename(path)
            if bull:
                bull_str = f"  BULL {bull['lat']:.3f}°N {bull['lon']:.3f}°E"
            else:
                bull_str = "  BULL: —"
            self.lbl_mission.setText(f"Mission: {name}{bull_str}  Rte:{n_r}  SAM:{n_t}  Ref:{n_ref}")
            self.lbl_mission.setStyleSheet(
                "color:#44aaff;font-family:Consolas;font-size:9pt;padding:0 5px;")
        except Exception as e:
            QMessageBox.warning(self, "Erreur", f"Import mission échoué:\n{e}")

    # ── Slots ─────────────────────────────────────────────────────────────────
    @pyqtSlot(dict)
    def _on_tracks(self, tracks):
        self._tracks = tracks
        self.radar.update_tracks(tracks)
        if self._trtt:
            st = self._trtt.stats()
            n_rd = sum(1 for t in tracks.values()
                       if t.alive and t.coalition in ("Red","Enemies") and t.is_air)
            txt = f"BLU:{st['air']}  RED:{n_rd}  AAM:{st['missile']}  HUM:{st['human']}"
            if self.lbl_tracks.text() != txt:
                self.lbl_tracks.setText(txt)

    @pyqtSlot(dict)
    def _on_ownship(self, data):
        pass  # ownship retiré comme demandé

    @pyqtSlot(bool, str)
    def _on_bms_status(self, connected, msg):
        was_connected = self._connected
        self._connected = connected
        # Guard: only update Qt widgets if state actually changed
        new_state = (connected, msg)
        if getattr(self, '_last_bms_state', None) != new_state:
            self._last_bms_state = new_state
            if connected:
                self._dot_bms.setStyleSheet("color:#00ff88;font-size:12pt;padding:0 2px;")
                self.lbl_bms.setText(f"BMS : {msg}")
                self.lbl_bms.setStyleSheet("color:#00ff88;font-family:Consolas;font-size:9pt;padding:0 5px;")
            else:
                color = "#ff4444" if "Échec" in msg else "#ffdd00" if "onnex" in msg else "#555555"
                self._dot_bms.setStyleSheet(f"color:{color};font-size:12pt;padding:0 2px;")
                self.lbl_bms.setText(f"BMS : {msg}")
                self.lbl_bms.setStyleSheet(f"color:{color};font-family:Consolas;font-size:9pt;padding:0 5px;")
        if connected != was_connected:
            self._update_conn_btn()

    @pyqtSlot(bool, str)
    def _on_ivc_status(self, connected, msg):
        # Guard: only update Qt widgets if state actually changed (setStyleSheet forces full repaint)
        new_state = (connected, msg)
        if getattr(self, '_last_ivc_state', None) == new_state:
            return
        self._last_ivc_state = new_state
        color = "#00ff88" if connected else "#555555"
        self._dot_ivc.setStyleSheet(f"color:{color};font-size:12pt;padding:0 2px;")
        self.lbl_ivc_sb.setText(f"IVC : {msg}")
        self.lbl_ivc_sb.setStyleSheet(f"color:{color};font-family:Consolas;font-size:9pt;padding:0 5px;")



    @pyqtSlot(float, float)
    def _on_cursor(self, lat, lon):
        ns = "N" if lat >= 0 else "S"
        ew = "E" if lon >= 0 else "W"
        self.lbl_cursor.setText(f"{abs(lat):8.4f}°{ns}  {abs(lon):9.4f}°{ew}")

    def _update_clock(self):
        from PyQt6.QtCore import QDateTime
        t = QDateTime.currentDateTimeUtc()
        txt = t.toString("HH:mm:ss") + "Z"
        if self.lbl_clock.text() != txt:
            self.lbl_clock.setText(txt)

    def _center_bull(self):
        bull = self.radar.bullseye
        if bull: self.radar.center_on(bull[0], bull[1])
        else:
            self.statusBar().showMessage("Aucun bullseye — importez une mission .ini", 3000)

    # ── Polling ───────────────────────────────────────────────────────────────
    def _poll_sm(self):
        pass

    # ── Async loop ────────────────────────────────────────────────────────────
    def _start_async_loop(self):
        self._loop_ready = threading.Event()
        def _run():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop_ready.set()
            self._loop.run_forever()
        threading.Thread(target=_run, daemon=True, name="AsyncLoop").start()
        self._loop_ready.wait(timeout=5.0)

    # ── Settings ──────────────────────────────────────────────────────────────
    def _load_settings(self):
        try:
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE) as f: return json.load(f)
        except Exception: pass
        return {"bms_host": "127.0.0.1", "bms_port": 42674, "bms_pass": "",
                 "ivc_enabled": False}

    def _save_settings(self, s):
        try:
            with open(SETTINGS_FILE, "w") as f: json.dump(s, f, indent=2)
        except Exception: pass

    def closeEvent(self, e):
        self._disconnect()
        if self._loop: self._loop.call_soon_threadsafe(self._loop.stop)
        e.accept()


# ── Helpers ───────────────────────────────────────────────────────────────────
def _lbl(txt):
    l = QLabel(txt); l.setFont(QFont("Consolas", 10)); return l

def _slbl(txt, color="#2a6a3a"):
    l = QLabel(txt)
    l.setStyleSheet(f"color:{color};font-family:Consolas;font-size:9pt;padding:0 5px;")
    return l

def _vsep():
    f = QFrame(); f.setFrameShape(QFrame.Shape.VLine)
    f.setStyleSheet("color:#0d3d0d;margin:2px 0;"); return f
