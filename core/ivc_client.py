# -*- coding: utf-8 -*-
"""
IVCClient — Client TeamSpeak 3 ClientQuery (port 25639)
Connects to IVC_Client.exe's ClientQuery interface to read
radio channels, connected pilots, and who's talking.
"""
import socket
import re
import time
import logging

logger = logging.getLogger(__name__)


class IVCClient:
    """Client léger pour le ClientQuery TeamSpeak 3 (protocol texte TCP)."""

    def __init__(self):
        self.sock      = None
        self.connected = False
        self.host      = ""
        self.port      = 25639
        self._buf      = ""

    def _recv_until_error(self, timeout=3.0) -> str:
        """Read from socket until we get 'error id=' response line."""
        self.sock.settimeout(timeout)
        data = b""
        try:
            while True:
                chunk = self.sock.recv(4096)
                if not chunk:
                    break
                data += chunk
                if b"error id=" in data:
                    break
        except socket.timeout:
            pass
        return data.decode("utf-8", errors="replace")

    def _send(self, cmd: str) -> str:
        """Send command and return response (after error id= line)."""
        try:
            self.sock.sendall((cmd.strip() + "\n").encode())
            return self._recv_until_error()
        except Exception as e:
            self.connected = False
            raise

    def _flush_banner(self):
        """Read and discard initial banner lines after connect."""
        try:
            self.sock.settimeout(2)
            data = b""
            while True:
                chunk = self.sock.recv(4096)
                if not chunk:
                    break
                data += chunk
                # Banner ends with "selected schandlerid=N\n"
                if b"selected schandlerid=" in data:
                    break
                if b"error id=" in data:
                    break
            banner = data.decode("utf-8", errors="replace")
            logger.debug(f"IVC banner: {banner.strip()[:120]}")
            return banner
        except socket.timeout:
            return ""

    def connect(self, host: str, port: int = 25639) -> dict:
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5)
            self.sock.connect((host, port))
            banner = self._flush_banner()
            if "TS3" not in banner and "TeamSpeak" not in banner and "selected" not in banner:
                self.sock.close()
                return {"status": "error",
                        "message": f"Connexion refusée — port {port} fermé ou ClientQuery désactivé"}
            self.host      = host
            self.port      = port
            self.connected = True
            logger.info(f"IVC connecté {host}:{port}")
            return {"status": "ok"}
        except socket.timeout:
            return {"status": "error",
                    "message": f"Timeout — vérifier que IVC_Client.exe tourne"}
        except ConnectionRefusedError:
            return {"status": "error",
                    "message": f"Connexion refusée — port {port} fermé ou ClientQuery désactivé"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def disconnect(self):
        try:
            if self.sock:
                try:
                    self.sock.sendall(b"quit\n")
                except Exception:
                    pass
                self.sock.close()
        except Exception:
            pass
        self.connected = False
        self.sock      = None

    def _parse_ts3(self, raw: str) -> list:
        """Parse TS3 response format: key=val key=val|key=val key=val"""
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

    def get_channels(self) -> list:
        """Get all channels with connected pilots and talking status."""
        if not self.connected:
            return []
        try:
            # Get channel list
            raw_ch   = self._send("channellist")
            channels = []
            for line in raw_ch.splitlines():
                if "cid=" not in line:
                    continue
                for ch in self._parse_ts3(line):
                    cid     = ch.get("cid", "")
                    name    = ch.get("channel_name", f"Canal {cid}")
                    clients = int(ch.get("total_clients", "0"))
                    channels.append({
                        "id":      cid,
                        "name":    name,
                        "freq":    self._name_to_freq(name),
                        "clients": clients,
                        "pilots":  [],
                    })

            # Get client list with voice flags
            raw_cl = self._send("clientlist -voice")
            for line in raw_cl.splitlines():
                if "clid=" not in line:
                    continue
                for cl in self._parse_ts3(line):
                    cid     = cl.get("cid", "")
                    name    = cl.get("client_nickname", "?")
                    talking = cl.get("client_flag_talking", "0") == "1"
                    for ch in channels:
                        if ch["id"] == cid:
                            ch["pilots"].append({"name": name, "talking": talking})

            return channels
        except Exception as e:
            logger.warning(f"IVC get_channels: {e}")
            self.connected = False
            return []

    def get_talking(self) -> str:
        """Get the name of the currently talking pilot."""
        if not self.connected:
            return ""
        try:
            raw = self._send("clientlist -voice")
            for line in raw.splitlines():
                if "client_flag_talking=1" in line:
                    for cl in self._parse_ts3(line):
                        if cl.get("client_flag_talking", "0") == "1":
                            return cl.get("client_nickname", "?")
        except Exception:
            pass
        return ""

    def join_channel(self, channel_id: str) -> bool:
        """Join a specific IVC channel."""
        if not self.connected:
            return False
        try:
            resp = self._send(f"clientmove clid=0 cid={channel_id}")
            return "error id=0" in resp
        except Exception:
            return False

    @staticmethod
    def _name_to_freq(name: str) -> str:
        """Extract frequency from channel name (e.g. '225.000 GCI PRI' → '225.000')."""
        m = re.search(r"(\d{2,3}\.\d{1,3})", name)
        return m.group(1) if m else ""
