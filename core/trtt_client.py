# -*- coding: utf-8 -*-
"""
TRTTClient — Tacview Real-Time Telemetry Protocol
Implémente le parsing complet : Name/Pilot/Callsign/Group/Coalition/Color
Conforme à la spec OpenRadar #issues (Callsign key, Group, Pilot=humain only)
"""
import asyncio, zlib, math, time, logging, re
from dataclasses import dataclass, field
from typing import Dict, Optional, Callable

logger = logging.getLogger(__name__)

TRTT_PORT  = 42674
HANDSHAKE  = b"XtraLib.Stream.0\nTacview.RealTimeTelemetry.0\n[BMS GCI Radar]\n\0"

# ── ID Codes (BOGEY/BANDIT/etc) ────────────────────────────────────────────────
ID_UNKNOWN  = "UNKNOWN"
ID_ASSUMED  = "ASSUMED FRIEND"
ID_FRIEND   = "FRIENDLY"
ID_NEUTRAL  = "NEUTRAL"
ID_SUSPECT  = "SUSPECT"
ID_HOSTILE  = "HOSTILE"
ID_BANDIT   = "BANDIT"
ID_BOGEY    = "BOGEY"

ID_COLORS = {
    ID_UNKNOWN:  "#888888",
    ID_ASSUMED:  "#44ff88",
    ID_FRIEND:   "#22ff44",
    ID_NEUTRAL:  "#aaaaaa",
    ID_SUSPECT:  "#ffaa00",
    ID_HOSTILE:  "#ff4444",
    ID_BANDIT:   "#ff2222",
    ID_BOGEY:    "#ffdd00",
}
# Preset couleurs rapides (touche 1-5)
COLOR_PRESETS = {
    1: ("#22ff44", ID_FRIEND),
    2: ("#ff2222", ID_BANDIT),
    3: ("#ffdd00", ID_BOGEY),
    4: ("#ff4444", ID_HOSTILE),
    5: ("#aaaaaa", ID_NEUTRAL),
}

@dataclass
class Track:
    uid:          str
    # Identité
    name:         str   = ""      # type d'avion (F-16CM-52, MiG-29G...)
    pilot:        str   = ""      # humain uniquement
    callsign:     str   = ""      # radio callsign (Viper11, Hobby71...)
    group:        str   = ""      # package/groupe
    obj_type:     str   = ""      # Air+FixedWing, Ground+...
    coalition:    str   = "Neutral"
    country:      str   = ""
    # ID GCI assigné par l'opérateur
    id_code:      str   = ID_UNKNOWN
    custom_color: Optional[str] = None

    # Position
    lat:   float = 0.0
    lon:   float = 0.0
    alt:   float = 0.0    # mètres MSL
    hdg:   float = 0.0    # degrés vrais
    speed: float = 0.0    # m/s

    # Trail (liste de (lat,lon))
    trail: list = field(default_factory=list)
    TRAIL_MAX: int = field(default=12, repr=False)

    updated_at: float = field(default_factory=time.time)
    alive:      bool  = True
    is_human:   bool  = False

    # ── Propriétés dérivées ────────────────────────────────────────────────
    @property
    def alt_ft(self)   -> int:   return int(self.alt * 3.28084)
    @property
    def speed_kts(self)-> int:   return int(self.speed * 1.94384)
    @property
    def is_air(self)   -> bool:  return "Air" in self.obj_type
    @property
    def is_missile(self)->bool:  return "Missile" in self.obj_type or "Bomb" in self.obj_type
    @property
    def is_ground(self)-> bool:  return "Ground" in self.obj_type or "Sea" in self.obj_type
    @property
    def is_rotary(self)-> bool:  return "Rotorcraft" in self.obj_type
    @property
    def display_label(self) -> str:
        """Label principal affiché sur la piste."""
        return self.callsign or self.pilot or self.name[:8] or self.uid[:6]
    @property
    def color(self) -> str:
        if self.custom_color:
            return self.custom_color
        return ID_COLORS.get(self.id_code, _coalition_color(self.coalition))

    def push_trail(self):
        if self.lat != 0 and self.lon != 0:
            if not self.trail or self.trail[-1] != (self.lat, self.lon):
                self.trail.append((self.lat, self.lon))
                if len(self.trail) > self.TRAIL_MAX:
                    self.trail.pop(0)

    def to_dict(self) -> dict:
        return {
            "uid": self.uid, "name": self.name, "pilot": self.pilot,
            "callsign": self.callsign, "group": self.group,
            "type": self.obj_type, "coalition": self.coalition,
            "id_code": self.id_code, "color": self.color,
            "lat": round(self.lat,5), "lon": round(self.lon,5),
            "alt_ft": self.alt_ft, "hdg": round(self.hdg,1),
            "speed_kts": self.speed_kts, "alive": self.alive,
            "is_human": self.is_human,
        }


