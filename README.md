<p align="center">
  <img src="assets/falconeye_logo.png" width="200" alt="Falcon-Eye GCI">
</p>

<h1 align="center">Falcon-Eye GCI</h1>
<p align="center"><em>The radar scope your GCI deserves.</em></p>

<p align="center">
  <img src="https://img.shields.io/badge/Falcon_BMS-4.37_|_4.38-orange">
  <img src="https://img.shields.io/badge/platform-Windows-lightgrey">
  <img src="https://img.shields.io/badge/license-GPL_v3-green">
  <img src="https://img.shields.io/github/v/release/falcon-charts/falcon-eye-gci">
</p>

---

## 🇫🇷 Français

### C'est quoi ?

Falcon-Eye GCI est un scope radar dédié aux **contrôleurs GCI et ATC** sur Falcon BMS. Il se connecte en temps réel à votre session BMS et affiche tous les contacts aériens sur une carte tactique — avec BRAA, bullseye, anneaux SAM et radio IVC intégrés.

Conçu pour tourner sur un **second écran** pendant une session multi. Le GCI garde les yeux sur la carte, les pilotes gardent les yeux dans le cockpit.

### Téléchargement

👉 **[Télécharger FalconEye-GCI.exe](../../releases/latest)**

Pas d'installation, pas de Python, pas de dépendances. Double-clic et c'est parti.

> ⚠️ **Windows SmartScreen** peut bloquer le premier lancement car l'exe n'est pas signé.  
> Cliquer **"Informations complémentaires" → "Exécuter quand même"**.

### Démarrage rapide

1. Lancer **Falcon BMS** et démarrer une mission
2. Lancer **FalconEye-GCI.exe**
3. Dans la fenêtre de connexion : laisser `127.0.0.1` si BMS tourne sur la même machine, sinon entrer l'IP du serveur
4. Cliquer **Connecter**
5. Les contacts apparaissent immédiatement

**Optionnel — Carte mission SAM/FLOT :**  
Bouton **MISSION** → charger votre fichier `.ini` BMS pour afficher les anneaux SAM, la route, le bullseye et les lignes de front.

**Optionnel — Radio IVC :**  
Lancer **IVC Client.exe** depuis le launcher BMS avant de décoller. Falcon-Eye lit automatiquement les fréquences UHF/VHF depuis BMS.

### Fonctionnalités

| | |
|---|---|
| 🎯 **Radar temps réel** | Contacts live depuis BMS via Tacview TRTT |
| 📡 **Portée réaliste** | Filtre ligne de mire basé sur l'altitude — un avion en nap (~500 ft) visible à ~37 NM, à 30 000 ft jusqu'à ~220 NM |
| 🔴 **BRAA** | Ctrl+clic sur un allié → clic sur la cible → bearing/range/altitude/aspect en live |
| 🗺️ **Overlay mission** | Bullseye, route, anneaux SAM, lignes FLOT depuis fichier .ini BMS |
| 📻 **Radio IVC** | Fréquences UHF/VHF depuis SharedMemory BMS, presets en un clic |
| ✈️ **Flight strips** | Fiche par contact : callsign, vitesse, cap, altitude, ID code |
| 🗂️ **Alliés** | Panneau dédié aux contacts amis |
| 🗺️ **Carte locale** | Côtes, DMZ, aéroports, pistes — aucun accès internet requis |

### Prérequis BMS

- Falcon BMS **4.37** ou **4.38**
- **Tacview Real-Time Telemetry** activé (actif par défaut sur le port 42674)
- Si le serveur BMS est distant : le port **42674 TCP** doit être ouvert/forwardé

### Raccourcis

| Action | Commande |
|---|---|
| Zoom | Molette souris |
| Ouvrir flight strip | Clic gauche sur contact |
| Définir source BRAA | Ctrl+clic sur allié |
| Compléter BRAA | Clic gauche sur cible |
| Règle de mesure | Clic droit (maintenir) |
| Annuler BRAA | Échap |

---

## 🇬🇧 English

### What is it?

Falcon-Eye GCI is a dedicated radar scope for **GCI and ATC controllers** in Falcon BMS. It connects in real-time to your BMS session and displays all air contacts on a tactical map — with BRAA, bullseye, SAM rings, and integrated IVC radio.

Built to run on a **second monitor** during multiplayer sessions. The GCI keeps eyes on the radar, pilots keep eyes in the cockpit.

### Download

👉 **[Download FalconEye-GCI.exe](../../releases/latest)**

No installation, no Python, no dependencies. Double-click and go.

> ⚠️ **Windows SmartScreen** may block the first launch since the exe is unsigned.  
> Click **"More info" → "Run anyway"**.

### Quick start

1. Launch **Falcon BMS** and start a mission
2. Launch **FalconEye-GCI.exe**
3. In the connection dialog: leave `127.0.0.1` if BMS is on the same machine, otherwise enter the server IP
4. Click **Connecter**
5. Contacts appear immediately

**Optional — SAM/FLOT mission map:**  
Click **MISSION** → load your BMS `.ini` file to display SAM rings, route, bullseye, and front lines.

**Optional — IVC Radio:**  
Launch **IVC Client.exe** from the BMS launcher before takeoff. Falcon-Eye reads UHF/VHF frequencies automatically from BMS.

### Features

| | |
|---|---|
| 🎯 **Live radar** | Real-time contacts from BMS via Tacview TRTT |
| 📡 **Realistic range** | Line-of-sight filter based on altitude — low-level (~500 ft) visible at ~37 NM, 30,000 ft up to ~220 NM |
| 🔴 **BRAA** | Ctrl+click on an ally → click on target → bearing/range/altitude/aspect live |
| 🗺️ **Mission overlay** | Bullseye, route, SAM rings, FLOT lines from BMS .ini file |
| 📻 **IVC Radio** | UHF/VHF from BMS SharedMemory, standard presets one click away |
| ✈️ **Flight strips** | Per-contact card: callsign, speed, heading, altitude, ID code |
| 🗂️ **Allies panel** | Dedicated friendly contacts panel |
| 🗺️ **Local map** | Coastlines, DMZ, airports, runways — no internet required |

### BMS requirements

- Falcon BMS **4.37** or **4.38**
- **Tacview Real-Time Telemetry** enabled (on by default, port 42674)
- If BMS server is remote: port **42674 TCP** must be open/forwarded

### Controls

| Action | Input |
|---|---|
| Zoom | Mouse wheel |
| Open flight strip | Left-click on contact |
| Set BRAA source | Ctrl+click on ally |
| Complete BRAA | Left-click on target |
| Distance ruler | Right-click (hold) |
| Cancel BRAA | Escape |

---

## Liens / Links

- 🌐 [falcon-charts.com](https://falcon-charts.com)
- 📧 contact@falcon-charts.com

## Licence / License

GNU General Public License v3.0 — voir [LICENSE](LICENSE)
