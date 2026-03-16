# -*- coding: utf-8 -*-
"""
Nebula GCI — Tactical radar by Riesu (contact@falcon-charts.com) — GPL v3
Nouveautés v5:
  - Panneau Radio flottant draggable dans la carte
  - Trails historique trajectoire (20 pts, dégradé opacité)
  - Vecteurs vitesse (cap + longueur proportionnelle)
  - Anneaux SAM depuis mission INI (ppt_)
  - Bullseye avec cercles concentriques depuis INI
  - Lignes FLOT (lineSTPT_) depuis INI
  - Label aéroport ICAO + Nom (TACAN uniquement dans strip)
  - Mise à jour différentielle tracks (skip si pas bougé)
  - Push IVC → JS panneau radio (users, canaux, freq active)
  - Options reorganisées + section IVC (micro/HP + autojoin)
"""
import json, math
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore    import Qt, QTimer, pyqtSignal, QObject, pyqtSlot
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore    import QWebEngineSettings
from PyQt6.QtWebChannel       import QWebChannel
from PyQt6.QtGui              import QColor

from core.data        import (AIRPORTS, COASTLINE_KOREA, DMZ_LINE, RUNWAY_POLYGONS,
                               haversine_nm, bearing_deg, braa_str, bullseye_str)
from core.trtt_client import (Track, ID_UNKNOWN, ID_FRIEND, ID_BOGEY, ID_BANDIT,
                               ID_HOSTILE, ID_NEUTRAL, ID_SUSPECT, ID_ASSUMED,
                               ID_COLORS, COLOR_PRESETS)


class _Bridge(QObject):
    track_clicked    = pyqtSignal(str)
    apt_clicked      = pyqtSignal(str)
    cursor_moved_sig = pyqtSignal(float, float)
    id_changed_sig   = pyqtSignal(str, str)
    braa_ref_sig     = pyqtSignal(str, str, str)
    page_ready       = pyqtSignal()
    radio_join_ch    = pyqtSignal(str)
    radio_freq_sel   = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

    @pyqtSlot()
    def onPageReady(self): self.page_ready.emit()

    @pyqtSlot(str)
    def onTrackClick(self, uid): self.track_clicked.emit(uid)

    @pyqtSlot(str)
    def onAptClick(self, icao): self.apt_clicked.emit(icao)

    @pyqtSlot(float, float)
    def onCursorMove(self, lat, lon): self.cursor_moved_sig.emit(lat, lon)

    @pyqtSlot(str, str)
    def onIdChange(self, uid, id_code): self.id_changed_sig.emit(uid, id_code)

    @pyqtSlot(str, str, str)
    def onBraaRef(self, uid, label, color): self.braa_ref_sig.emit(uid, label, color)

    @pyqtSlot(str)
    def onRadioJoin(self, channel_id): self.radio_join_ch.emit(channel_id)

    @pyqtSlot(str)
    def onRadioFreq(self, freq): self.radio_freq_sel.emit(freq)


