<p align="center">
  <img src="assets/falconeye_logo.png" width="220" alt="Falcon-Eye GCI">
</p>

<h1 align="center">Falcon-Eye GCI</h1>
<p align="center"><strong>Ground Control Intercept tool for Falcon BMS</strong></p>
<p align="center">
  <img src="https://img.shields.io/badge/Falcon_BMS-4.37_|_4.38-orange">
  <img src="https://img.shields.io/badge/Python-3.11+-blue">
  <img src="https://img.shields.io/badge/license-GPL_v3-green">
  <img src="https://img.shields.io/badge/platform-Windows-lightgrey">
</p>

---

## 🇫🇷 Français

### Présentation

Falcon-Eye GCI est un outil de contrôle radar dédié aux opérateurs GCI (Ground Control Intercept) et ATC sur **Falcon BMS**. Il se connecte en temps réel au flux Tacview TRTT de BMS pour afficher tous les contacts aériens sur une carte tactique, avec symbologie militaire, calculs BRAA, bullseye et gestion radio IVC.

L'outil est conçu pour être utilisé sur un second écran pendant une session multijoueur — le GCI garde les yeux sur la carte pendant que les pilotes volent.

### Fonctionnalités

- **Radar tactique temps réel** — contacts aériens live depuis BMS via Tacview TRTT (port 42674)
- **Portée radar réaliste** — filtre ligne de mire basé sur l'altitude : `R = 1.23 × (√alt + √50)` NM. Un avion en nap de terrain (~500 ft) n'est visible qu'à ~37 NM, un avion à 30 000 ft jusqu'à ~220 NM
- **Système BRAA** — Ctrl+clic sur un allié → clic sur la cible → bearing, range, altitude, aspect calculés et mis à jour en live, avec ligne orange sur la carte
- **Bullseye** — affichage permanent avec cercles concentriques depuis le fichier mission .ini
- **Overlay mission** — charge un fichier .ini BMS : bullseye, route, anneaux SAM/AAA, lignes FLOT, points de référence
- **Panneau radio IVC** — lit les fréquences UHF/VHF directement depuis la SharedMemory BMS, presets standard accessibles en un clic, détection automatique des périphériques audio
- **Flight strips** — fiche flottante par contact avec callsign, vitesse, cap, altitude, ID code
- **Symbologie militaire** — carré = allié, diamant = hostile, cercle = inconnu, avec vecteurs vitesse et trails
- **Carte vectorielle locale** — côtes, DMZ, aéroports, pistes, TACAN — aucune dépendance réseau pour la carte de base

### Installation

```bash
# Cloner ou extraire le dossier
pip install -r requirements.txt

# Lancer
python main.py
```

**Dépendances Python :**
| Package | Rôle |
|---|---|
| `PyQt6` | Interface graphique |
| `PyQt6-WebEngine` | Carte Leaflet intégrée |
| `sounddevice` | Détection périphériques audio |

### Connexion à BMS

1. Lancer Falcon BMS et démarrer une mission (campagne ou TE)
2. S'assurer que **Tacview Real-Time Telemetry** est activé (activé par défaut, port 42674)
3. Ouvrir Falcon-Eye → cliquer **CONNECTER**
4. Entrer l'IP du serveur BMS si distant (défaut : `127.0.0.1`)
5. Les contacts apparaissent dès que la mission tourne

Pour la radio IVC, lancer **IVC Client.exe** depuis le launcher BMS. Les fréquences se lisent automatiquement depuis la SharedMemory BMS.

### Interface

| Élément | Action |
|---|---|
| **Molette** | Zoom carte |
| **Clic gauche** sur contact | Ouvrir flight strip |
| **Ctrl+clic** sur contact | Définir source BRAA |
| **Clic gauche** sur cible | Compléter la paire BRAA |
| **Clic droit** | Menu contextuel / règle de mesure |
| **Échap** | Annuler BRAA en cours |
| Bouton **MISSION** | Charger un .ini BMS |
| Bouton **BULL** | Centrer sur le bullseye |
| Bouton **ALLIÉS** | Panneau contacts amis |
| Bouton **RADIO** | Panneau radio IVC |
| Bouton **BRAA** | Fenêtre récap BRAA |
| Bouton **OPTIONS** | Paramètres visuels |

### Fichiers de log