def _coalition_color(coalition: str) -> str:
    return {"Blue":"#22ff44","Allies":"#22ff44",
            "Red":"#ff2222","Enemies":"#ff2222"}.get(coalition, "#888888")



# ── Détection camp par type avion/pays (méthode F4Radar/OpenRadar) ────────
_BLUE_AIRCRAFT = {
    "F-16", "F-15", "F/A-18", "FA-18", "A-10", "F-117", "B-1", "B-2", "B-52",
    "F-22", "F-35", "E-3", "E-2", "KC-135", "KC-10", "C-130", "C-17",
    "AH-64", "UH-60", "CH-47", "AH-1", "P-3", "F-14", "F-4E",
    "EF-2000", "Tornado", "Rafale", "Mirage", "JAS-39", "KF-16",
    "T-50", "FA-50", "KF-21",
}
_RED_AIRCRAFT = {
    "MiG-21", "MiG-23", "MiG-25", "MiG-29", "MiG-31",
    "Su-25", "Su-27", "Su-30", "Su-33", "Su-34", "Su-35", "Su-57",
    "J-10", "J-11", "J-15", "J-16", "J-20", "JH-7",
    "Tu-22", "Tu-95", "Tu-160", "IL-76", "An-2",
    "Mi-24", "Mi-8", "Mi-28", "Ka-50", "Ka-52",
    "SA-2", "SA-3", "SA-5", "SA-6", "SA-8", "SA-10", "SA-11", "SA-13", "SA-15",
    "KN-06", "HQ-9",
}
_BLUE_COUNTRIES = {"us", "kr", "rok", "jp", "jpn", "uk", "gb", "fr", "de", "au", "ca", "it", "es", "nl", "be", "no", "dk", "tr"}
_RED_COUNTRIES = {"kp", "dprk", "cn", "ru", "ir", "sy"}

def _detect_camp(name: str, country: str) -> str:
    """Detect Blue/Red from aircraft type name and country code."""
    n = name.upper()
    # Check aircraft type
    for prefix in _BLUE_AIRCRAFT:
        if prefix.upper() in n:
            return "Blue"
    for prefix in _RED_AIRCRAFT:
        if prefix.upper() in n:
            return "Red"
    # Check country
    if country:
        cl = country.lower()
        if cl in _BLUE_COUNTRIES:
            return "Blue"
        if cl in _RED_COUNTRIES:
            return "Red"
    return ""