class RadarWidget(QWidget):
    track_selected     = pyqtSignal(object)
    track_id_changed   = pyqtSignal(str, str)
    cursor_moved       = pyqtSignal(float, float)
    braa_ref_selected  = pyqtSignal(str, str, str)
    radio_join_channel = pyqtSignal(str)
    radio_freq_changed = pyqtSignal(str)

    def __init__(self, trtt_client=None, parent=None):
        super().__init__(parent)
        self.trtt          = trtt_client
        self.tracks        = {}
        self._bullseye     = []
        self.mission       = {}
        self.selected_uid  = ""
        self._strips       = {}
        self._page_ready   = False
        self._pending_mission = None
        self._trails: dict = {}
        self._TRAIL_LEN    = 20
        self._last_pos: dict = {}
        self._ivc_data: dict = {"channels": [], "active_freq": "", "active_ch_name": ""}
        self.layers = {
            "coastline": True, "dmz": True, "runways": True,
            "trails": True, "labels": True, "threats": True,
            "route": True, "air_blue": True, "air_red": True,
            "missiles": True, "ground": False, "sam_rings": True,
            "velocity": True, "flot": True,
        }
        self._build_ui()
        self._push_timer = QTimer(self)
        self._push_timer.timeout.connect(self._push_tracks)
        self._push_timer.start(500)
        self._ivc_timer = QTimer(self)
        self._ivc_timer.timeout.connect(self._push_radio)
        self._ivc_timer.start(1000)

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self._view = QWebEngineView()
        self._view.settings().setAttribute(
            QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        self._view.settings().setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        self._channel = QWebChannel()
        self._bridge  = _Bridge(self)
        self._channel.registerObject("py", self._bridge)
        self._view.page().setWebChannel(self._channel)
        self._bridge.page_ready.connect(self._on_page_ready)
        self._bridge.track_clicked.connect(self._on_track_click)
        self._bridge.apt_clicked.connect(self._on_apt_click)
        self._bridge.cursor_moved_sig.connect(self.cursor_moved)
        self._bridge.id_changed_sig.connect(self.track_id_changed)
        self._bridge.braa_ref_sig.connect(self.braa_ref_selected)
        self._bridge.radio_join_ch.connect(self.radio_join_channel)
        self._bridge.radio_freq_sel.connect(self.radio_freq_changed)
        self._view.setHtml(self._build_html())
        lay.addWidget(self._view)

    def _on_page_ready(self):
        self._page_ready = True
        if self._pending_mission is not None:
            m = self._pending_mission
            self._pending_mission = None
            self.set_mission(m)

    def _js(self, code: str):
        if self._page_ready:
            self._view.page().runJavaScript(code)

    # ── API publique ─────────────────────────────────────────────────────────
    def update_tracks(self, tracks: dict): self.tracks = tracks

    def update_ivc(self, channels: list, active_freq: str = "", active_ch_name: str = ""):
        self._ivc_data = {"channels": channels, "active_freq": active_freq,
                          "active_ch_name": active_ch_name}

    def set_mission(self, mission: dict):
        self.mission = mission
        bull = mission.get("bullseye")
        if bull: self._bullseye = [bull["lat"], bull["lon"]]
        if not self._page_ready:
            self._pending_mission = mission; return
        import logging
        log = logging.getLogger(__name__)
        try:
            js = json.dumps(mission, ensure_ascii=False,
                            default=lambda o: o.__dict__ if hasattr(o, '__dict__') else str(o))
            self._js(f"setMission({js});")
            if bull:
                self._js(f"window._bullseye=[{bull['lat']},{bull['lon']}];")
            log.info(f"set_mission OK: route={len(mission.get('route',[]))} sam={len(mission.get('threats',[]))}")
        except Exception as e:
            log.error(f"set_mission: {e}")

    def set_scale(self, nm: float):
        zoom = max(5, min(14, round(math.log2(20000 / max(nm, 1)))))
        self._js(f"map.setZoom({zoom});")

    def set_layer(self, name: str, visible: bool):
        self.layers[name] = visible
        self._js(f"toggleLayer('{name}',{str(visible).lower()});")

    def toggle_layer(self, name: str, visible: bool):
        self.layers[name] = visible
        self._js(f"toggleLayer('{name}',{str(visible).lower()});")

    def center_on(self, lat: float, lon: float):
        self._js(f"map.setView([{lat},{lon}], map.getZoom());")

    @property
    def bullseye(self): return self._bullseye
    @bullseye.setter
    def bullseye(self, v): self._bullseye = v

    def _push_radio(self):
        if not self._page_ready: return
        self._js(f"updateRadio({json.dumps(self._ivc_data, ensure_ascii=False)});")

    def _push_tracks(self):
        if not self._page_ready: return
        alive  = [t for t in self.tracks.values() if t.alive]
        n_blue = sum(1 for t in alive if t.coalition in ("Blue","Allies") and t.is_air)
        n_red  = sum(1 for t in alive if t.coalition in ("Red","Enemies") and t.is_air)
        n_aam  = sum(1 for t in alive if t.is_missile)
        n_hum  = sum(1 for t in alive if t.is_human)

        show_blue = self.layers.get("air_blue", True)
        show_red  = self.layers.get("air_red", True)
        show_aam  = self.layers.get("missiles", True)

        tracks_list = []
        for t in alive:
            # GCI: only air + missiles (skip ground/sea entirely)
            if t.is_ground:
                continue
            if not (t.is_air or t.is_missile):
                continue
            if t.is_missile and not show_aam:
                continue
            if t.is_air and t.coalition in ("Blue", "Allies") and not show_blue:
                continue
            if t.is_air and t.coalition in ("Red", "Enemies") and not show_red:
                continue

            prev  = self._last_pos.get(t.uid)
            moved = (prev is None or
                     abs(t.lat - prev[0]) > 0.00008 or
                     abs(t.lon - prev[1]) > 0.00008 or
                     abs(t.hdg - prev[2]) > 1.0)
            self._last_pos[t.uid] = (t.lat, t.lon, t.hdg)
            trail = self._trails.setdefault(t.uid, [])
            if not trail or abs(t.lat-trail[-1][0])>0.0001 or abs(t.lon-trail[-1][1])>0.0001:
                trail.append((t.lat, t.lon))
                if len(trail) > self._TRAIL_LEN: trail.pop(0)
            tracks_list.append({
                "uid": t.uid, "lat": t.lat, "lon": t.lon, "hdg": t.hdg,
                "alt_ft": t.alt_ft, "speed_kts": t.speed_kts,
                "display_label": t.display_label, "name": t.name, "group": t.group,
                "coalition": t.coalition, "id_code": t.id_code,
                "is_human": t.is_human, "is_missile": t.is_missile,
                "color": t.color, "alive": t.alive, "moved": moved,
                "trail": trail[-8:],
            })

        alive_uids = {t.uid for t in alive}
        for uid in list(self._trails.keys()):
            if uid not in alive_uids: del self._trails[uid]
        for uid in list(self._last_pos.keys()):
            if uid not in alive_uids: del self._last_pos[uid]

        payload = {"tracks": tracks_list,
                   "n_blue": n_blue, "n_red": n_red, "n_aam": n_aam, "n_hum": n_hum}
        self._js(f"receiveTracks({json.dumps(payload, ensure_ascii=False)});")

    def _on_track_click(self, uid: str):
        self.selected_uid = uid
        t = self.tracks.get(uid)
        if t: self.track_selected.emit(t)

    def _on_apt_click(self, icao: str): pass  # géré en JS

    def _airports_json(self) -> str:
        return json.dumps([{
            "icao": icao, "lat": apt["lat"], "lon": apt["lon"],
            "name": apt.get("name",""), "tacan": apt.get("tacan",""),
            "elev_ft": apt.get("elev_ft",0), "country": apt.get("country",""),
            "freqs": apt.get("freqs",{}), "runways": apt.get("runways",[]),
        } for icao, apt in AIRPORTS.items()])

    def _runways_json(self) -> str:
        return json.dumps([{"icao": icao, "c": corners}
                           for icao, polys in RUNWAY_POLYGONS.items()
                           for corners in polys])

    def _build_html(self) -> str:
        airports_js = self._airports_json()
        runways_js  = self._runways_json()
        dmz_js      = json.dumps(DMZ_LINE)
        return _HTML_TEMPLATE.format(
            airports_js=airports_js,
            runways_js=runways_js,
            dmz_js=dmz_js,
        )

    def keyPressEvent(self, e): super().keyPressEvent(e)


# ── Template HTML (f-string avec {{ }} pour les accolades JS littérales) ─────
_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<link rel="icon" type="image/png" href="data:image/png;base64,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">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="qrc:///qtwebchannel/qwebchannel.js"></script>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
html,body,#map{{width:100%;height:100%;background:#080c08;overflow:hidden}}
.leaflet-container{{background:#080c08!important;font-family:Consolas,monospace}}
.leaflet-control-zoom,.leaflet-control-attribution{{display:none!important}}
.leaflet-div-icon,.leaflet-div-icon-clean{{background:transparent!important;border:none!important;padding:0!important}}

/* ── Label aéroport (ICAO + Nom, sans TACAN) ── */
.apt-tac{{font-family:Consolas,monospace;white-space:nowrap;cursor:pointer;user-select:none;pointer-events:all;display:inline-block}}
.apt-tac-box{{display:inline-flex;flex-direction:column;background:rgba(2,8,4,var(--lbl-alpha,0.72));padding:2px 8px 2px 5px;border-left:2px solid currentColor;backdrop-filter:blur(2px);transition:background .15s}}
.apt-tac-box:hover{{background:rgba(6,24,10,.92)}}
.apt-tac-icao{{font-size:var(--lbl-icao-sz,13px);font-weight:700;letter-spacing:.4px;line-height:1.3}}
.apt-tac-name{{font-size:var(--lbl-name-sz,10px);opacity:.65;line-height:1.2}}

/* ── Track labels ── */
.trk-lbl{{background:transparent;border:none;font-family:Consolas,monospace;pointer-events:none;white-space:nowrap;text-shadow:0 0 6px #000,0 0 12px #000}}

/* ── Flight Strip ── */
.fstrip{{position:fixed;background:rgba(2,10,4,var(--strip-alpha,.96));border:1px solid var(--strip-border,#1a4a1a);border-radius:3px;font-family:Consolas,monospace;box-shadow:0 6px 28px rgba(0,0,0,.9);min-width:540px;height:var(--strip-h,66px);z-index:8000;overflow:hidden;display:flex;flex-direction:row;align-items:stretch}}
.fstrip-accent{{width:5px;flex-shrink:0}}
.fstrip-drag{{display:flex;align-items:stretch;flex:1;cursor:move;overflow:hidden}}
.fstrip-cell{{display:flex;flex-direction:column;justify-content:center;padding:0 12px;border-right:1px solid rgba(255,255,255,.07);flex-shrink:0}}
.fstrip-cell.grow{{flex:1;min-width:0}}
.fstrip-icao{{font-size:var(--strip-icao-sz,18px);font-weight:700;letter-spacing:.5px;line-height:1.2}}
.fstrip-name{{font-size:var(--strip-name-sz,11px);line-height:1.2;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.fstrip-lbl{{font-size:var(--strip-lbl-sz,8px);letter-spacing:.4px;line-height:1.1;color:var(--strip-lbl-col,#1a6a30)}}
.fstrip-val{{font-size:var(--strip-val-sz,12px);font-weight:700;line-height:1.3}}
.fstrip-close{{width:32px;display:flex;align-items:center;justify-content:center;cursor:pointer;opacity:.4;font-size:18px;flex-shrink:0;border-left:1px solid rgba(255,255,255,.07);transition:opacity .15s}}
.fstrip-close:hover{{opacity:1}}
.fstrip-resize{{width:10px;background:transparent;cursor:ew-resize;flex-shrink:0;display:flex;align-items:center;justify-content:center;opacity:.25;font-size:10px;color:#44aa66}}
.fstrip-resize:hover{{opacity:.8}}

/* ── HUD ── */
#hud{{position:fixed;bottom:10px;left:10px;background:rgba(0,10,4,var(--hud-alpha,.78));border:1px solid var(--hud-border,#0d3d2a);padding:5px 12px;font-family:Consolas,monospace;font-size:var(--hud-sz,12px);font-weight:bold;pointer-events:none;z-index:9999;line-height:1.8}}
.h-blue{{color:var(--col-blue,#22ff44)}}.h-red{{color:var(--col-red,#ff2222)}}.h-aam{{color:var(--col-aam,#ff9900)}}.h-hum{{color:var(--col-hum,#aaffcc)}}.h-scl{{color:var(--col-scl,#1a5a1a)}}

/* ── Panneau RADIO flottant ── */
#radio-panel{{position:fixed;top:60px;right:14px;width:320px;min-width:280px;background:rgba(3,10,5,.97);border:1px solid rgba(0,180,80,.22);border-radius:4px;font-family:Consolas,monospace;box-shadow:0 8px 32px rgba(0,0,0,.95);z-index:9500;display:flex;flex-direction:column;max-height:82vh;min-height:120px}}
#radio-panel.hidden{{display:none}}
#radio-drag-bar{{background:rgba(0,20,10,.97);border-bottom:1px solid rgba(0,180,80,.18);padding:7px 12px;display:flex;align-items:center;justify-content:space-between;cursor:move;user-select:none;flex-shrink:0}}
.radio-title{{font-size:12px;font-weight:bold;color:#00e5ff;letter-spacing:2px;display:flex;align-items:center;gap:7px}}
.radio-dot{{width:7px;height:7px;border-radius:50%;background:#00e5a0;box-shadow:0 0 7px #00e5a0;animation:rpulse 2s infinite}}
@keyframes rpulse{{0%,100%{{opacity:1}}50%{{opacity:.25}}}}
.radio-close{{cursor:pointer;opacity:.4;font-size:16px;color:#aaffcc;transition:opacity .15s;pointer-events:all}}
.radio-close:hover{{opacity:1}}
#radio-body{{overflow-y:auto;flex:1}}
#radio-body::-webkit-scrollbar{{width:3px}}
#radio-body::-webkit-scrollbar-thumb{{background:rgba(0,180,80,.2);border-radius:2px}}
#radio-resize{{height:6px;cursor:ns-resize;background:transparent;display:flex;align-items:center;justify-content:center;opacity:.3;font-size:10px;color:#44aa66;flex-shrink:0}}
#radio-resize:hover{{opacity:.7}}
.r-freq-box{{padding:9px 12px;border-bottom:1px solid rgba(0,180,80,.12)}}
.r-freq-lbl{{font-size:8px;color:#007a50;letter-spacing:1.5px}}
.r-freq-val{{font-size:26px;font-weight:700;color:#ffcc44;letter-spacing:1px;text-shadow:0 0 12px rgba(255,204,68,.3);line-height:1.2}}
.r-freq-name{{font-size:10px;color:#00e5a0}}
.r-freq-btns{{display:flex;gap:4px;margin-top:7px}}
.r-btn{{flex:1;background:rgba(0,20,10,.8);border:1px solid rgba(0,180,80,.25);color:#007a50;font-family:Consolas,monospace;font-size:10px;padding:4px 0;border-radius:2px;text-align:center;cursor:pointer;transition:all .12s}}
.r-btn:hover{{background:rgba(0,40,18,.9);color:#00e5a0;border-color:#00e5a0}}
.r-btn.tx{{background:rgba(0,70,28,.7);border-color:#00e5a0;color:#00ff88}}
.r-ch-section{{padding:7px 12px;border-bottom:1px solid rgba(0,180,80,.10)}}
.r-sect-lbl{{font-size:8px;color:#007a50;letter-spacing:1.5px;margin-bottom:5px}}
.r-ch-grid{{display:grid;grid-template-columns:repeat(5,1fr);gap:3px}}
.r-ch{{background:rgba(0,10,5,.8);border:1px solid rgba(0,100,40,.2);color:#007a50;font-family:Consolas,monospace;font-size:9px;padding:4px 2px;text-align:center;border-radius:2px;cursor:pointer;transition:all .12s;line-height:1.4}}
.r-ch:hover{{background:rgba(0,30,12,.9);color:#00e5a0;border-color:rgba(0,180,80,.4)}}
.r-ch.active{{background:rgba(0,50,18,.8);border-color:#ffcc44;color:#ffcc44;box-shadow:0 0 5px rgba(255,204,68,.15)}}
.r-ch .cn{{font-size:7px;opacity:.55;display:block}}.r-ch .cf{{font-size:9px;display:block}}.r-ch .ck{{font-size:7px;opacity:.6;display:block}}
.r-users-section{{padding:7px 12px}}
.r-users-hdr{{display:flex;justify-content:space-between;align-items:center;margin-bottom:5px}}
.r-badge{{background:rgba(0,50,20,.7);border:1px solid rgba(0,180,80,.3);color:#00e5a0;font-size:8px;padding:1px 6px;border-radius:10px}}
.r-user{{display:flex;align-items:center;gap:5px;padding:4px 5px;border-radius:2px;border:1px solid transparent;border-left:2px solid transparent;cursor:pointer;transition:all .1s;margin-bottom:2px;font-size:10px}}
.r-user.same{{border-left-color:#00e5a0;background:rgba(0,18,8,.5)}}
.r-user.diff{{border-left-color:#1a3a22;opacity:.6}}
.r-user.txing{{border-color:rgba(0,255,100,.3);background:rgba(0,40,18,.7)}}
.r-user:hover{{background:rgba(0,25,12,.7)}}
.u-dot-tx{{width:7px;height:7px;border-radius:50%;background:#00ff88;box-shadow:0 0 7px #00ff88;flex-shrink:0;animation:rpulse .6s infinite}}
.u-dot{{width:7px;height:7px;border-radius:50%;background:#1a4a22;flex-shrink:0}}
.u-name{{flex:1;font-weight:700}}.u-freq{{font-size:9px;color:#ffcc44;min-width:48px}}.u-pos{{font-size:8px;color:#aaffcc;min-width:70px;text-align:right}}
.u-join{{font-size:8px;padding:2px 5px;border:1px solid rgba(0,180,80,.3);background:transparent;color:#007a50;border-radius:2px;cursor:pointer;font-family:Consolas,monospace;white-space:nowrap;transition:all .12s}}
.u-join:hover,.u-join.j{{border-color:#ffcc44;color:#ffcc44}}
.r-audio-section{{padding:7px 12px;border-top:1px solid rgba(0,180,80,.1)}}
.r-audio-row{{display:flex;align-items:center;gap:7px;margin-bottom:4px;font-size:10px}}
.r-audio-icon{{font-size:13px;min-width:18px}}
.r-audio-val{{flex:1;background:rgba(0,12,5,.8);border:1px solid rgba(0,100,40,.25);padding:3px 7px;border-radius:2px;color:#00e5a0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}


/* ── Friendly Flight Strip ── */
#flt-strip{{position:fixed;top:80px;left:50%;transform:translateX(-50%);min-width:300px;background:rgba(3,12,5,.97);border:1px solid rgba(34,255,68,.3);border-top:3px solid #22ff44;border-radius:4px;font-family:Consolas,monospace;box-shadow:0 8px 32px rgba(0,0,0,.9);z-index:9500;min-width:320px;display:none;padding:0}}
#flt-strip.open{{display:block}}
.fs-hdr{{background:rgba(0,20,8,.95);border-bottom:1px solid rgba(34,255,68,.2);padding:6px 12px;display:flex;align-items:center;justify-content:space-between;cursor:move}}
.fs-cs{{font-size:16px;font-weight:bold;color:#22ff44;letter-spacing:1px}}
.fs-type{{font-size:10px;color:#44aa66;margin-left:8px}}
.fs-close{{cursor:pointer;color:#666;font-size:14px;transition:color .15s}}
.fs-close:hover{{color:#ff4444}}
.fs-body{{padding:8px 12px;display:grid;grid-template-columns:1fr 1fr;gap:4px 16px}}
.fs-lbl{{font-size:8px;color:#1a6a30;letter-spacing:1px}}
.fs-val{{font-size:14px;font-weight:bold;color:#aaffcc;margin-bottom:4px}}
.fs-val.spd{{color:#ffcc44}}.fs-val.hdg{{color:#44ccff}}.fs-val.alt{{color:#22ff44}}



/* ── BRAA Window ── */
#braa-win{{position:fixed;top:80px;right:14px;width:360px;min-width:300px;background:rgba(3,12,5,.97);border:1px solid rgba(0,180,80,.25);border-top:3px solid #00e5ff;border-radius:4px;font-family:Consolas,monospace;box-shadow:0 8px 32px rgba(0,0,0,.9);z-index:9500;display:none;padding:0;max-height:80vh;overflow-y:auto}}
#braa-win.open{{display:block}}
.braa-hdr{{background:rgba(0,20,8,.95);border-bottom:1px solid rgba(0,180,80,.2);padding:8px 14px;display:flex;align-items:center;justify-content:space-between;cursor:move}}
.braa-title{{font-size:14px;font-weight:bold;color:#00e5ff;letter-spacing:1px}}
.braa-close{{cursor:pointer;color:#666;font-size:14px}}.braa-close:hover{{color:#ff4444}}
.braa-hint{{padding:8px 14px;color:#1a6a30;font-size:11px;border-bottom:1px solid rgba(0,180,80,.1)}}
.braa-list{{padding:4px 0}}
.braa-card{{margin:4px 10px;padding:8px 12px;background:rgba(0,20,8,.6);border:1px solid rgba(0,180,80,.2);border-left:3px solid #00e5ff;border-radius:3px;position:relative}}
.braa-card-hdr{{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px}}
.braa-card-pair{{font-size:11px}}
.braa-card-del{{cursor:pointer;color:#444;font-size:12px;padding:2px 6px}}.braa-card-del:hover{{color:#ff4444}}
.braa-card-data{{display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:4px;text-align:center}}
.braa-d-lbl{{font-size:8px;color:#1a6a30;letter-spacing:1px}}
.braa-d-val{{font-size:16px;font-weight:bold}}
.braa-d-val.b{{color:#00e5ff}}.braa-d-val.r{{color:#ffcc44}}.braa-d-val.a{{color:#22ff44}}.braa-d-val.s{{color:#ff8844}}
.braa-empty{{padding:20px;text-align:center;color:#1a5a2a;font-size:11px}}
/* ── Altitude Filter ── */



/* ── Resize handles for all floating windows ── */
.win-resize{{position:absolute;bottom:0;right:0;width:16px;height:16px;cursor:nwse-resize;opacity:.3;text-align:right;line-height:16px;font-size:10px;color:#44aa66}}
.win-resize:hover{{opacity:.8}}
/* ── TX Indicator overlay ── */
#tx-overlay{{position:fixed;bottom:40px;left:50%;transform:translateX(-50%);z-index:9600;pointer-events:none;display:none}}
#tx-overlay.on{{display:flex;align-items:center;gap:10px;background:rgba(255,60,0,.12);border:1px solid rgba(255,100,0,.5);border-radius:6px;padding:6px 18px;backdrop-filter:blur(4px)}}
#tx-dot{{width:10px;height:10px;border-radius:50%;background:#ff4400;box-shadow:0 0 14px #ff4400;animation:txpulse .6s infinite alternate}}
@keyframes txpulse{{0%{{opacity:1;box-shadow:0 0 8px #ff4400}}100%{{opacity:.6;box-shadow:0 0 20px #ff6600}}}}
#tx-name{{color:#ffaa44;font:bold 13px Consolas;letter-spacing:1px}}
#tx-freq{{color:#ff6633;font:11px Consolas;opacity:.8}}
.r-ch.txing{{border-color:#ff4400 !important;box-shadow:0 0 12px rgba(255,68,0,.4) !important;animation:chtx .5s infinite alternate}}
@keyframes chtx{{0%{{border-color:#ff4400}}100%{{border-color:#ff8800}}}}

/* ── Panel Options ── */
#opt-panel{{position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);background:rgba(3,12,5,.97);border:1px solid #1a5a2a;border-radius:4px;font-family:Consolas,monospace;font-size:13px;color:#aaffcc;padding:0;z-index:99000;width:540px;max-height:90vh;box-shadow:0 8px 40px rgba(0,0,0,.95);display:none;overflow:hidden;flex-direction:column}}
#opt-panel.open{{display:flex}}
.opt-title{{background:rgba(0,30,10,.95);border-bottom:1px solid #1a5a2a;padding:10px 16px;font-size:15px;font-weight:bold;color:#00e5ff;display:flex;align-items:center;justify-content:space-between;cursor:move}}
.opt-close{{cursor:pointer;opacity:.5;font-size:18px;transition:opacity .15s}}
.opt-close:hover{{opacity:1}}
.opt-body{{overflow-y:auto;padding:10px 14px;flex:1}}
.opt-body::-webkit-scrollbar{{width:3px}}
.opt-body::-webkit-scrollbar-thumb{{background:rgba(0,180,80,.2);border-radius:2px}}
.opt-section{{margin-bottom:10px;border:1px solid rgba(26,90,42,.4);border-radius:3px;overflow:hidden}}
.opt-section-hd{{background:rgba(0,20,8,.8);padding:6px 12px;font-size:12px;font-weight:bold;color:#1a8a3a;letter-spacing:.5px;cursor:pointer;user-select:none;display:flex;justify-content:space-between}}
.opt-section-hd:hover{{color:#44cc66}}
.opt-section-body{{padding:10px 14px;background:rgba(0,10,4,.5)}}
.opt-row{{display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;gap:10px}}
.opt-row label{{color:#66aa88;font-size:12px;flex:1;min-width:140px}}
.opt-row input[type=range]{{flex:2;height:5px;accent-color:#00e5ff;cursor:pointer}}
.opt-row input[type=color]{{width:42px;height:26px;border:1px solid #1a5a2a;border-radius:2px;background:transparent;cursor:pointer;padding:1px}}
.opt-row .val-disp{{color:#00e5ff;font-size:12px;min-width:36px;text-align:right}}
.opt-row input[type=checkbox]{{accent-color:#00e5ff;width:16px;height:16px;cursor:pointer}}
.opt-select{{background:rgba(0,12,5,.9);border:1px solid #1a5a2a;color:#aaffcc;font-family:Consolas,monospace;font-size:10px;padding:3px 6px;border-radius:2px;flex:2;cursor:pointer}}

/* BRAA/tips/menus */
#braa-bar{{position:fixed;top:8px;left:50%;transform:translateX(-50%);background:rgba(0,10,4,.88);border:1px solid #1a5a2a;padding:4px 16px;font-family:Consolas,monospace;font-size:12px;font-weight:bold;color:#44cc66;pointer-events:none;z-index:9999;display:none}}
#map-tip{{position:fixed;background:rgba(0,8,4,.9);border:1px solid #1a5a2a;color:#aaffcc;font-family:Consolas,monospace;font-size:10px;padding:3px 9px;pointer-events:none;z-index:99999;border-radius:2px;white-space:nowrap}}
.leaflet-container.ruler-active{{cursor:crosshair!important}}
.cmenu{{position:fixed;background:rgba(4,14,5,.97);border:1px solid #1a5a2a;font-family:Consolas,monospace;font-size:11px;z-index:99999;min-width:170px;box-shadow:0 4px 20px rgba(0,0,0,.9)}}
.cmenu-head{{padding:6px 12px;border-bottom:1px solid #1a5a2a;font-weight:bold;cursor:default}}
.cmenu-item{{padding:5px 12px;cursor:pointer;transition:background .1s}}
.cmenu-item:hover{{background:#0d3d2a;color:#aaffcc!important}}
.cmenu-sep{{height:1px;background:#0d3d2a;margin:2px 0}}

</style>
</head>
<body>
<div id="map"></div>
<div id="hud">
  <div class="h-blue">BLUE  <span id="n-blue">0</span></div>
  <div class="h-red" >RED   <span id="n-red" >0</span></div>
  <div class="h-aam" >AAM   <span id="n-aam" >0</span></div>
  <div class="h-hum" >HUM   <span id="n-hum" >0</span></div>
  <div class="h-scl" >SCL   <span id="scl">—</span></div>
  <div style="color:#1a5a2a;font-size:7px;margin-top:3px">Nebula</div>
</div>
<div id="braa-bar">BRAA: —</div>


<!-- PANNEAU RADIO FLOTTANT -->
<div id="radio-panel" class="hidden">
  <div id="radio-drag-bar">
    <div class="radio-title"><div class="radio-dot"></div>RADIO NEBULA</div>
    <div style="display:flex;align-items:center;gap:8px">
      <span id="radio-status" style="font-size:9px;color:#007a50;letter-spacing:1px">IVC —</span>
      <span class="radio-close" onclick="toggleRadio()">✕</span>
    </div>
  </div>
  <div id="radio-body">
    <div class="r-freq-box">
      <div class="r-freq-lbl">FRÉQUENCE ACTIVE</div>
      <div class="r-freq-val" id="r-freq-val">—</div>
      <div class="r-freq-name" id="r-freq-name">—</div>
      <div class="r-freq-btns">
        <div class="r-btn tx">● TX</div>
        <div class="r-btn" onclick="freqStep(0.025)">▲</div>
        <div class="r-btn" onclick="freqStep(-0.025)">▼</div>
        <div class="r-btn" onclick="selectGuard()">GUARD</div>
      </div>
    </div>
    <div class="r-ch-section">
      <div class="r-sect-lbl">CANAUX PRÉSETS</div>
      <div class="r-ch-grid" id="r-ch-grid"></div>
    </div>
    <div class="r-users-section">
      <div class="r-users-hdr">
        <div class="r-sect-lbl">UTILISATEURS IVC</div>
        <span class="r-badge" id="r-user-count">0 ONLINE</span>
      </div>
      <div id="r-users-list"></div>
    </div>
    <div class="r-audio-section">
      <div class="r-sect-lbl" style="margin-bottom:5px">AUDIO IVC</div>
      <div class="r-audio-row"><span class="r-audio-icon">🎤</span><span class="r-audio-val" id="r-mic-val">—</span></div>
      <div class="r-audio-row"><span class="r-audio-icon">🔊</span><span class="r-audio-val" id="r-spk-val">—</span></div>
    </div>
  </div>
  <div class="win-resize" id="radio-resize">⋯</div>
</div>




<!-- BRAA WINDOW -->
<div id="braa-win">
  <div class="braa-hdr" id="braa-drag">
    <span class="braa-title">📐 BRAA</span>
    <span class="braa-close" onclick="toggleBraaWin()">✕</span>
  </div>
  <div class="braa-hint" id="braa-hint">Clic-droit sur un ALLIÉ → Clic gauche sur un BOGEY</div>
  <div class="braa-list" id="braa-list">
    <div class="braa-empty">Aucun BRAA actif</div>
  </div>
  <div class="win-resize" id="braa-resize">⋱</div>
</div>



<!-- TX INDICATOR -->
<div id="tx-overlay">
  <div id="tx-dot"></div>
  <div id="tx-name">—</div>
  <div id="tx-freq"></div>
</div>

<!-- FRIENDLY FLIGHT STRIP -->
<div id="flt-strip">
  <div class="fs-hdr" id="fs-drag">
    <div><span class="fs-cs" id="fs-cs">—</span><span class="fs-type" id="fs-type"></span></div>
    <span class="fs-close" onclick="closeFltStrip()">✕</span>
  </div>
  <div class="fs-body">
    <div><div class="fs-lbl">SPEED (KT)</div><div class="fs-val spd" id="fs-spd">—</div></div>
    <div><div class="fs-lbl">HEADING</div><div class="fs-val hdg" id="fs-hdg">—</div></div>
    <div><div class="fs-lbl">ALTITUDE (FL)</div><div class="fs-val alt" id="fs-alt">—</div></div>
    <div><div class="fs-lbl">ID CODE</div><div class="fs-val" id="fs-id">—</div></div>
  </div>
</div>

<!-- PANEL OPTIONS -->
<div id="opt-panel">
  <div class="opt-title" id="opt-drag-bar">
    <span>⚙ OPTIONS RADAR</span>
    <span class="opt-close" onclick="closeOptions()">✕</span>
  </div>
  <div class="opt-body">
    <div class="opt-section">
      <div class="opt-section-hd" onclick="toggleSection(this)">COUCHES CARTE <span>▾</span></div>
      <div class="opt-section-body">
        <div class="opt-row"><label>DMZ</label><input type="checkbox" id="lay-dmz" checked onchange="toggleLayer('dmz',this.checked)"></div>
        <div class="opt-row"><label>Pistes</label><input type="checkbox" id="lay-rwy" checked onchange="toggleLayer('runways',this.checked)"></div>
        <div class="opt-row"><label>Labels aéroport</label><input type="checkbox" id="lay-lbl" checked onchange="toggleLayer('labels',this.checked)"></div>
        <div class="opt-row"><label>SAM rings</label><input type="checkbox" id="lay-sam" checked onchange="toggleLayer('sam_rings',this.checked)"></div>
        <div class="opt-row"><label>Lignes FLOT</label><input type="checkbox" id="lay-flot" checked onchange="toggleLayer('flot',this.checked)"></div>
        <div class="opt-row"><label>Trails</label><input type="checkbox" id="lay-trail" checked onchange="toggleLayer('trails',this.checked)"></div>
        <div class="opt-row"><label>Vecteurs vitesse</label><input type="checkbox" id="lay-vel" checked onchange="toggleLayer('velocity',this.checked)"></div>
      </div>
    </div>
    <div class="opt-section">
      <div class="opt-section-hd" onclick="toggleSection(this)">LABELS AÉROPORT <span>▾</span></div>
      <div class="opt-section-body">
        <div class="opt-row"><label>Afficher ICAO</label><input type="checkbox" id="show-icao" checked onchange="applyLabelOpts()"></div>
        <div class="opt-row"><label>Afficher Nom</label><input type="checkbox" id="show-name" checked onchange="applyLabelOpts()"></div>
        <div class="opt-row"><label>Taille ICAO</label><input type="range" id="sz-icao" min="9" max="20" value="13" oninput="applyLabelOpts();this.nextElementSibling.textContent=this.value+'px'"><span class="val-disp">13px</span></div>
        <div class="opt-row"><label>Taille Nom</label><input type="range" id="sz-name" min="7" max="16" value="10" oninput="applyLabelOpts();this.nextElementSibling.textContent=this.value+'px'"><span class="val-disp">10px</span></div>
        <div class="opt-row"><label>Transparence fond</label><input type="range" id="lbl-alpha" min="0" max="100" value="72" oninput="applyLabelOpts();this.nextElementSibling.textContent=this.value+'%'"><span class="val-disp">72%</span></div>
        <div class="opt-row"><label>Couleur ROK</label><input type="color" id="col-rok" value="#00e5ff" onchange="rebuildApts()"></div>
        <div class="opt-row"><label>Couleur DPRK</label><input type="color" id="col-dprk" value="#ff5555" onchange="rebuildApts()"></div>
        <div class="opt-row"><label>Couleur JPN</label><input type="color" id="col-jpn" value="#44cc66" onchange="rebuildApts()"></div>
      </div>
    </div>
    <div class="opt-section">
      <div class="opt-section-hd" onclick="toggleSection(this)">FLIGHT STRIPS <span>▾</span></div>
      <div class="opt-section-body">
        <div class="opt-row"><label>Hauteur</label><input type="range" id="strip-h" min="50" max="100" value="66" oninput="applyStripOpts();this.nextElementSibling.textContent=this.value+'px'"><span class="val-disp">66px</span></div>
        <div class="opt-row"><label>Taille ICAO</label><input type="range" id="strip-icao-sz" min="12" max="28" value="18" oninput="applyStripOpts();this.nextElementSibling.textContent=this.value+'px'"><span class="val-disp">18px</span></div>
        <div class="opt-row"><label>Taille Nom</label><input type="range" id="strip-name-sz" min="8" max="18" value="11" oninput="applyStripOpts();this.nextElementSibling.textContent=this.value+'px'"><span class="val-disp">11px</span></div>
        <div class="opt-row"><label>Taille Valeurs</label><input type="range" id="strip-val-sz" min="8" max="18" value="12" oninput="applyStripOpts();this.nextElementSibling.textContent=this.value+'px'"><span class="val-disp">12px</span></div>
        <div class="opt-row"><label>Taille Labels</label><input type="range" id="strip-lbl-sz" min="6" max="14" value="8" oninput="applyStripOpts();this.nextElementSibling.textContent=this.value+'px'"><span class="val-disp">8px</span></div>
        <div class="opt-row"><label>Transparence</label><input type="range" id="strip-alpha" min="50" max="100" value="96" oninput="applyStripOpts();this.nextElementSibling.textContent=this.value+'%'"><span class="val-disp">96%</span></div>
        <div class="opt-row"><label>Couleur bordure</label><input type="color" id="strip-border" value="#1a4a1a" onchange="applyStripOpts()"></div>
        <div class="opt-row"><label>Couleur labels</label><input type="color" id="strip-lbl-col" value="#1a6a30" onchange="applyStripOpts()"></div>
        <div class="opt-row"><label>Couleur nom apt</label><input type="color" id="strip-name-col" value="#33cc55" onchange="applyStripOpts()"></div>
      </div>
    </div>
    <div class="opt-section">
      <div class="opt-section-hd" onclick="toggleSection(this)">TRACKS — ICÔNES <span>▾</span></div>
      <div class="opt-section-body">
        <div class="opt-row"><label>Taille AMI (□)</label><input type="range" id="cfg-friendSz" min="3" max="14" value="7" oninput="applyCFG();this.nextElementSibling.textContent=this.value"><span class="val-disp">7</span></div>
        <div class="opt-row"><label>Couleur AMI</label><input type="color" id="cfg-friendCol" value="#22ff44" onchange="applyCFG()"></div>
        <div class="opt-row"><label>Taille HOSTILE (◇)</label><input type="range" id="cfg-hostSz" min="3" max="14" value="9" oninput="applyCFG();this.nextElementSibling.textContent=this.value"><span class="val-disp">8</span></div>
        <div class="opt-row"><label>Couleur HOSTILE</label><input type="color" id="cfg-hostCol" value="#ff2222" onchange="applyCFG()"></div>
        <div class="opt-row"><label>Couleur BOGEY</label><input type="color" id="cfg-bogeyCol" value="#ffdd00" onchange="applyCFG()"></div>
        <div class="opt-row"><label>Taille INCONNU (○)</label><input type="range" id="cfg-unkSz" min="3" max="12" value="6" oninput="applyCFG();this.nextElementSibling.textContent=this.value"><span class="val-disp">5</span></div>
        <div class="opt-row"><label>Couleur INCONNU</label><input type="color" id="cfg-unkCol" value="#666666" onchange="applyCFG()"></div>
        <div class="opt-row"><label>Taille MISSILE (▲)</label><input type="range" id="cfg-mslSz" min="2" max="10" value="4" oninput="applyCFG();this.nextElementSibling.textContent=this.value"><span class="val-disp">4</span></div>
        <div class="opt-row"><label>Couleur MISSILE</label><input type="color" id="cfg-mslCol" value="#ff8800" onchange="applyCFG()"></div>
        <div class="opt-row"><label>Vecteur vitesse</label><input type="range" id="cfg-vecMul" min="0" max="30" value="10" oninput="applyCFG();this.nextElementSibling.textContent=(this.value/10).toFixed(1)+'x'"><span class="val-disp">1.0x</span></div>
      </div>
    </div>
    <div class="opt-section">
      <div class="opt-section-hd" onclick="toggleSection(this)">TRACKS — LABELS <span>▾</span></div>
      <div class="opt-section-body">
        <div class="opt-row"><label>Taille callsign</label><input type="range" id="cfg-lblSz" min="8" max="18" value="12" oninput="applyCFG();this.nextElementSibling.textContent=this.value+'px'"><span class="val-disp">11px</span></div>
        <div class="opt-row"><label>Taille données</label><input type="range" id="cfg-subSz" min="7" max="14" value="9" oninput="applyCFG();this.nextElementSibling.textContent=this.value+'px'"><span class="val-disp">9px</span></div>
        <div class="opt-row"><label>Points trail</label><input type="range" id="trail-len" min="3" max="20" value="8" oninput="this.nextElementSibling.textContent=this.value"><span class="val-disp">8</span></div>
        <div class="opt-row"><label>Vecteur (secondes)</label><input type="range" id="vel-len" min="5" max="60" value="20" oninput="this.nextElementSibling.textContent=this.value+'s'"><span class="val-disp">20s</span></div>
      </div>
    </div>
    <div class="opt-section">
      <div class="opt-section-hd" onclick="toggleSection(this)">HUD <span>▾</span></div>
      <div class="opt-section-body">
        <div class="opt-row"><label>Taille texte</label><input type="range" id="hud-sz" min="9" max="18" value="12" oninput="applyHudOpts();this.nextElementSibling.textContent=this.value+'px'"><span class="val-disp">12px</span></div>
        <div class="opt-row"><label>Transparence</label><input type="range" id="hud-alpha" min="0" max="100" value="78" oninput="applyHudOpts();this.nextElementSibling.textContent=this.value+'%'"><span class="val-disp">78%</span></div>
        <div class="opt-row"><label>Couleur BLUE</label><input type="color" id="col-blue" value="#22ff44" onchange="applyHudOpts()"></div>
        <div class="opt-row"><label>Couleur RED</label><input type="color" id="col-red" value="#ff2222" onchange="applyHudOpts()"></div>
        <div class="opt-row"><label>Couleur AAM</label><input type="color" id="col-aam" value="#ff9900" onchange="applyHudOpts()"></div>
      </div>
    </div>
    <div class="opt-section">
      <div class="opt-section-hd" onclick="toggleSection(this)">IVC / RADIO <span>▾</span></div>
      <div class="opt-section-body">
        <div class="opt-row"><label>Microphone</label><select class="opt-select" id="opt-mic" onchange="applyAudioOpts()"><option>— Détecter —</option></select></div>
        <div class="opt-row"><label>Haut-parleur</label><select class="opt-select" id="opt-spk" onchange="applyAudioOpts()"><option>— Détecter —</option></select></div>
        <div class="opt-row"><label>Auto-join canal</label><input type="checkbox" id="opt-autojoin" checked></div>
        <div class="opt-row"><label>Opacité panel</label><input type="range" id="radio-opacity" min="70" max="100" value="97" oninput="document.getElementById('radio-panel').style.opacity=(this.value/100).toFixed(2);this.nextElementSibling.textContent=this.value+'%'"><span class="val-disp">97%</span></div>
      </div>
    </div>
    <div style="padding:10px 12px;border-top:1px solid rgba(0,180,80,.15);text-align:center">
      <div style="padding:16px;border-top:1px solid rgba(0,180,80,.2);text-align:center">
          <img src="data:image/png;base64,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" style="width:64px;height:64px;border-radius:50%;margin-bottom:8px;box-shadow:0 0 20px rgba(0,180,255,.3)"><br>
          <div style="font-size:16px;font-weight:bold;color:#00e5ff;letter-spacing:2px;margin-bottom:6px">NEBULA GCI</div>
          <div style="font-size:12px;color:#44aa66;margin-bottom:3px">By Riesu</div>
          <div style="font-size:12px;color:#44aa66;margin-bottom:3px">contact@falcon-charts.com</div>
          <div style="font-size:11px;color:#1a6a30;margin-top:6px">GNU General Public License v3</div>
          <div style="font-size:10px;color:#1a5a2a;margin-top:2px">Open Source — Made in France 🇫🇷</div>
        </div>
  </div>
</div>

<script>
const AIRPORTS    = {airports_js};
const RUNWAY_DATA = {runways_js};
const DMZ         = {dmz_js};

function cssVar(n,v){{document.documentElement.style.setProperty(n,v);}}
function gv(id){{return document.getElementById(id);}}

function toggleSection(hd){{
  const b=hd.nextElementSibling,o=b.style.display!=='none';
  b.style.display=o?'none':'block';
  hd.querySelector('span').textContent=o?'▸':'▾';
}}

const _layerGroups={{}};
function toggleLayer(name,on){{
  const g=_layerGroups[name]; if(!g)return;
  (Array.isArray(g)?g:[g]).forEach(l=>{{try{{on?map.addLayer(l):map.removeLayer(l);}}catch(e){{}}}}); 
}}

function applyLabelOpts(){{
  cssVar('--lbl-icao-sz',gv('sz-icao').value+'px');
  cssVar('--lbl-name-sz',gv('sz-name').value+'px');
  cssVar('--lbl-alpha',(gv('lbl-alpha').value/100).toFixed(2));
  document.querySelectorAll('.apt-tac-icao').forEach(e=>e.style.display=gv('show-icao').checked?'':'none');
  document.querySelectorAll('.apt-tac-name').forEach(e=>e.style.display=gv('show-name').checked?'':'none');
}}
function applyStripOpts(){{
  cssVar('--strip-h',gv('strip-h').value+'px');
  cssVar('--strip-icao-sz',gv('strip-icao-sz').value+'px');
  cssVar('--strip-name-sz',gv('strip-name-sz').value+'px');
  cssVar('--strip-val-sz',gv('strip-val-sz').value+'px');
  cssVar('--strip-lbl-sz',gv('strip-lbl-sz').value+'px');
  cssVar('--strip-alpha',(gv('strip-alpha').value/100).toFixed(2));
  cssVar('--strip-border',gv('strip-border').value);
  cssVar('--strip-lbl-col',gv('strip-lbl-col').value);
  const nc=gv('strip-name-col').value;
  document.querySelectorAll('.fstrip-name').forEach(e=>e.style.color=nc);
}}
function applyHudOpts(){{
  cssVar('--hud-sz',gv('hud-sz').value+'px');
  cssVar('--hud-alpha',(gv('hud-alpha').value/100).toFixed(2));
  cssVar('--col-blue',gv('col-blue').value);
  cssVar('--col-red',gv('col-red').value);
  cssVar('--col-aam',gv('col-aam').value);
}}
function applyCFG(){{
  CFG.friendSz=parseInt(gv('cfg-friendSz').value);
  CFG.hostSz=parseInt(gv('cfg-hostSz').value);
  CFG.unkSz=parseInt(gv('cfg-unkSz').value);
  CFG.mslSz=parseInt(gv('cfg-mslSz').value);
  CFG.friendCol=gv('cfg-friendCol').value;
  CFG.hostCol=gv('cfg-hostCol').value;
  CFG.unkCol=gv('cfg-unkCol').value;
  CFG.bogeyCol=gv('cfg-bogeyCol').value;
  CFG.mslCol=gv('cfg-mslCol').value;
  CFG.vecMul=parseInt(gv('cfg-vecMul').value)/10;
  CFG.lblSz=gv('cfg-lblSz').value+'px';
  CFG.subSz=gv('cfg-subSz').value+'px';
  updateAllTrackIcons();
}}
function applyAudioOpts(){{
  gv('r-mic-val').textContent=gv('opt-mic').value;
  gv('r-spk-val').textContent=gv('opt-spk').value;
}}

async function detectAudioDevices(){{
  try{{
    const devs=await navigator.mediaDevices.enumerateDevices();
    const ms=gv('opt-mic'),ss=gv('opt-spk');
    ms.innerHTML='';ss.innerHTML='';
    devs.forEach(d=>{{
      const o=document.createElement('option');
      o.value=d.deviceId;o.textContent=d.label||d.deviceId.slice(0,20);
      if(d.kind==='audioinput')ms.appendChild(o);
      if(d.kind==='audiooutput')ss.appendChild(o.cloneNode(true));
    }});
    applyAudioOpts();
  }}catch(e){{}}
}}

function openOptions(){{gv('opt-panel').classList.add('open');detectAudioDevices();}}
function closeOptions(){{gv('opt-panel').classList.remove('open');}}

(function(){{
  const p=gv('opt-panel'),b=gv('opt-drag-bar');
  let mx=0,my=0,on=false;
  b.addEventListener('mousedown',e=>{{if(e.target.classList.contains('opt-close'))return;on=true;p.style.transform='none';mx=e.clientX-p.offsetLeft;my=e.clientY-p.offsetTop;document.body.style.userSelect='none';e.preventDefault();}});
  document.addEventListener('mousemove',e=>{{if(!on)return;p.style.left=Math.max(0,e.clientX-mx)+'px';p.style.top=Math.max(0,e.clientY-my)+'px';}});
  document.addEventListener('mouseup',()=>{{on=false;document.body.style.userSelect='';}});
}})();

// ── Carte ────────────────────────────────────────────────────────────────────
const map=L.map('map',{{preferCanvas:true,zoomControl:false,attributionControl:false}}).setView([37.5,127.5],7);
const darkTile=L.tileLayer('https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png',{{maxZoom:19,subdomains:'abcd',keepBuffer:4}}).addTo(map);
darkTile.once('tileerror',()=>{{map.removeLayer(darkTile);L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png',{{maxZoom:19}}).addTo(map);}});

const dmzLayer=L.polyline(DMZ,{{color:'#cc4400',weight:2,opacity:.7,dashArray:'10 6'}}).addTo(map);
_layerGroups['dmz']=dmzLayer;
const rwyLayers=[];
RUNWAY_DATA.forEach(r=>{{
  const nk=r.icao.startsWith('KP-')||r.icao.startsWith('ZK');
  const p=L.polygon(r.c,{{color:nk?'rgba(255,80,80,.85)':'rgba(80,180,140,.85)',fillColor:nk?'rgba(180,40,40,.2)':'rgba(40,120,80,.18)',fillOpacity:1,weight:1.5,interactive:false}}).addTo(map);
  const mA=[(r.c[0][0]+r.c[1][0])/2,(r.c[0][1]+r.c[1][1])/2],mB=[(r.c[2][0]+r.c[3][0])/2,(r.c[2][1]+r.c[3][1])/2];
  const a=L.polyline([mA,mB],{{color:nk?'rgba(255,100,100,.45)':'rgba(80,200,140,.38)',weight:1,dashArray:'5 4',interactive:false}}).addTo(map);
  rwyLayers.push(p,a);
}});
_layerGroups['runways']=rwyLayers;

// ── Aéroports ────────────────────────────────────────────────────────────────
let openStrips={{}},aptMarkerLayers=[];
function aptCol(ap){{
  if(ap.icao.startsWith('KP-')||ap.icao.startsWith('ZK'))return gv('col-dprk')?gv('col-dprk').value:'#ff5555';
  if(ap.icao.startsWith('RJ'))return gv('col-jpn')?gv('col-jpn').value:'#44cc66';
  return gv('col-rok')?gv('col-rok').value:'#00e5ff';
}}
function buildStrip(ap){{
  const col=aptCol(ap),nc=gv('strip-name-col')?gv('strip-name-col').value:'#33cc55';
  const rwys=(ap.runways||[]).slice(0,2);
  const freqs=ap.freqs||{{}};
  const rwyHtml=rwys.length?rwys.map(r=>`<div style="margin-bottom:2px"><div class="fstrip-lbl">${{r[3]||'RWY'}}</div><div class="fstrip-val" style="color:#aaffcc">${{r[1]}}FT</div></div>`).join(''):`<div class="fstrip-val" style="color:#333">—</div>`;
  const frqHtml=['TWR','APP','GND','ATIS'].filter(k=>freqs[k]).slice(0,3).map(k=>`<div style="display:flex;gap:5px;align-items:baseline;margin-bottom:2px"><span class="fstrip-lbl" style="min-width:26px">${{k}}</span><span class="fstrip-val" style="color:#88ccff;cursor:pointer" onclick="radioSelectFreq('${{freqs[k]}}')">${{freqs[k]}}</span></div>`).join('')||`<div class="fstrip-val" style="color:#333">—</div>`;
  const el=document.createElement('div');el.className='fstrip';el.dataset.icao=ap.icao;
  el.innerHTML=`<div class="fstrip-accent" style="background:${{col}}"></div>
    <div class="fstrip-drag">
      <div class="fstrip-cell" style="min-width:86px"><div class="fstrip-icao" style="color:${{col}}">${{ap.icao}}</div><div class="fstrip-name" style="color:${{nc}}">${{ap.name}}</div></div>
      <div class="fstrip-cell"><div class="fstrip-lbl">TCN</div><div class="fstrip-val" style="color:#ffdd88">${{ap.tacan||'—'}}</div><div class="fstrip-lbl" style="margin-top:3px">ELEV</div><div class="fstrip-val" style="color:#aaffcc;font-size:10px">${{ap.elev_ft||'?'}}FT</div></div>
      <div class="fstrip-cell" style="min-width:96px">${{rwyHtml}}</div>
      <div class="fstrip-cell grow">${{frqHtml}}</div>
    </div>
    <div class="fstrip-resize">⋮</div>
    <div class="fstrip-close" style="color:${{col}}" onclick="closeStrip('${{ap.icao}}')">✕</div>`;
  const drag=el.querySelector('.fstrip-drag');
  let mx2=0,my2=0,mv=false;
  drag.addEventListener('mousedown',ev=>{{mv=true;mx2=ev.clientX-el.offsetLeft;my2=ev.clientY-el.offsetTop;document.body.style.userSelect='none';ev.preventDefault();}});
  document.addEventListener('mousemove',ev=>{{if(!mv)return;el.style.left=Math.max(0,ev.clientX-mx2)+'px';el.style.top=Math.max(0,ev.clientY-my2)+'px';}});
  document.addEventListener('mouseup',()=>{{mv=false;document.body.style.userSelect='';}});
  const rz=el.querySelector('.fstrip-resize');
  let rz_on=false,rz_x=0,rz_w=0;
  rz.addEventListener('mousedown',ev=>{{rz_on=true;rz_x=ev.clientX;rz_w=el.offsetWidth;ev.stopPropagation();ev.preventDefault();}});
  document.addEventListener('mousemove',ev=>{{if(!rz_on)return;el.style.width=Math.max(540,rz_w+(ev.clientX-rz_x))+'px';}});
  document.addEventListener('mouseup',()=>{{rz_on=false;}});
  return el;
}}
function toggleStrip(icao){{
  if(openStrips[icao]){{closeStrip(icao);return;}}
  const ap=AIRPORTS.find(a=>a.icao===icao);if(!ap)return;
  const el=buildStrip(ap);
  const W=Math.min(window.innerWidth-40,700),offs=Object.keys(openStrips).length;
  el.style.left=Math.round((window.innerWidth-W)/2)+'px';
  el.style.top=(55+offs*72)+'px';el.style.width=W+'px';
  document.body.appendChild(el);openStrips[icao]=el;
}}
function closeStrip(icao){{if(openStrips[icao]){{openStrips[icao].remove();delete openStrips[icao];}}}}
function rebuildApts(){{aptMarkerLayers.forEach(l=>{{try{{map.removeLayer(l);}}catch(e){{}}}}); aptMarkerLayers=[];renderApts();}}
function renderApts(){{
  var aptIcons=[],aptIcaoLbls=[],aptNameLbls=[];
  AIRPORTS.forEach(function(ap){{
    var col=aptCol(ap),sz=12;
    var mIcon=L.marker([ap.lat,ap.lon],{{icon:L.divIcon({{html:'<svg xmlns="http://www.w3.org/2000/svg" width="'+sz+'" height="'+sz+'" viewBox="0 0 '+sz+' '+sz+'" style="display:block;cursor:pointer;overflow:visible"><polygon points="'+sz/2+',0.5 '+(sz-0.5)+','+sz/2+' '+sz/2+','+(sz-0.5)+' 0.5,'+sz/2+'" fill="'+col+'" fill-opacity=".92" stroke="rgba(0,0,0,.5)" stroke-width="1"/></svg>',className:'leaflet-div-icon-clean',iconSize:[sz,sz],iconAnchor:[sz/2,sz/2]}}),zIndexOffset:10}}).addTo(map);
    mIcon.on('click',function(e){{L.DomEvent.stopPropagation(e);toggleStrip(ap.icao);if(window._pyBridge)window._pyBridge.onAptClick(ap.icao);}});
    aptIcons.push(mIcon);
    var mIcao=L.marker([ap.lat,ap.lon],{{icon:L.divIcon({{html:'<div class="apt-tac" style="cursor:pointer"><div class="apt-tac-box" style="color:'+col+'"><div class="apt-tac-icao">'+ap.icao+'</div></div></div>',className:'leaflet-div-icon-clean',iconSize:[80,16],iconAnchor:[-10,8]}}),zIndexOffset:5,interactive:true}}).addTo(map);
    mIcao.on('click',function(){{toggleStrip(ap.icao);}});
    aptIcaoLbls.push(mIcao);
    var mName=L.marker([ap.lat,ap.lon],{{icon:L.divIcon({{html:'<div style="color:'+col+';font:10px Consolas;opacity:.7;white-space:nowrap;pointer-events:none;margin-top:13px;margin-left:-10px">'+ap.name+'</div>',className:'leaflet-div-icon-clean',iconSize:[120,14],iconAnchor:[-10,-6]}}),zIndexOffset:4,interactive:false}}).addTo(map);
    aptNameLbls.push(mName);
    aptMarkerLayers.push(mIcon,mIcao,mName);
  }});
  _layerGroups['labels']=aptIcons;
  _layerGroups['apt_icao']=aptIcaoLbls;
  _layerGroups['apt_name']=aptNameLbls;
}}
renderApts();

// ── Tracks ────────────────────────────────────────────────────────────────────
let trackMarkers={{}},trackLabels={{}},trackTrails={{}},trackVectors={{}},trackData={{}};
let braaRefUid=null,selUid=null;
const ID_COLORS={{'FRIENDLY':'#22ff44','ASSUMED FRIEND':'#44ff88','NEUTRAL':'#aaaaaa','UNKNOWN':'#666666','SUSPECT':'#ffaa00','HOSTILE':'#ff4444','BANDIT':'#ff2222','BOGEY':'#ffdd00'}};
let CFG={{friendSz:7,hostSz:9,unkSz:6,mslSz:4,friendCol:'#22ff44',hostCol:'#ff2222',unkCol:'#888888',bogeyCol:'#ffdd00',mslCol:'#ff8800',vecMul:1.0,lblSz:'12px',subSz:'10px'}};
function trkCol(t){{
  if(t.id_code==='FRIENDLY'||t.id_code==='ASSUMED FRIEND') return CFG.friendCol;
  if(t.id_code==='HOSTILE'||t.id_code==='BANDIT') return CFG.hostCol;
  if(t.id_code==='BOGEY') return CFG.bogeyCol;
  if(t.id_code==='SUSPECT') return '#ffaa00';
  if(t.coalition==='Blue'||t.coalition==='Allies') return CFG.friendCol;
  if(t.coalition==='Red'||t.coalition==='Enemies') return CFG.hostCol;
  return CFG.unkCol;
}}
function isFriendly(t){{return t.coalition==='Blue'||t.coalition==='Allies'||t.id_code==='FRIENDLY'||t.id_code==='ASSUMED FRIEND';}}
function isHostile(t){{return t.coalition==='Red'||t.coalition==='Enemies'||t.id_code==='HOSTILE'||t.id_code==='BANDIT'||t.id_code==='BOGEY'||t.id_code==='SUSPECT';}}
function makeTrackSvg(t,sel){{
  const c=trkCol(t),vSz=60,half=vSz/2,hdg=t.hdg||0,isRef=(braaRefUid===t.uid),hum=t.is_human;
  let shape='',sz=6;
  if(t.is_missile){{sz=CFG.mslSz;const mc=CFG.mslCol;shape=`<line x1="0" y1="${{sz}}" x2="0" y2="${{sz+10}}" stroke="${{mc}}" stroke-width="1.5" opacity=".3" stroke-dasharray="2 2"/><polygon points="0,${{-sz}} ${{sz*0.5}},${{sz*0.4}} ${{-sz*0.5}},${{sz*0.4}}" fill="${{mc}}" fill-opacity=".95" stroke="#fff" stroke-width="0.3"/><circle cx="0" cy="${{-sz-2}}" r="1.5" fill="${{mc}}" opacity=".6"/>`;
  }}else if(isFriendly(t)){{sz=hum?CFG.friendSz+1:CFG.friendSz;const sw=hum?2:1.3;shape=`<rect x="${{-sz}}" y="${{-sz}}" width="${{sz*2}}" height="${{sz*2}}" fill="none" stroke="${{c}}" stroke-width="${{sw}}"/>`;
  }}else if(isHostile(t)){{sz=hum?CFG.hostSz+1:CFG.hostSz;const sw=hum?2:1.3;shape=`<polygon points="0,${{-sz}} ${{sz}},0 0,${{sz}} ${{-sz}},0" fill="none" stroke="${{c}}" stroke-width="${{sw}}"/>`;
  }}else{{sz=CFG.unkSz;shape=`<circle cx="0" cy="0" r="${{sz}}" fill="none" stroke="${{c}}" stroke-width="1.2"/>`;}}
  const vl=(t.speed_kts>10&&!t.is_missile)?Math.min(25,5+t.speed_kts/20)*CFG.vecMul:0;
  const vec=vl>0?`<line x1="0" y1="0" x2="0" y2="${{-vl}}" stroke="${{c}}" stroke-width="1" opacity=".6"/>`:'';
  const sR=sel?`<circle cx="0" cy="0" r="${{sz+5}}" fill="none" stroke="#fff" stroke-width="1" opacity=".4" stroke-dasharray="3 2"/>`:'';
  const rR=isRef?`<circle cx="0" cy="0" r="${{sz+6}}" fill="none" stroke="#00ff88" stroke-width="1.5" stroke-dasharray="4 3" opacity=".7"/>`:'';
  return`<svg xmlns="http://www.w3.org/2000/svg" width="${{vSz}}" height="${{vSz}}" viewBox="${{-half}} ${{-half}} ${{vSz}} ${{vSz}}"><g transform="rotate(${{hdg}},0,0)">${{vec}}${{shape}}</g>${{sR}}${{rR}}</svg>`;
}}
function makeLabelHtml(t){{
  var c=trkCol(t),lbl=t.display_label||t.uid.slice(-4);
  var grp=t.group?'<div style="color:'+c+';opacity:.5;font-size:8px">'+t.group+'</div>':'';
  var fl=t.alt_ft?Math.round(Math.abs(t.alt_ft)/100):0;
  var spd=(t.speed_kts>10)?Math.round(t.speed_kts):0;
  var p=[];if(spd)p.push(spd);if(fl)p.push(fl);
  var sub=p.length?'<div style="color:'+c+';opacity:.7;font-size:'+CFG.subSz+'">'+p.join('  ')+'</div>':'';
  return'<div class="trk-lbl"><div style="color:'+c+';font-size:'+CFG.lblSz+';font-weight:'+(t.is_human?'700':'400')+'">'+lbl+'</div>'+grp+sub+'</div>';
}}
function updateTrail(t){{
  const trail=t.trail||[];
  if(trackTrails[t.uid]){{try{{map.removeLayer(trackTrails[t.uid]);}}catch(e){{}}delete trackTrails[t.uid];}}
  if(!gv('lay-trail')||!gv('lay-trail').checked||trail.length<2)return;
  const c=trkCol(t),segs=[];
  for(let i=0;i<trail.length-1;i++){{
    segs.push(L.polyline([trail[i],trail[i+1]],{{color:c,weight:1.5,opacity:0.08+0.55*(i/(trail.length-1)),dashArray:i<trail.length-3?'3 2':null,interactive:false}}));
  }}
  trackTrails[t.uid]=L.layerGroup(segs).addTo(map);
}}
function updateVector(t){{
  if(trackVectors[t.uid]){{try{{map.removeLayer(trackVectors[t.uid]);}}catch(e){{}}delete trackVectors[t.uid];}}
  if(!gv('lay-vel')||!gv('lay-vel').checked||!(t.speed_kts>10)||t.is_missile)return;
  const secs=parseInt(gv('vel-len')?gv('vel-len').value:20);
  const nm=t.speed_kts*(secs/3600);
  const hdgR=(t.hdg||0)*Math.PI/180;
  const dLat=nm/60*Math.cos(hdgR),dLon=nm/60*Math.sin(hdgR)/Math.cos(t.lat*Math.PI/180);
  trackVectors[t.uid]=L.polyline([[t.lat,t.lon],[t.lat+dLat,t.lon+dLon]],{{color:trkCol(t),weight:1.5,opacity:.55,interactive:false,dashArray:'6 3'}}).addTo(map);
}}
function updateTrack(t){{
  if(!t.lat||!t.alive){{removeTrack(t.uid);return;}}
  const ll=[t.lat,t.lon],sz=60;
  updateTrail(t);updateVector(t);
  if(t.moved||!trackMarkers[t.uid]){{
    const ic=L.divIcon({{html:makeTrackSvg(t,t.uid===selUid),className:'leaflet-div-icon-clean',iconSize:[sz,sz],iconAnchor:[sz/2,sz/2]}});
    if(trackMarkers[t.uid]){{trackMarkers[t.uid].setLatLng(ll);trackMarkers[t.uid].setIcon(ic);}}
    else{{
      const m=L.marker(ll,{{icon:ic,zIndexOffset:100}}).addTo(map);
      m.on('click',e=>{{L.DomEvent.stopPropagation(e);if(e.originalEvent.ctrlKey){{braaRefUid=t.uid;updateAllTrackIcons();if(window._pyBridge)window._pyBridge.onBraaRef(t.uid,t.display_label,trkCol(t));}}else{{selUid=t.uid;updateAllTrackIcons();openFltStrip(t.uid);if(_braaPending)braaTrackClick(t.uid);if(window._pyBridge)window._pyBridge.onTrackClick(t.uid);}}}});
      m.on('contextmenu',e=>{{L.DomEvent.stopPropagation(e);showTrackMenu(t,e.containerPoint);}});
      trackMarkers[t.uid]=m;
    }}
    const lic=L.divIcon({{html:makeLabelHtml(t),className:'leaflet-div-icon-clean',iconSize:[160,36],iconAnchor:[-14,8]}});
    if(trackLabels[t.uid]){{trackLabels[t.uid].setLatLng(ll);trackLabels[t.uid].setIcon(lic);}}
    else{{trackLabels[t.uid]=L.marker(ll,{{icon:lic,zIndexOffset:-10,interactive:false}}).addTo(map);}}
  }}
  trackData[t.uid]=t;
}}
function removeTrack(uid){{
  [trackMarkers,trackLabels].forEach(s=>{{if(s[uid]){{try{{map.removeLayer(s[uid]);}}catch(e){{}}delete s[uid];}}}});
  [trackTrails,trackVectors].forEach(s=>{{if(s[uid]){{try{{map.removeLayer(s[uid]);}}catch(e){{}}delete s[uid];}}}});
  delete trackData[uid];
}}
function updateAllTrackIcons(){{
  const sz=60;
  Object.values(trackData).forEach(t=>{{if(trackMarkers[t.uid])trackMarkers[t.uid].setIcon(L.divIcon({{html:makeTrackSvg(t,t.uid===selUid),className:'leaflet-div-icon-clean',iconSize:[sz,sz],iconAnchor:[sz/2,sz/2]}}));}});
}}

// ── Context menu ──────────────────────────────────────────────────────────────
let _ctxEl=null;
function showTrackMenu(t,pt){{
  closeCtx();
  const col=trkCol(t),ids=['FRIENDLY','ASSUMED FRIEND','NEUTRAL','UNKNOWN','SUSPECT','HOSTILE','BANDIT','BOGEY'];
  const d=document.createElement('div');d.className='cmenu';d.style.cssText=`left:${{pt.x}}px;top:${{pt.y}}px`;
  d.innerHTML=`<div class="cmenu-head" style="color:${{col}}">${{t.display_label}} <span style="opacity:.5;font-size:9px">${{t.name}}</span></div>
    <div class="cmenu-item" style="color:#00ff88" onclick="setBraaRef('${{t.uid}}')">⊕ Set BRAA Ref</div>
    <div class="cmenu-sep"></div>
    ${{ids.map(id=>`<div class="cmenu-item" onclick="setTrkId('${{t.uid}}','${{id}}')" style="color:${{ID_COLORS[id]||'#aaa'}}">${{id}}</div>`).join('')}}
    <div class="cmenu-sep"></div><div class="cmenu-item" style="color:#00e5ff" onclick="braaSetSource(''+uid+'')">📐 BRAA depuis ce contact</div><div class="cmenu-item" style="color:#555" onclick="closeCtx()">Annuler</div>`;
  document.body.appendChild(d);_ctxEl=d;
  setTimeout(()=>document.addEventListener('click',closeCtx,{{once:true}}),10);
}}
function closeCtx(){{if(_ctxEl){{_ctxEl.remove();_ctxEl=null;}}}}
function setTrkId(uid,id){{closeCtx();if(window._pyBridge)window._pyBridge.onIdChange(uid,id);}}
function setBraaRef(uid){{closeCtx();const t=trackData[uid];if(!t)return;braaRefUid=uid;updateAllTrackIcons();if(window._pyBridge)window._pyBridge.onBraaRef(uid,t.display_label,trkCol(t));}}

// ── HUD ───────────────────────────────────────────────────────────────────────
function updateHud(d){{
  gv('n-blue').textContent=d.n_blue;gv('n-red').textContent=d.n_red;
  gv('n-aam').textContent=d.n_aam;gv('n-hum').textContent=d.n_hum;
  gv('scl').textContent=Math.round(20000/Math.pow(2,map.getZoom()))+'NM';
}}

// ── Règle de mesure ───────────────────────────────────────────────────────────
let rulerOn=false,rStart=null,rLine=null,rLbl=null,rDot=null;
function hmNm(a,b){{const R=3440.065,f1=a.lat*Math.PI/180,f2=b.lat*Math.PI/180,df=(b.lat-a.lat)*Math.PI/180,dl=(b.lng-a.lng)*Math.PI/180,x=Math.sin(df/2)**2+Math.cos(f1)*Math.cos(f2)*Math.sin(dl/2)**2;return 2*R*Math.atan2(Math.sqrt(x),Math.sqrt(1-x));}}
function brg(a,b){{const f1=a.lat*Math.PI/180,f2=b.lat*Math.PI/180,dl=(b.lng-a.lng)*Math.PI/180;return((Math.atan2(Math.sin(dl)*Math.cos(f2),Math.cos(f1)*Math.sin(f2)-Math.sin(f1)*Math.cos(f2)*Math.cos(dl))*180/Math.PI)+360)%360;}}
function updRuler(to){{
  if(!rStart)return;
  [rLine,rLbl].forEach(l=>{{if(l)try{{map.removeLayer(l);}}catch(e){{}}}});
  rLine=L.polyline([rStart,to],{{color:'#ffdd00',weight:2,opacity:.85,dashArray:'10 5',interactive:false}}).addTo(map);
  const nm=hmNm(rStart,to),b1=brg(rStart,to),b2=(b1+180)%360,mid=L.latLng((rStart.lat+to.lat)/2,(rStart.lng+to.lng)/2);
  var t250=nm>0?(nm/250*60).toFixed(0)+'min @250kt':'';var t400=nm>0?(nm/400*60).toFixed(0)+'min @400kt':'';
  rLbl=L.marker(mid,{{icon:L.divIcon({{html:'<div style="background:rgba(0,8,4,.92);border:1px solid #ffdd00;border-radius:2px;padding:4px 12px;font-family:Consolas,monospace;pointer-events:none;white-space:nowrap"><div style="color:#ffdd00;font-size:13px;font-weight:bold">'+String(Math.round(b1)).padStart(3,'0')+'° / '+String(Math.round(b2)).padStart(3,'0')+'°</div><div style="color:#fff;font-size:16px;font-weight:bold">'+nm.toFixed(1)+' NM</div><div style="color:#aaa;font-size:10px">'+(nm*1.852).toFixed(1)+' km</div><div style="color:#88ccff;font-size:9px;margin-top:2px">'+t250+'  '+t400+'</div></div>',className:'leaflet-div-icon-clean',iconSize:[160,80],iconAnchor:[80,40]}}),interactive:false,zIndexOffset:9000}}).addTo(map);
}}
function clearRuler(){{
  [rLine,rLbl,rDot].forEach(l=>{{if(l)try{{map.removeLayer(l);}}catch(e){{}}}});
  rLine=rLbl=rDot=rStart=null;rulerOn=false;map.getContainer().classList.remove('ruler-active');
}}
document.addEventListener('contextmenu',e=>e.preventDefault());
map.on('contextmenu',e=>{{L.DomEvent.stopPropagation(e);closeCtx();if(rulerOn){{clearRuler();return;}}rulerOn=true;rStart=e.latlng;map.getContainer().classList.add('ruler-active');rDot=L.circleMarker(rStart,{{radius:5,color:'#ffdd00',fillColor:'#ffdd00',fillOpacity:1,weight:2,interactive:false}}).addTo(map);}});
map.on('mousemove',e=>{{if(window._pyBridge)window._pyBridge.onCursorMove(e.latlng.lat,e.latlng.lng);if(rulerOn&&rStart)updRuler(e.latlng);}});
map.on('click',e=>{{if(rulerOn){{updRuler(e.latlng);rulerOn=false;map.getContainer().classList.remove('ruler-active');closeMapTip();return;}}selUid=null;updateAllTrackIcons();closeCtx();}});
let _tipEl=null;
function showMapTip(pt,msg){{closeMapTip();const d=document.createElement('div');d.id='map-tip';d.style.cssText=`left:${{pt.x+14}}px;top:${{pt.y-10}}px`;d.textContent=msg;document.body.appendChild(d);_tipEl=d;}}
function closeMapTip(){{if(_tipEl){{_tipEl.remove();_tipEl=null;}}}}
document.addEventListener('keydown',e=>{{if(e.key==='Escape'){{clearRuler();closeCtx();closeMapTip();braaRefUid=null;updateAllTrackIcons();}}}});

// ── receiveTracks / setMission ────────────────────────────────────────────────
function receiveTracks(data){{
  const seen=new Set();
  (data.tracks||[]).forEach(t=>{{updateTrack(t);seen.add(t.uid);}});
  Object.keys(trackMarkers).forEach(uid=>{{if(!seen.has(uid))removeTrack(uid);}});
  updateHud(data);
}}

let _msnGroup=null;
function setMission(m){{
  if(_msnGroup){{try{{map.removeLayer(_msnGroup);}}catch(e){{}}}}_msnGroup=null;
  var layers=[];
  if(m.bullseye){{var b=m.bullseye;
    layers.push(L.polyline([[b.lat-.15,b.lon],[b.lat+.15,b.lon]],{{color:'#4488ff',weight:1.5,opacity:.6,interactive:false}}));
    layers.push(L.polyline([[b.lat,b.lon-.2],[b.lat,b.lon+.2]],{{color:'#4488ff',weight:1.5,opacity:.6,interactive:false}}));
    layers.push(L.circleMarker([b.lat,b.lon],{{radius:8,color:'#4488ff',fill:false,weight:2,interactive:false}}));
    layers.push(L.circleMarker([b.lat,b.lon],{{radius:18,color:'#4488ff',fill:false,weight:1,opacity:.3,interactive:false}}));
    layers.push(L.marker([b.lat,b.lon],{{icon:L.divIcon({{html:'<div style="color:#4488ff;font:bold 11px Consolas;background:rgba(0,8,4,.8);padding:1px 6px">BULL</div>',className:'leaflet-div-icon-clean',iconSize:[40,16],iconAnchor:[-12,8]}}),interactive:false,zIndexOffset:50}}));
  }}
  (m.ref_points||[]).forEach(function(r){{
    layers.push(L.circleMarker([r.lat,r.lon],{{radius:4,color:'#ffaa44',fillColor:'#ffaa44',fillOpacity:.6,weight:1.5,interactive:false}}));
    layers.push(L.marker([r.lat,r.lon],{{icon:L.divIcon({{html:'<div style="color:#ffaa44;font:bold 10px Consolas">'+r.name+'</div>',className:'leaflet-div-icon-clean',iconSize:[60,16],iconAnchor:[-8,8]}}),interactive:false,zIndexOffset:15}}));
  }});
  (m.line_segments||[]).forEach(function(s){{if(s.length<2)return;
    layers.push(L.polyline(s.map(function(p){{return[p.lat,p.lon];}}),{{color:'#4488ff',weight:1.5,dashArray:'8 4',opacity:.5,interactive:false}}));
  }});
  if(m.route&&m.route.length>1)
    layers.push(L.polyline(m.route.map(function(p){{return[p.lat,p.lon];}}),{{color:'#4488ff',weight:2,dashArray:'8 4',opacity:.6,interactive:false}}));
  _msnGroup=L.layerGroup(layers).addTo(map);
  var threats=m.threats||[];
  function _nextSAM(i){{
    if(i>=threats.length)return;
    var t=threats[i];
    if(t.range_m&&t.range_m>=500){{
      _msnGroup.addLayer(L.circle([t.lat,t.lon],{{radius:t.range_m,color:'rgba(255,60,0,.35)',fillColor:'rgba(255,40,0,.03)',fillOpacity:1,weight:1.5,dashArray:'6 3',interactive:false}}));
      _msnGroup.addLayer(L.circleMarker([t.lat,t.lon],{{radius:4,color:'#ff4400',fillColor:'#ff4400',fillOpacity:.8,weight:1,interactive:false}}));
      _msnGroup.addLayer(L.marker([t.lat,t.lon],{{icon:L.divIcon({{html:'<div style="color:#ff6633;font:bold 10px Consolas">'+t.name+'<br><span style="font-size:8px;color:#ff4400">'+t.range_nm+'NM</span></div>',className:'leaflet-div-icon-clean',iconSize:[60,28],iconAnchor:[-6,8]}}),interactive:false,zIndexOffset:20}}));
    }}
    setTimeout(function(){{_nextSAM(i+1);}},60);
  }}
  setTimeout(function(){{_nextSAM(0);}},100);
}}

// ── Panneau RADIO ────────────────────────────────────────────────────────────
function toggleRadio(){{
  gv('radio-panel').classList.toggle('hidden');
}}
(function(){{
  const p=gv('radio-panel'),b=gv('radio-drag-bar');
  let mx=0,my=0,on=false;
  b.addEventListener('mousedown',e=>{{if(e.target.classList.contains('radio-close'))return;on=true;p.style.right='auto';mx=e.clientX-p.offsetLeft;my=e.clientY-p.offsetTop;document.body.style.userSelect='none';e.preventDefault();}});
  document.addEventListener('mousemove',e=>{{if(!on)return;p.style.left=Math.max(0,e.clientX-mx)+'px';p.style.top=Math.max(0,e.clientY-my)+'px';}});
  document.addEventListener('mouseup',()=>{{on=false;document.body.style.userSelect='';}});
}})();
(function(){{
  const p=gv('radio-panel'),h=gv('radio-resize');
  let on=false,sy=0,sh=0;
  h.addEventListener('mousedown',e=>{{on=true;sy=e.clientY;sh=p.offsetHeight;document.body.style.userSelect='none';e.preventDefault();}});
  document.addEventListener('mousemove',e=>{{if(!on)return;p.style.maxHeight=Math.max(200,sh+(e.clientY-sy))+'px';}});
  document.addEventListener('mouseup',()=>{{on=false;document.body.style.userSelect='';}});
}})();

const DEFAULT_CHANNELS=[
  {{id:'ch1',freq:'225.000',name:'GCI PRI'}},{{id:'ch2',freq:'234.500',name:'GCI SEC'}},
  {{id:'ch3',freq:'243.000',name:'GUARD'}},{{id:'ch4',freq:'257.800',name:'RKSG TWR'}},
  {{id:'ch5',freq:'269.100',name:'RKSG APP'}},{{id:'ch6',freq:'270.100',name:'RKTU TWR'}},
  {{id:'ch7',freq:'275.800',name:'RKSG GND'}},{{id:'ch8',freq:'282.500',name:'ATIS'}},
  {{id:'ch9',freq:'311.000',name:'AWACS'}},
];
let _activeFreq='—',_activeChName='—';

function buildRadioChannels(channels){{
  var grid=gv('r-ch-grid');grid.innerHTML='';
  var list=channels.length>0?channels:DEFAULT_CHANNELS;
  list.forEach(function(ch){{
    var isActive=(ch.freq===_activeFreq);
    var isTx=ch.txing||false;
    var d=document.createElement('div');
    d.className='r-ch'+(isActive?' active':'')+(isTx?' txing':'');
    d.innerHTML='<span class="cn">'+(ch.id||'')+'</span><span class="cf">'+(ch.freq||ch.name)+'</span><span class="ck">'+(ch.name||'')+'</span>';
    d.onclick=function(){{radioJoinChannel(ch.id||ch.freq,ch.freq,ch.name);}};
    grid.appendChild(d);
  }});
}}

function radioJoinChannel(chId,freq,name){{
  _activeFreq=freq;_activeChName=name;
  gv('r-freq-val').textContent=freq;gv('r-freq-name').textContent=name;
  buildRadioChannels([]);
  if(window._pyBridge){{window._pyBridge.onRadioJoin(chId);window._pyBridge.onRadioFreq(freq);}}
}}
function radioSelectFreq(freq){{
  _activeFreq=freq;_activeChName=freq;
  gv('r-freq-val').textContent=freq;gv('r-freq-name').textContent='Manuel';
  buildRadioChannels([]);
  if(window._pyBridge)window._pyBridge.onRadioFreq(freq);
  if(gv('radio-panel').classList.contains('hidden'))toggleRadio();
}}
function freqStep(delta){{
  const cur=parseFloat(_activeFreq)||225.000;
  const nw=(cur+delta).toFixed(3);
  _activeFreq=nw;gv('r-freq-val').textContent=nw;
  if(window._pyBridge)window._pyBridge.onRadioFreq(nw);
}}
function selectGuard(){{radioJoinChannel('guard','243.000','GUARD');}}

function updateRadio(data){{
  var channels=data.channels||[],activeFreq=data.active_freq||'',activeName=data.active_ch_name||'';
  var total=channels.reduce(function(s,c){{return s+(c.pilots||[]).length;}},0);
  gv('r-user-count').textContent=total+' ONLINE';
  gv('radio-status').textContent=total>0?'IVC CONNECTÉ':'IVC —';
  if(activeFreq){{_activeFreq=activeFreq;_activeChName=activeName;gv('r-freq-val').textContent=activeFreq;gv('r-freq-name').textContent=activeName;}}
  // Find who's talking
  var txPilot='',txFreq='',txChId='';
  channels.forEach(function(ch){{
    (ch.pilots||[]).forEach(function(p){{
      if(p.talking){{txPilot=p.name;txFreq=ch.freq||ch.name;txChId=ch.id;}}
    }});
  }});
  // TX overlay
  var txEl=gv('tx-overlay');
  if(txPilot){{
    txEl.classList.add('on');
    gv('tx-name').textContent='▶ '+txPilot;
    gv('tx-freq').textContent=txFreq;
  }}else{{
    txEl.classList.remove('on');
  }}
  // Build channel grid with TX highlight
  var chList=channels.length>0?channels.map(function(c){{return{{id:c.id,freq:c.freq||c.name,name:c.name,txing:c.id===txChId}};}}):[]; 
  buildRadioChannels(chList);
  // User list
  var list=gv('r-users-list');list.innerHTML='';
  channels.forEach(function(ch){{
    (ch.pilots||[]).forEach(function(pilot){{
      var same=(ch.freq&&_activeFreq&&ch.freq.replace(' MHz','')===_activeFreq.replace(' MHz',''));
      var isTx=pilot.talking;
      var row=document.createElement('div');
      row.className='r-user'+(isTx?' txing':same?' same':' diff');
      row.innerHTML='<div class="'+(isTx?'u-dot-tx':'u-dot')+'"></div><div class="u-name" style="color:'+(isTx?'#ff8844':same?'#00d4ff':'#557755')+'">'+pilot.name+'</div><div class="u-freq">'+(ch.freq||'')+'</div>'+(isTx?'<div style="color:#ff4400;font-size:9px;font-weight:bold">◀ TX</div>':'');
      list.appendChild(row);
    }});
  }});
}}
buildRadioChannels([]);


// ── Friendly Flight Strip ─────────────────────────────────────────────────
var _fsUid=null,_fsTimer=null;
function openFltStrip(uid){{
  var t=trackData[uid];if(!t)return;
  _fsUid=uid;
  gv('fs-cs').textContent=t.display_label||uid;
  gv('fs-type').textContent=(t.group?t.group+' — ':'')+( t.name||'');
  gv('fs-spd').textContent=t.speed_kts>0?Math.round(t.speed_kts):'—';
  gv('fs-hdg').textContent=t.hdg!=null?String(Math.round(t.hdg)).padStart(3,'0')+'°':'—';
  gv('fs-alt').textContent=t.alt_ft?'FL'+String(Math.round(Math.abs(t.alt_ft)/100)).padStart(3,'0'):'—';
  gv('fs-id').textContent=t.id_code||t.coalition||'—';
  gv('fs-id').style.color=trkCol(t);
  var sc=trkCol(t);gv('flt-strip').style.borderTopColor=sc;gv('fs-cs').style.color=sc;gv('flt-strip').classList.add('open');
  if(_fsTimer)clearInterval(_fsTimer);
  _fsTimer=setInterval(function(){{
    var u=trackData[_fsUid];
    if(!u||!u.alive){{closeFltStrip();return;}}
    gv('fs-spd').textContent=u.speed_kts>0?Math.round(u.speed_kts):'—';
    gv('fs-hdg').textContent=u.hdg!=null?String(Math.round(u.hdg)).padStart(3,'0')+'°':'—';
    gv('fs-alt').textContent=u.alt_ft?'FL'+String(Math.round(Math.abs(u.alt_ft)/100)).padStart(3,'0'):'—';
  }},500);
}}
function closeFltStrip(){{gv('flt-strip').classList.remove('open');_fsUid=null;if(_fsTimer){{clearInterval(_fsTimer);_fsTimer=null;}}}}
// Flight strip drag handled by makeDragResize


// ── BRAA Window ──────────────────────────────────────────────────────────────
var _braaPairs=[],_braaLines=[],_braaPending=null,_braaTimer=null;
var _braaIdCounter=0;

function toggleBraaWin(){{
  gv('braa-win').classList.toggle('open');
}}

function computeBraa(latA,lonA,latB,lonB){{
  var R=3440.065;
  var f1=latA*Math.PI/180,f2=latB*Math.PI/180,df=(latB-latA)*Math.PI/180,dl=(lonB-lonA)*Math.PI/180;
  var a=Math.sin(df/2)*Math.sin(df/2)+Math.cos(f1)*Math.cos(f2)*Math.sin(dl/2)*Math.sin(dl/2);
  var rng=2*R*Math.atan2(Math.sqrt(a),Math.sqrt(1-a));
  var bear=((Math.atan2(Math.sin(dl)*Math.cos(f2),Math.cos(f1)*Math.sin(f2)-Math.sin(f1)*Math.cos(f2)*Math.cos(dl))*180/Math.PI)+360)%360;
  return{{bear:bear,rng:rng}};
}}

function getAspect(bearFromFriend,hdgTgt){{
  if(hdgTgt==null)return'—';
  var diff=((hdgTgt-bearFromFriend)+540)%360-180;
  if(Math.abs(diff)<=30)return'HOT';
  if(Math.abs(diff)>=150)return'COLD';
  if(diff>0)return'FLANK R';
  return'FLANK L';
}}

function braaSetSource(uid){{
  _braaPending=uid;
  var t=trackData[uid];
  gv('braa-hint').innerHTML='<span style="color:#22ff44">'+(t?t.display_label:uid)+'</span> sélectionné — clic gauche sur un BOGEY';
  gv('braa-win').classList.add('open');
}}

function braaTrackClick(uid){{
  if(!_braaPending)return;
  var tF=trackData[_braaPending],tT=trackData[uid];
  if(!tF||!tT)return;
  if(_braaPending===uid)return;
  var id=++_braaIdCounter;
  _braaPairs.push({{id:id,friendUid:_braaPending,tgtUid:uid}});
  _braaPending=null;
  gv('braa-hint').textContent='Clic-droit sur un ALLIÉ → Clic gauche sur un BOGEY';
  gv('braa-win').classList.add('open');
  updateAllBraa();
  if(!_braaTimer)_braaTimer=setInterval(updateAllBraa,500);
}}

function removeBraa(id){{
  _braaPairs=_braaPairs.filter(function(p){{return p.id!==id;}});
  // Remove map line
  if(_braaLines[id]){{try{{map.removeLayer(_braaLines[id]);}}catch(e){{}}delete _braaLines[id];}}
  updateAllBraa();
  if(_braaPairs.length===0&&_braaTimer){{clearInterval(_braaTimer);_braaTimer=null;}}
}}

function clearAllBraa(){{
  _braaPairs.forEach(function(p){{if(_braaLines[p.id])try{{map.removeLayer(_braaLines[p.id]);}}catch(e){{}}}});
  _braaPairs=[];_braaLines={{}};
  if(_braaTimer){{clearInterval(_braaTimer);_braaTimer=null;}}
  updateAllBraa();
}}

function updateAllBraa(){{
  var list=gv('braa-list');
  if(_braaPairs.length===0){{
    list.innerHTML='<div class="braa-empty">Aucun BRAA actif</div>';
    return;
  }}
  list.innerHTML='';
  _braaPairs.forEach(function(p){{
    var tF=trackData[p.friendUid],tT=trackData[p.tgtUid];
    if(!tF||!tT)return;
    var r=computeBraa(tF.lat,tF.lon,tT.lat,tT.lon);
    var bear=String(Math.round(r.bear)).padStart(3,'0');
    var rng=r.rng.toFixed(1);
    var alt=tT.alt_ft?'FL'+String(Math.round(Math.abs(tT.alt_ft)/100)).padStart(3,'0'):'—';
    var asp=getAspect(r.bear,tT.hdg);

    var card=document.createElement('div');card.className='braa-card';
    card.innerHTML='<div class="braa-card-hdr"><div class="braa-card-pair"><span style="color:#22ff44">'+(tF.display_label||p.friendUid)+'</span> → <span style="color:#ff4444">'+(tT.display_label||p.tgtUid)+'</span></div><span class="braa-card-del" onclick="removeBraa('+p.id+')">🗑</span></div><div class="braa-card-data"><div><div class="braa-d-lbl">BRG</div><div class="braa-d-val b">'+bear+'°</div></div><div><div class="braa-d-lbl">RNG</div><div class="braa-d-val r">'+rng+'</div></div><div><div class="braa-d-lbl">ALT</div><div class="braa-d-val a">'+alt+'</div></div><div><div class="braa-d-lbl">ASP</div><div class="braa-d-val s">'+asp+'</div></div></div>';
    list.appendChild(card);

    // Draw dashed line on map
    if(_braaLines[p.id]){{try{{map.removeLayer(_braaLines[p.id]);}}catch(e){{}}}}
    _braaLines[p.id]=L.polyline([[tF.lat,tF.lon],[tT.lat,tT.lon]],{{color:'#00e5ff',weight:1.5,opacity:.6,dashArray:'6 4',interactive:false}}).addTo(map);
  }});
}}

// Expose bullseye to JS
window._bullseye=[];

// BRAA drag handled by makeDragResize

// ── Altitude Filter ──────────────────────────────────────────────────────────




// ── Generic draggable + resizable for floating windows ───────────────────────
function makeDragResize(panelId,dragId,resizeId){{
  var p=gv(panelId),d=gv(dragId);
  if(!p||!d)return;
  var mx=0,my=0,dragging=false;
  d.addEventListener('mousedown',function(e){{
    if(e.target.classList.contains('braa-close')||e.target.classList.contains('fs-close'))return;
    dragging=true;p.style.right='auto';p.style.bottom='auto';
    mx=e.clientX-p.offsetLeft;my=e.clientY-p.offsetTop;
    document.body.style.userSelect='none';e.preventDefault();
  }});
  document.addEventListener('mousemove',function(e){{
    if(!dragging)return;
    p.style.left=Math.max(0,e.clientX-mx)+'px';
    p.style.top=Math.max(0,e.clientY-my)+'px';
  }});
  document.addEventListener('mouseup',function(){{dragging=false;document.body.style.userSelect='';}});
  if(resizeId){{
    var rh=gv(resizeId);if(!rh)return;
    var resizing=false,sx=0,sy=0,sw=0,sh=0;
    rh.addEventListener('mousedown',function(e){{
      resizing=true;sx=e.clientX;sy=e.clientY;sw=p.offsetWidth;sh=p.offsetHeight;
      document.body.style.userSelect='none';e.stopPropagation();e.preventDefault();
    }});
    document.addEventListener('mousemove',function(e){{
      if(!resizing)return;
      p.style.width=Math.max(240,sw+(e.clientX-sx))+'px';
      p.style.maxHeight=Math.max(150,sh+(e.clientY-sy))+'px';
    }});
    document.addEventListener('mouseup',function(){{resizing=false;document.body.style.userSelect='';}});
  }}
}}

// Init drag/resize for windows
makeDragResize('braa-win','braa-drag','braa-resize');
makeDragResize('flt-strip','fs-drag',null);
makeDragResize('radio-panel','radio-drag-bar','radio-resize');

// ── QWebChannel ───────────────────────────────────────────────────────────────
new QWebChannel(qt.webChannelTransport,ch=>{{
  window._pyBridge=ch.objects.py;
  window._pyBridge.onPageReady();
}});
</script>
</body></html>"""


# ── Stubs compatibilité ───────────────────────────────────────────────────────
class RadarColors:
    EDITABLE = []
    def __init__(self): pass
    def q(self, key):
        from PyQt6.QtGui import QColor
        return QColor("#44cc66")

COLORS = RadarColors()