Windows : `%LOCALAPPDATA%\FalconEyeGCI\logs\`  
Linux/Mac : `~/.falcon_eye_gci/logs/`

---

## 🇬🇧 English

### Overview

Falcon-Eye GCI is a dedicated radar scope for **GCI (Ground Control Intercept)** and ATC operators in **Falcon BMS**. It connects in real-time to BMS via the Tacview TRTT stream and displays all air contacts on a tactical map with military symbology, BRAA calculations, bullseye display, and IVC radio management.

Built to run on a second monitor during multiplayer sessions — the GCI operator keeps eyes on the radar while pilots fly.

### Features

- **Real-time tactical radar** — live air contacts from BMS via Tacview TRTT (port 42674)
- **Realistic radar range** — line-of-sight filter based on altitude: `R = 1.23 × (√alt + √50)` NM. A low-level aircraft (~500 ft) is only visible within ~37 NM; a high-altitude aircraft at 30,000 ft is visible up to ~220 NM
- **BRAA system** — Ctrl+click on an ally → click on target → bearing, range, altitude, aspect calculated live, with an orange dashed line on the map
- **Bullseye** — permanent display with concentric rings, loaded from mission .ini
- **Mission overlay** — load a BMS .ini file: bullseye, route, SAM/AAA threat rings, FLOT lines, reference points
- **IVC radio panel** — reads UHF/VHF frequencies directly from BMS SharedMemory, standard presets one-click access, automatic audio device detection
- **Flight strips** — floating info card per contact: callsign, speed, heading, altitude, ID code
- **Military symbology** — square = friendly, diamond = hostile, circle = unknown, with velocity vectors and trails
- **Local vector map** — coastlines, DMZ, airports, runways, TACAN — no network dependency for base map

### Installation

```bash
# Clone or extract the folder
pip install -r requirements.txt

# Run
python main.py
```

**Python dependencies:**
| Package | Purpose |
|---|---|
| `PyQt6` | GUI framework |
| `PyQt6-WebEngine` | Embedded Leaflet map |
| `sounddevice` | Audio device detection |

### Connecting to BMS

1. Launch Falcon BMS and start a mission (campaign or TE)
2. Ensure **Tacview Real-Time Telemetry** is enabled (on by default, port 42674)
3. Open Falcon-Eye → click **CONNECTER**
4. Enter the BMS server IP if remote (default: `127.0.0.1`)
5. Contacts appear as soon as the mission is running

For IVC radio, launch **IVC Client.exe** from the BMS launcher. Frequencies are read automatically from BMS SharedMemory.

### Controls

| Element | Action |
|---|---|
| **Mouse wheel** | Zoom map |
| **Left-click** on contact | Open flight strip |
| **Ctrl+click** on contact | Set BRAA source |
| **Left-click** on target | Complete BRAA pair |
| **Right-click** | Context menu / ruler |
| **Escape** | Cancel active BRAA |
| **MISSION** button | Load a BMS .ini file |
| **BULL** button | Center on bullseye |
| **ALLIÉS** button | Friendly contacts panel |
| **RADIO** button | IVC radio panel |
| **BRAA** button | BRAA summary window |
| **OPTIONS** button | Visual settings |

### Log files

Windows: `%LOCALAPPDATA%\FalconEyeGCI\logs\`  
Linux/Mac: `~/.falcon_eye_gci/logs/`

---

## Architecture

```
falcon-eye/
├── main.py                 # Entry point
├── core/
│   ├── trtt_client.py      # Tacview TRTT WebSocket client + Track dataclass
│   ├── ivc_client.py       # IVC radio via BMS SharedMemory
│   ├── shared_mem.py       # BMS SharedMemory reader (UHF/VHF freq, position)
│   ├── mission_parser.py   # BMS .ini mission file parser
│   └── data.py             # Geographic data (airports, coastlines, DMZ, runways)
├── ui/
│   ├── radar_widget.py     # Main radar (PyQt6 + QWebEngine + Leaflet.js)
│   ├── main_window.py      # Application window, toolbar, status bar
│   ├── connection_dialog.py
│   ├── braa_window.py
│   ├── allies_panel.py
│   ├── flight_strip.py
│   └── ivc_panel.py
├── assets/                 # Icons, logo
├── tests/
│   └── test_core.py        # 163 unit tests
└── requirements.txt
```

## License

GNU General Public License v3.0 — see [LICENSE](LICENSE)

---

*Falcon-Eye GCI — by [Riesu](https://falcon-charts.com) — contact@falcon-charts.com*
