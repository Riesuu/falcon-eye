# 🇫🇷 Nebula GCI

**Ground Control Intercept tool for Falcon BMS**

By **Riesu** — [contact@falcon-charts.com](mailto:contact@falcon-charts.com)

---

## Features

- **Tactical radar map** — Leaflet-based map with military symbology (■ friendly, ◆ hostile, ● unknown)
- **TRTT data source** — Real-time Tacview telemetry, sees ALL contacts on the theatre
- **Aircraft-type camp detection** — F-16 → Blue, MiG-29 → Red (F4Radar/OpenRadar method)
- **Mission INI import** — Load BMS .ini files with route, SAM rings, FLOT lines, bullseye
- **Flight strip on click** — Callsign, speed, heading, altitude, group/package
- **Radio panel** — BMS frequency presets, TX indicator
- **Configurable** — Icon sizes, colors, label sizes, all in the Options panel
- **105 unit tests**

## Requirements

- Python 3.10+
- PyQt6, PyQt6-WebEngine

```bash
pip install PyQt6 PyQt6-WebEngine
python main.py
```

## Usage

1. Start Falcon BMS and enable TRTT (Tacview Real-Time Telemetry)
2. Launch Nebula GCI: `python main.py`
3. Click **CONNECTER** → IP `127.0.0.1`, port `42674` → OK
4. Click **MISSION** to load a .ini file
5. Click **📻 RADIO** for the frequency panel
6. Click on any contact for the flight strip

## Architecture

```
Falcon BMS (TRTT port 42674)
       ↓
TRTTClient → parses ACMI stream → Track objects
       ↓
RadarWidget (PyQt6 + Leaflet) → JS map with military symbology
```

## License

GNU General Public License v3.0 — see [LICENSE](LICENSE)

---

*Made in France 🇫🇷*