class TRTTClient:
    def __init__(self, on_update: Callable = None):
        self.host      = ""; self.port = TRTT_PORT; self.password = ""
        self.connected = False; self.running = False
        self.tracks:   Dict[str, Track] = {}
        self.on_update = on_update or (lambda t: None)
        self._ref_lat  = 0.0; self._ref_lon = 0.0
        self._reader   = None; self._writer = None
        self._buf      = ""; self._last_ts = 0.0

    # ── Connexion ─────────────────────────────────────────────────────────────
    async def connect(self, host, port=TRTT_PORT, password="") -> bool:
        self.host = host; self.port = port; self.password = password
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=10.0)
            self._writer.write(HANDSHAKE)
            await self._writer.drain()
            try:
                resp = await asyncio.wait_for(self._reader.read(512), timeout=5.0)
                if password and b"Password" in resp:
                    crc = zlib.crc32(password.encode("utf-16-le")) & 0xFFFFFFFF
                    self._writer.write(f"{crc}\n\0".encode())
                    await self._writer.drain()
            except asyncio.TimeoutError:
                pass
            self.connected = True
            logger.info(f"TRTT connecté {host}:{port}")
            return True
        except Exception as e:
            logger.error(f"TRTT connexion: {e}")
            return False

    async def disconnect(self):
        self.running = False; self.connected = False
        try:
            if self._writer:
                self._writer.close(); await self._writer.wait_closed()
        except Exception: pass

    async def run(self):
        self.running = True; self._buf = ""
        try:
            while self.running and self._reader:
                try:
                    chunk = await asyncio.wait_for(self._reader.read(65536), timeout=30.0)
                    if not chunk: break
                    self._buf += chunk.decode("utf-8", errors="replace")
                    self._parse_buffer()
                except asyncio.TimeoutError: break
                except Exception as e: logger.error(f"TRTT read: {e}"); break
        finally:
            self.connected = False; self.running = False

    # ── Parsing ───────────────────────────────────────────────────────────────
    def _parse_buffer(self):
        lines = self._buf.split("\n")
        self._buf = lines[-1]
        changed = False
        for line in lines[:-1]:
            line = line.strip()
            if not line: continue
            if self._parse_line(line): changed = True
        if changed:
            now = time.time()
            # Marquer comme morts les contacts sans update depuis 60s
            dead_uids = [
                uid for uid, t in self.tracks.items()
                if now - t.updated_at > 60.0
            ]
            for uid in dead_uids:
                del self.tracks[uid]
            self.on_update(self.tracks)

    def _parse_line(self, line: str) -> bool:
        if line.startswith("#"):
            try: self._last_ts = float(line[1:])
            except (ValueError, TypeError): pass
            return False
        if line.startswith("0,"):
            self._parse_global(line[2:]); return False
        if line.startswith("-"):
            uid = line[1:].strip()
            if uid in self.tracks:
                del self.tracks[uid]
            return True
        comma = line.find(",")
        if comma < 1: return False
        return self._parse_track(line[:comma], line[comma+1:])

    def _parse_global(self, props: str):
        for kv in props.split(","):
            if "=" not in kv: continue
            k, v = kv.split("=", 1)
            k = k.strip(); v = v.strip()
            if k == "ReferenceLatitude":
                try: self._ref_lat = float(v)
                except (ValueError, TypeError): pass
            elif k == "ReferenceLongitude":
                try: self._ref_lon = float(v)
                except (ValueError, TypeError): pass

    def _parse_track(self, uid: str, props: str) -> bool:
        kv = self._split_props(props)
        is_new = uid not in self.tracks
        if is_new:
            self.tracks[uid] = Track(uid=uid)
        t = self.tracks[uid]
        t.alive = True; t.updated_at = time.time()

        if "T" in kv: self._parse_T(t, kv["T"])

        if "Name"     in kv: t.name     = kv["Name"]
        if "Group"    in kv: t.group    = kv["Group"]
        if "Country"  in kv: t.country  = kv["Country"]

        # CallSign has capital S in BMS TRTT
        if "CallSign" in kv:
            cs = kv["CallSign"]
            if cs: t.callsign = cs
        elif "Callsign" in kv:
            cs = kv["Callsign"]
            if cs: t.callsign = cs
        if "Pilot" in kv:
            t.pilot    = kv["Pilot"]
            t.is_human = True
            if not t.callsign:
                t.callsign = kv["Pilot"]

        # Extract group/package from callsign (e.g. "Cajun61" → "Cajun6")
        if t.callsign and not t.group:
            m = re.match(r'^([A-Za-z]+\d+)\d$', t.callsign)
            if m:
                t.group = m.group(1)

        if "Type" in kv:
            t.obj_type = kv["Type"]

        # Camp: Color primary, Coalition fallback
        if "Color" in kv:
            c = kv["Color"].lower()
            if "blue" in c or "allies" in c:
                t.coalition = "Blue"
            elif "red" in c or "enemies" in c:
                t.coalition = "Red"

        if "Coalition" in kv:
            co = kv["Coalition"]
            if t.coalition not in ("Blue", "Red"):
                if co in ("Allies", "Blue"):
                    t.coalition = "Blue"
                elif co in ("Enemies", "Red"):
                    t.coalition = "Red"
                else:
                    t.coalition = co

        # If Color/Coalition didn't set the camp, detect from aircraft type/country
        # (like F4Radar/OpenRadar approach)
        if t.coalition not in ("Blue", "Red") and t.name:
            detected = _detect_camp(t.name, t.country)
            if detected:
                t.coalition = detected

        # ALWAYS update id_code from camp
        if not t.custom_color:
            if t.coalition in ("Blue", "Allies"):
                t.id_code = ID_FRIEND
            elif t.coalition in ("Red", "Enemies"):
                t.id_code = ID_BOGEY

        if "IAS" in kv:
            try: t.speed = float(kv["IAS"])          # Tacview IAS déjà en m/s
            except (ValueError, TypeError): pass

        # Debug: log new tracks with ALL received keys
        if is_new and len(kv) > 1:
            logger.info(f"TRACK {uid}: ALL_KEYS={list(kv.keys())} "
                        f"name={t.name} cs={t.callsign} pilot={t.pilot} "
                        f"grp={t.group} coal={t.coalition} id={t.id_code}")

        return True

    def _parse_T(self, t: Track, raw: str):
        parts = raw.split("|")
        def g(i):
            if i < len(parts) and parts[i].strip():
                try: return float(parts[i])
                except (ValueError, TypeError): pass
            return None
        lon = g(0); lat = g(1); alt = g(2); hdg = g(5)
        if lon is not None: t.lon = self._ref_lon + lon
        if lat is not None: t.lat = self._ref_lat + lat
        if alt is not None: t.alt = alt
        if hdg is not None: t.hdg = hdg % 360.0

    @staticmethod
    def _split_props(props: str) -> dict:
        """Split sur virgules en respectant les champs T= qui contiennent |.

        Le champ T= utilise | comme séparateur interne (ex: T=1.23|4.56|789||...).
        On détecte T= et on continue à accumuler jusqu'à rencontrer une virgule
        suivie d'un token contenant '=' (donc la prochaine clé).
        """
        kv = {}
        buf = ""
        in_T = False
        for ch in props + ",":
            if ch == ",":
                if in_T:
                    # Regarder si ce qui suit ressemble à une clé (contient =)
                    # On stocke la virgule et on vérifiera au prochain =
                    buf += ch
                    continue
                if "=" in buf:
                    k, v = buf.split("=", 1)
                    kv[k.strip()] = v.strip()
                buf = ""
            else:
                # Si on était dans T= et qu'on rencontre un '=' dans le buffer
                # après la dernière virgule, c'est qu'on a dépassé T=
                if in_T and ch == "=":
                    # Trouver la dernière virgule dans buf pour séparer
                    last_comma = buf.rfind(",")
                    if last_comma >= 0:
                        t_val = buf[:last_comma]
                        if "=" in t_val:
                            tk, tv = t_val.split("=", 1)
                            kv[tk.strip()] = tv.strip()
                        buf = buf[last_comma + 1:]
                        in_T = False
                buf += ch
                if not in_T and buf.strip().startswith("T="):
                    in_T = True
        # Flush remaining buffer
        if buf.strip() and "=" in buf:
            k, v = buf.split("=", 1)
            kv[k.strip()] = v.strip()
        return kv

    # ── ID Management ──────────────────────────────────────────────────────────
    def set_track_id(self, uid: str, id_code: str, custom_color: str = None):
        if uid in self.tracks:
            self.tracks[uid].id_code = id_code
            self.tracks[uid].custom_color = custom_color
            self.on_update(self.tracks)

    def apply_preset(self, uid: str, preset_num: int):
        if preset_num in COLOR_PRESETS and uid in self.tracks:
            color, id_code = COLOR_PRESETS[preset_num]
            self.tracks[uid].custom_color = color
            self.tracks[uid].id_code = id_code
            self.on_update(self.tracks)

    def stats(self) -> dict:
        # Toutes les tracks dans le dict sont vivantes (les mortes sont supprimées)
        alive = list(self.tracks.values())
        return {
            "total":   len(alive),
            "alive":   len(alive),
            "air":     sum(1 for t in alive if t.is_air),
            "missile": sum(1 for t in alive if t.is_missile),
            "ground":  sum(1 for t in alive if t.is_ground),
            "human":   sum(1 for t in alive if t.is_human),
        }
