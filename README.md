<p align="center">
  <img src="assets/falconeye_logo.png" width="220" alt="Falcon-Eye">
</p>

<h1 align="center">Falcon-Eye</h1>
<p align="center"><em>AWACS / ATC System for Falcon BMS</em></p>

<p align="center">
  <img src="https://img.shields.io/badge/Falcon_BMS-4.38-orange">
  <img src="https://img.shields.io/badge/Platform-Windows-lightgrey">
  <img src="https://img.shields.io/badge/License-GPL_v3-green">
  <img src="https://img.shields.io/badge/Gratuit-open_source-brightgreen">
</p>

---

## 🇫🇷 Français

### C'est quoi ?

Falcon-Eye est un scope radar **gratuit et open source** dédié aux **contrôleurs AWACS/GCI et ATC** sur Falcon BMS. Il se connecte en temps réel à votre session BMS et affiche tous les contacts aériens sur une carte tactique — avec BRAA, bullseye, SAM et IVC intégrés.


📧 contact@falcon-charts.com — 🌐 [eye.falcon-charts.com](https://eye.falcon-charts.com)

---

### Téléchargement

👉 **[Télécharger FalconEye.exe](../../releases/latest)**

> ⚠️ **Windows SmartScreen** peut bloquer le premier lancement car l'exe n'est pas signé.  
> Cliquer **"Informations complémentaires" → "Exécuter quand même"**.

---

### Démarrage rapide

1. Lancer **Falcon BMS** et démarrer une mission
2. Lancer **FalconEye.exe**
3. Laisser `127.0.0.1` si BMS tourne sur la même machine, sinon entrer l'IP du serveur
4. Cliquer sur **Connecter**

**Optionnel — Carte mission :** Bouton **MISSION** → charger votre fichier `.ini` BMS pour les SAM, la route, le bullseye et les lignes de front.


---

### Fonctionnalités

#### 📡 Radar temps réel

Falcon-Eye se connecte au flux **Tacview Real-Time Telemetry (TRTT)** que BMS diffuse en continu sur le port 42674. Tous les contacts aériens actifs apparaissent sur la carte avec leur symbologie militaire :

- **Carré** → allié (Blue/Friendly)
- **Diamant** → hostile (Red/Bandit/Bogey)
- **Cercle** → inconnu
- Vecteurs vitesse proportionnels au cap et à la vitesse
- Trails de trajectoire (20 points)
- Labels : callsign, vitesse en nœuds, altitude FL

#### 📐 Portée radar réaliste

Falcon-Eye applique un **filtre de portée basé sur la physique réelle** du radar. Un radar au sol ne peut pas voir un avion volant en dessous de son horizon électromagnétique.

La formule utilisée est le standard aéronautique de ligne de mire :

```
R_max (NM) = 1.23 × (√altitude_avion_ft + √altitude_radar_ft)
```

Avec un site GCI à **50 ft** effectif (antenne + terrain), cela donne :

| Altitude avion | Portée maximale |
|---|---|
| 500 ft (nap de terrain) | ~37 NM |
| 5 000 ft | ~96 NM |
| 10 000 ft | ~130 NM |
| 20 000 ft | ~182 NM |
| 30 000 ft | ~222 NM |
| 40 000 ft | ~256 NM |

**Un avion en nap de terrain disparaît du scope** exactement comme dans la réalité. Le GCI doit gérer les zones d'ombre et s'appuyer sur ses pilotes pour les contacts basse altitude.

> Si le bullseye est défini dans votre fichier mission (.ini), la distance est calculée depuis ce point (position du site radar). Sans bullseye, le filtre s'applique sans contrainte de position absolue.

#### 🔴 Système BRAA

Le BRAA (Bearing, Range, Altitude, Aspect) Falcon-Eye le rend **aussi simple que possible** :

1. **Clic** sur un contact → flight strip s'ouvre
2. Cliquer **📐 BRAA** dans la strip → contact mis en surbrillance orange
3. **Clic** sur le contact cible → BRAA calculé et affiché en temps réel

Ou via **clic droit** → "📐 BRAA source" → clic sur la cible.

Chaque paire BRAA affiche :
- **B**earing — cap vers la cible (degrés)
- **R**ange — distance en NM
- **A**ltitude — altitude FL de la cible
- **A**spect — angle d'aspect (Hot/Flank/Beam/Drag)

Plusieurs paires BRAA simultanées, mise à jour live toutes les 500ms, ligne orange sur la carte.

#### 🗺️ Overlay mission

Chargez votre fichier `.ini` de mission BMS pour afficher :
- **Bullseye** avec cercles concentriques (référence GCI)
- **Route** waypoints de la mission
- **Anneaux SAM/AAA** avec portées en NM
- **Lignes FLOT** (ligne de front)
- **Points de référence** IP, waypoints tactiques

#### 📻 Radio IVC

Le panneau radio lit les **fréquences UHF/VHF directement depuis la SharedMemory BMS** — pas de configuration réseau requise. Affiche la fréquence active du cockpit en temps réel, avec les presets standard BMS accessibles en un clic.

Sélection du microphone et du haut-parleur depuis les options, avec détection automatique de tous les périphériques Windows.

#### ✈️ Flight strips

Un clic sur un contact ouvre une fiche flottante avec :
- Callsign et type d'appareil
- Vitesse (kt), cap (°), altitude (FL)
- ID code (Friendly/Hostile/Bogey...)
- Bouton BRAA

#### 🗂️ Panneau Alliés

Vue dédiée de tous les contacts amis avec leurs données, indépendante de la carte principale.

---

### Raccourcis

| Action | Commande |
|---|---|
| Zoom carte | Molette souris |
| Ouvrir flight strip | Clic gauche sur contact |
| BRAA source | Bouton BRAA dans la strip, ou clic droit → BRAA source |
| BRAA cible | Clic gauche sur le contact cible |
| Annuler BRAA en cours | Clic sur "SOURCE ✓" ou Échap |
| Règle de mesure | Clic droit sur la carte (maintenir) |
| Menu contextuel contact | Clic droit sur contact |
| Centrer sur bullseye | Bouton BULL |

---

## 🇬🇧 English

### What is it?

Falcon-Eye is a **free and open source** radar scope for **AWACS/GCI and ATC controllers** in Falcon BMS. It connects in real-time to your BMS session and displays all air contacts on a tactical map — with BRAA, bullseye, SAM rings, and integrated IVC radio.

📧 contact@falcon-charts.com — 🌐 [eye.falcon-charts.com](https://eye.falcon-charts.com)

---

### Download

👉 **[Download FalconEye.exe](../../releases/latest)**


> ⚠️ **Windows SmartScreen** may block the first launch since the exe is unsigned.  
> Click **"More info" → "Run anyway"**.

---

### Quick start

1. Launch **Falcon BMS** and start a mission
2. Launch **FalconEye.exe**
3. Leave `127.0.0.1` if BMS is on the same machine, otherwise enter the server IP
4. Click **Connecter** — contacts appear immediately

---

### Features

#### 📡 Real-time radar

Falcon-Eye connects to the **Tacview Real-Time Telemetry (TRTT)** stream broadcast by BMS on port 42674. All active air contacts appear on the map with military symbology:

- **Square** → friendly (Blue)
- **Diamond** → hostile (Red/Bandit/Bogey)
- **Circle** → unknown
- Velocity vectors proportional to heading and speed
- Trajectory trails (20 points)
- Labels: callsign, speed in knots, altitude FL

#### 📐 Realistic radar range

Falcon-Eye applies a **physics-based radar range filter**. A ground radar cannot detect aircraft flying below its electromagnetic horizon.

The formula used is the aviation standard line-of-sight:

```
R_max (NM) = 1.23 × (√aircraft_alt_ft + √radar_alt_ft)
```

With a GCI site at **50 ft** effective altitude, this gives:

| Aircraft altitude | Max range |
|---|---|
| 500 ft (low level) | ~37 NM |
| 5,000 ft | ~96 NM |
| 10,000 ft | ~130 NM |
| 20,000 ft | ~182 NM |
| 30,000 ft | ~222 NM |
| 40,000 ft | ~256 NM |

**A low-level aircraft disappears from the scope** exactly as in real life. The GCI must manage radar shadows and rely on pilots for low-altitude contacts.

#### 🔴 BRAA System

BRAA (Bearing, Range, Altitude, Aspect) is the universal GCI language. Falcon-Eye makes it **as simple as possible**:

1. **Click** on a contact → flight strip opens
2. Click **📐 BRAA** in the strip → contact highlighted in orange as source
3. **Click** on the target contact → BRAA calculated and displayed live

Or via **right-click** → "📐 BRAA source" → click target.

Each BRAA pair displays:
- **B**earing — heading to target (degrees)
- **R**ange — distance in NM
- **A**ltitude — target altitude FL
- **A**spect — aspect angle (Hot/Flank/Beam/Drag)

Multiple simultaneous BRAA pairs, live update every 500ms, orange line on map.

#### 🗺️ Mission overlay

Load your BMS `.ini` mission file to display:
- **Bullseye** with concentric rings
- **Route** mission waypoints
- **SAM/AAA rings** with ranges in NM
- **FLOT lines** (front line)
- **Reference points** IP, tactical waypoints

#### 📻 IVC Radio

The radio panel reads **UHF/VHF frequencies directly from BMS SharedMemory** — no network configuration required. Displays the active cockpit frequency in real-time, with standard BMS presets one click away.

#### ✈️ Flight strips

Click any contact to open a floating card with speed, heading, altitude, ID code, and a direct BRAA button.

---

### Controls

| Action | Input |
|---|---|
| Zoom | Mouse wheel |
| Open flight strip | Left-click contact |
| BRAA source | BRAA button in strip, or right-click → BRAA source |
| BRAA target | Left-click on target contact |
| Cancel BRAA | Click "SOURCE ✓" or Escape |
| Distance ruler | Right-click on map |
| Contact context menu | Right-click on contact |
| Center on bullseye | BULL button |

---

## Crédits / Credits

<p align="center">
  <img src="assets/credits_banner.png" width="500" alt="Credits">
</p>

**Développé par / Developed by [Riesu](https://falcon-charts.com)**

| | |
|---|---|
| 🌐 Falcon-Eye | [eye.falcon-charts.com](https://eye.falcon-charts.com) |
| 🌐 Falcon Charts | [falcon-charts.com](https://falcon-charts.com) |
| 🌐 Falcon-Pad | [pad.falcon-charts.com](https://pad.falcon-charts.com) |
| 🌐 Falcon BMS | [falcon-bms.com](https://www.falcon-bms.com) |
| 🌐 FFW01 | [ffw-01.fr](https://www.ffw-01.fr) |
| 🌐 FFW36 | [ffw36.com](http://www.ffw36.com) |

**Remerciements / Thanks:**
- **Falcon BMS Team** — pour ce superbe simulateur / for this outstanding simulator ([falcon-bms.com](https://www.falcon-bms.com))
- **FFW01** — Escadrille virtuelle F-16 ([ffw-01.fr](https://www.ffw-01.fr))
- **FFW36** — Escadrille virtuelle F-16 ([ffw36.com](http://www.ffw36.com))

**Buy Falcon 4** — [Steam](https://store.steampowered.com/app/429530/Falcon_40)

> *Falcon-Eye est un outil communautaire indépendant. Il n'existe aucun lien officiel entre Falcon-Eye et les créateurs de Falcon 4 ou de Falcon BMS.*  
> *Falcon-Eye is an independent community tool. There is no official connection between Falcon-Eye and the creators of Falcon 4 or Falcon BMS.*

---

## Licence / License

GNU General Public License v3.0 — [LICENSE](LICENSE)
