# -*- coding: utf-8 -*-
"""
IVCReader — Lit les données radio IVC depuis la SharedMemory BMS.

IVC BMS (IVC Client.exe) n'est PAS TeamSpeak — c'est le client radio
intégré à Falcon BMS. Les fréquences UHF/VHF actives sont exposées via
FalconSharedMemoryArea2. La liste des pilotes connectés n'est pas
accessible publiquement.

Ce module lit la SharedMemory pour afficher :
- La fréquence UHF/VHF active dans le cockpit
- Le statut BMS (actif/inactif)
"""
import logging
from core.shared_mem import get_radio_data, is_bms_running, format_freq

logger = logging.getLogger(__name__)


class IVCClient:
    """
    Lit les données radio depuis la SharedMemory BMS.
    
    Interface identique à l'ancien client TS3 pour compatibilité
    avec le reste du code (main_window._poll_ivc, radar widget).
    """

    def __init__(self):
        self.connected = False
        self.sock      = None   # inutilisé, conservé pour compatibilité
        self.host      = ""
        self.port      = 0
        self._uhf_freq = ""
        self._vhf_freq = ""

    def connect(self, host: str = "", port: int = 0) -> dict:
        """
        "Connexion" = vérifier que BMS tourne et la SM est accessible.
        host/port ignorés (SharedMemory locale uniquement).
        """
        if is_bms_running():
            self.connected = True
            logger.info("IVC: BMS SharedMemory accessible")
            return {"status": "ok"}
        else:
            self.connected = False
            return {
                "status": "error",
                "message": "BMS non détecté — lance Falcon BMS d'abord"
            }

    def disconnect(self):
        self.connected = False

    def get_channels(self) -> list:
        """
        Lit UHF/VHF depuis la SharedMemory et les retourne comme
        "canaux" pour compatibilité avec le panneau radio JS.
        
        Format retourné : liste de dicts compatibles updateRadio() JS.
        """
        if not is_bms_running():
            self.connected = False
            return []

        self.connected = True
        data = get_radio_data()
        if not data:
            return []

        uhf = data.get("uhf_freq", "")
        vhf = data.get("vhf_freq", "")
        self._uhf_freq = uhf
        self._vhf_freq = vhf

        uhf_ch = data.get("uhf_channel", 0)
        vhf_ch = data.get("vhf_channel", 0)

        channels = []
        if uhf:
            ch_label = f"CH{uhf_ch}" if uhf_ch else "UHF"
            channels.append({
                "id":     "uhf",
                "name":   f"{ch_label} {uhf}",
                "freq":   uhf,
                "pilots": [],
            })
        if vhf:
            ch_label = f"CH{vhf_ch}" if vhf_ch else "VHF"
            channels.append({
                "id":     "vhf",
                "name":   f"{ch_label} {vhf}",
                "freq":   vhf,
                "pilots": [],
            })

        return channels

    def get_talking(self) -> str:
        """Qui parle — non accessible via SM, toujours vide."""
        return ""

    def join_channel(self, channel_id: str) -> bool:
        """Changer de canal — non supporté via SM."""
        return False

    def get_active_freq(self) -> str:
        """Retourne la fréquence UHF active."""
        return self._uhf_freq

    @staticmethod
    def _name_to_freq(name: str) -> str:
        """Extract frequency from channel name (e.g. '225.000 GCI PRI' → '225.000')."""
        import re
        m = re.search(r"(\d{2,3}\.\d{1,3})", name)
        return m.group(1) if m else ""

    def _parse_ts3(self, raw: str) -> list:
        """Compatibilité tests — parse format TS3 (non utilisé en prod)."""
        results = []
        for block in raw.strip().split("|"):
            obj = {}
            for pair in block.strip().split(" "):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    v = (v.replace("\\s", " ")
                          .replace("\\p", "|")
                          .replace("\\n", "\n")
                          .replace("\\/", "/"))
                    obj[k] = v
            if obj:
                results.append(obj)
        return results
