#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VR Casting Manager
Gestion du casting de casques VR via ADB WiFi et scrcpy
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import subprocess
import os
import json
import re
import threading
import time
from datetime import datetime
from pathlib import Path
from collections import deque


# =============================================================================
# CONFIGURATION ET GESTION DES FICHIERS
# =============================================================================

class ConfigManager:
    """Gestion du fichier de configuration JSON"""

    DEFAULT_CONFIG = {
        "ssid": "",
        "scrcpy_presets": {
            "Quest 3": ["--no-audio", "--angle=20", "--crop=1500:1500:370:200"],
            "Quest 2": ["--no-audio", "--crop=1080:900:270:270"],
            "Quest": ["--no-audio", "--crop=1080:900:270:270"],
            "VR_S3": ["--no-audio", "--crop=1080:1300:270:500"],
            "default": ["--no-audio"]
        }
    }

    def __init__(self, filepath="config.json"):
        # Utiliser le répertoire du script comme base
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.filepath = os.path.join(script_dir, filepath)
        self.config = self.load()

    def load(self):
        """Charge la configuration depuis le fichier JSON"""
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    for key, value in self.DEFAULT_CONFIG.items():
                        if key not in config:
                            config[key] = value
                    return config
            except (json.JSONDecodeError, IOError):
                return self.DEFAULT_CONFIG.copy()
        return self.DEFAULT_CONFIG.copy()

    def save(self):
        """Sauvegarde la configuration dans le fichier JSON"""
        with open(self.filepath, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value
        self.save()


class SessionManager:
    """Gestion du fichier de session JSON"""

    DEFAULT_SESSION = {
        "devices": {}
    }

    def __init__(self, filepath="session.json"):
        # Utiliser le répertoire du script comme base
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.filepath = os.path.join(script_dir, filepath)
        self.session = self.load()

    def load(self):
        """Charge la session depuis le fichier JSON"""
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return self.DEFAULT_SESSION.copy()
        return self.DEFAULT_SESSION.copy()

    def save(self):
        """Sauvegarde la session dans le fichier JSON"""
        with open(self.filepath, 'w', encoding='utf-8') as f:
            json.dump(self.session, f, indent=2, ensure_ascii=False)

    def get_devices(self):
        return self.session.get("devices", {})

    def add_device(self, mac_address, device_info):
        """Ajoute ou met à jour un appareil"""
        if "devices" not in self.session:
            self.session["devices"] = {}
        self.session["devices"][mac_address] = device_info
        self.save()

    def get_device(self, mac_address):
        return self.session.get("devices", {}).get(mac_address)

    def update_device(self, mac_address, key, value):
        """Met à jour une propriété d'un appareil"""
        if mac_address in self.session.get("devices", {}):
            self.session["devices"][mac_address][key] = value
            self.save()

    def clear_ips(self):
        """Efface toutes les adresses IP des appareils"""
        for mac in self.session.get("devices", {}):
            self.session["devices"][mac]["ip"] = ""
        self.save()

    def clear_all(self):
        """Efface les IPs (nouvelle session)"""
        for mac in self.session.get("devices", {}):
            self.session["devices"][mac]["ip"] = ""
        self.save()


class LogManager:
    """Gestion du fichier de log avec rotation automatique"""

    def __init__(self, filepath="casting.log", max_lines=500):
        # Utiliser le répertoire du script comme base
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.filepath = os.path.join(script_dir, filepath)
        self.max_lines = max_lines
        self.lines = deque(maxlen=max_lines)
        self.load()

    def load(self):
        """Charge les logs existants"""
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    for line in f:
                        self.lines.append(line.rstrip('\n'))
            except IOError:
                pass

    def save(self):
        """Sauvegarde les logs dans le fichier"""
        with open(self.filepath, 'w', encoding='utf-8') as f:
            for line in self.lines:
                f.write(line + '\n')

    def log(self, message):
        """Ajoute une entrée de log"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_line = f"[{timestamp}] {message}"
        self.lines.append(log_line)
        self.save()
        return log_line


# =============================================================================
# GESTIONNAIRE ADB
# =============================================================================

class ADBManager:
    """Gestion des commandes ADB"""

    def __init__(self, adb_path=None):
        # Toujours vérifier que le chemin existe, sinon chercher automatiquement
        if adb_path and os.path.exists(adb_path):
            self.adb_path = adb_path
        else:
            self.adb_path = self.find_adb_path()

    def find_adb_path(self):
        """Trouve le chemin vers adb.exe"""
        script_dir = os.path.dirname(os.path.abspath(__file__))
        scrcpy_adb = os.path.join(script_dir, "scrcpy-win64-v3.3.1-quest3-fix", "adb.exe")
        if os.path.exists(scrcpy_adb):
            return scrcpy_adb

        username = os.environ.get('USERNAME', 'User')
        sidequest_path = f"C:\\Users\\{username}\\AppData\\Local\\Programs\\SideQuest\\resources\\app.asar.unpacked\\build\\platform-tools\\adb.exe"
        if os.path.exists(sidequest_path):
            return sidequest_path

        return None

    def run_command(self, command, device_id=None, timeout=30):
        """Exécute une commande ADB"""
        if not self.adb_path:
            return "", "ADB not found", 1

        try:
            if device_id:
                cmd = [self.adb_path, "-s", device_id] + command
            else:
                cmd = [self.adb_path] + command

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            return result.stdout or "", result.stderr or "", result.returncode
        except subprocess.TimeoutExpired:
            return "", "Command timeout", 1
        except Exception as e:
            return "", str(e), 1

    def get_devices(self):
        """Retourne la liste des appareils connectés"""
        stdout, stderr, rc = self.run_command(["devices"])
        devices = []
        if rc == 0:
            for line in stdout.strip().split('\n')[1:]:
                if '\tdevice' in line:
                    device_id = line.split('\t')[0]
                    devices.append(device_id)
        return devices

    def get_device_model(self, device_id):
        """Récupère le modèle de l'appareil"""
        stdout, _, rc = self.run_command(["shell", "getprop", "ro.product.model"], device_id)
        if rc == 0:
            return stdout.strip()
        return "Unknown"

    def get_device_ip(self, device_id):
        """Récupère l'adresse IP WiFi de l'appareil"""
        stdout, _, rc = self.run_command(["shell", "ip", "addr", "show", "wlan0"], device_id)
        if rc == 0:
            match = re.search(r'inet (\d+\.\d+\.\d+\.\d+)', stdout)
            if match:
                return match.group(1)
        return None

    def get_device_ssid(self, device_id):
        """Récupère le SSID WiFi de l'appareil"""
        # Utilise grep sur le device pour éviter les problèmes d'encodage avec le dump complet
        stdout, _, rc = self.run_command(["shell", "dumpsys wifi | grep mWifiInfo | head -1"], device_id)
        if rc == 0:
            # Supporte les deux formats: SSID: vr-cegep, ou SSID: "vr-cegep",
            match = re.search(r'SSID: "?([^",]+)"?', stdout)
            if match:
                return match.group(1)
        return None

    def get_device_mac(self, device_id):
        """Récupère l'adresse MAC de l'appareil"""
        # Utilise grep sur le device pour éviter les problèmes d'encodage avec le dump complet
        stdout, _, rc = self.run_command(["shell", "dumpsys wifi | grep mWifiInfo | head -1"], device_id)
        if rc == 0:
            match = re.search(r'MAC: ([0-9a-fA-F:]+)', stdout)
            if match:
                return match.group(1).lower()
        return None

    def get_battery_level(self, device_id):
        """Récupère le niveau de batterie"""
        stdout, _, rc = self.run_command(["shell", "dumpsys", "battery"], device_id)
        if rc == 0:
            match = re.search(r'level: (\d+)', stdout)
            if match:
                return int(match.group(1))
        return None

    def get_controller_batteries(self, device_id):
        """Récupère les niveaux de batterie des manettes"""
        stdout, _, rc = self.run_command(["shell", "dumpsys", "OVRRemoteService"], device_id)
        left_battery = None
        right_battery = None

        if rc == 0:
            lines = stdout.split('\n')
            for line in lines:
                if 'Type:' in line and 'Battery:' in line:
                    battery_match = re.search(r'Battery:\s*(\d+)%', line)
                    if battery_match:
                        battery = int(battery_match.group(1))
                        if 'Right' in line:
                            right_battery = battery
                        elif 'Left' in line:
                            left_battery = battery

        return left_battery, right_battery

    def get_volume(self, device_id):
        """Récupère le niveau de volume"""
        stdout, _, rc = self.run_command(["shell", "settings", "get", "system", "volume_music_speaker"], device_id)
        if rc == 0:
            try:
                return int(stdout.strip())
            except ValueError:
                pass
        return None

    def set_volume_up(self, device_id):
        """Augmente le volume"""
        self.run_command(["shell", "input", "keyevent", "KEYCODE_VOLUME_UP"], device_id)

    def set_volume_down(self, device_id):
        """Diminue le volume"""
        self.run_command(["shell", "input", "keyevent", "KEYCODE_VOLUME_DOWN"], device_id)

    def get_current_app(self, device_id):
        """Récupère l'application en cours"""
        stdout, _, rc = self.run_command(["shell", "dumpsys", "window"], device_id)
        if rc == 0:
            matches = re.findall(r'mCurrentFocus=Window\{[^}]+ ([^\s}]+)\}', stdout)
            if matches:
                return matches[-1]
        return None

    def close_app(self, device_id, package_name):
        """Ferme une application"""
        if '/' in package_name:
            package_name = package_name.split('/')[0]
        self.run_command(["shell", "am", "force-stop", package_name], device_id)

    def disable_proximity_sensor(self, device_id):
        """Désactive le capteur de proximité"""
        stdout, stderr, rc = self.run_command(
            ["shell", "am", "broadcast", "-a", "com.oculus.vrpowermanager.prox_close"],
            device_id
        )
        return rc == 0

    def enable_proximity_sensor(self, device_id):
        """Active le capteur de proximité"""
        stdout, stderr, rc = self.run_command(
            ["shell", "am", "broadcast", "-a", "com.oculus.vrpowermanager.automation_disable"],
            device_id
        )
        return rc == 0

    def enable_wifi_adb(self, device_id):
        """Active ADB over WiFi"""
        stdout, stderr, rc = self.run_command(["tcpip", "5555"], device_id)
        return rc == 0

    def connect_wifi(self, ip_address):
        """Connecte à un appareil via WiFi (tentative unique)"""
        print(f"[ADB] Connexion à {ip_address}:5555...")
        stdout, stderr, rc = self.run_command(["connect", f"{ip_address}:5555"], timeout=5)
        print(f"[ADB] Réponse: stdout='{stdout.strip()}', stderr='{stderr.strip()}', rc={rc}")

        if "connected" in stdout.lower() or "already connected" in stdout.lower():
            print(f"[ADB] Connexion réussie!")
            return True

        print(f"[ADB] Connexion échouée")
        return False

    def disconnect_wifi(self, ip_address):
        """Déconnecte un appareil WiFi"""
        self.run_command(["disconnect", f"{ip_address}:5555"])

    def open_wifi_settings(self, device_id):
        """Ouvre les paramètres WiFi sur l'appareil"""
        self.run_command(["shell", "am", "start", "-a", "android.settings.WIFI_SETTINGS"], device_id)


def get_pc_ssid():
    """Récupère le SSID WiFi du PC (Windows)"""
    try:
        result = subprocess.run(
            ["netsh", "wlan", "show", "interfaces"],
            capture_output=True, timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        if result.returncode == 0:
            # Décoder avec gestion des erreurs pour éviter UnicodeDecodeError
            try:
                output = result.stdout.decode('utf-8')
            except UnicodeDecodeError:
                try:
                    output = result.stdout.decode('cp850')  # Encodage Windows français
                except UnicodeDecodeError:
                    output = result.stdout.decode('latin-1', errors='replace')

            for line in output.split('\n'):
                if 'SSID' in line and 'BSSID' not in line:
                    parts = line.split(':')
                    if len(parts) >= 2:
                        ssid = ':'.join(parts[1:]).strip()
                        if ssid:
                            return ssid
    except Exception:
        pass
    return None


# =============================================================================
# GESTIONNAIRE SCRCPY
# =============================================================================

class ScrcpyManager:
    """Gestion du casting scrcpy"""

    def __init__(self, scrcpy_path=None):
        # Toujours vérifier que le chemin existe, sinon chercher automatiquement
        if scrcpy_path and os.path.exists(scrcpy_path):
            self.scrcpy_path = scrcpy_path
        else:
            self.scrcpy_path = self.find_scrcpy_path()
        self.processes = {}

    def find_scrcpy_path(self):
        """Trouve le chemin vers scrcpy.exe"""
        script_dir = os.path.dirname(os.path.abspath(__file__))
        scrcpy_path = os.path.join(script_dir, "scrcpy-win64-v3.3.1-quest3-fix", "scrcpy.exe")
        if os.path.exists(scrcpy_path):
            return scrcpy_path
        return None

    def start_casting(self, device_id, nickname, params):
        """Démarre le casting pour un appareil"""
        if not self.scrcpy_path:
            return False, "scrcpy.exe non trouvé"

        # Fermer le casting existant s'il y en a un
        if device_id in self.processes:
            self.stop_casting(device_id)

        try:
            cmd = [self.scrcpy_path, "-s", device_id] + params + ["--window-title", nickname]
            # Ne pas utiliser CREATE_NO_WINDOW pour scrcpy car on veut voir la fenêtre de casting!
            process = subprocess.Popen(cmd)
            self.processes[device_id] = process
            return True, "Casting démarré"
        except Exception as e:
            return False, str(e)

    def stop_casting(self, device_id):
        """Arrête le casting pour un appareil"""
        if device_id in self.processes:
            try:
                self.processes[device_id].terminate()
                del self.processes[device_id]
            except Exception:
                pass


# =============================================================================
# FENÊTRE DE DÉMARRAGE
# =============================================================================

def show_startup_dialog():
    """Affiche le dialogue de démarrage et retourne le choix"""
    result = {"choice": None}

    root = tk.Tk()
    root.title("VR Casting Manager")
    root.geometry("450x180")
    root.resizable(False, False)

    # Centrer la fenêtre
    root.update_idletasks()
    x = (root.winfo_screenwidth() - 450) // 2
    y = (root.winfo_screenheight() - 180) // 2
    root.geometry(f"+{x}+{y}")

    def on_continue():
        result["choice"] = "continue"
        root.destroy()

    def on_new():
        if messagebox.askyesno(
            "Confirmation",
            "Es-tu certain?\n\nIl te faudra rebrancher tous les casques avec un fil USB.",
            parent=root
        ):
            result["choice"] = "new"
            root.destroy()

    def on_close():
        result["choice"] = None
        root.destroy()

    # Contenu
    tk.Label(
        root,
        text="VR Casting Manager",
        font=("Helvetica", 18, "bold")
    ).pack(pady=20)

    tk.Label(
        root,
        text="Comment voulez-vous démarrer?",
        font=("Helvetica", 11)
    ).pack(pady=10)

    btn_frame = tk.Frame(root)
    btn_frame.pack(pady=20)

    tk.Button(
        btn_frame,
        text="Continuer la session précédente",
        command=on_continue,
        width=28,
        height=2
    ).pack(side="left", padx=10)

    tk.Button(
        btn_frame,
        text="Nouvelle session",
        command=on_new,
        width=20,
        height=2
    ).pack(side="left", padx=10)

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()

    return result["choice"]


# =============================================================================
# DIALOGUE DE CONFIGURATION D'APPAREIL
# =============================================================================

class DeviceSetupDialog:
    """Dialogue de configuration d'un nouvel appareil"""

    def __init__(self, parent, device_info, adb_manager, log_callback):
        self.result = None
        self.device_info = device_info
        self.adb = adb_manager
        self.log = log_callback

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"Configuration - {device_info['model']}")
        self.dialog.geometry("450x350")
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # Centrer
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() - 450) // 2
        y = (self.dialog.winfo_screenheight() - 350) // 2
        self.dialog.geometry(f"+{x}+{y}")

        # Titre
        tk.Label(
            self.dialog,
            text=f"Configuration de {device_info['model']}",
            font=("Helvetica", 12, "bold")
        ).pack(pady=10)

        # Frame pour les étapes
        self.steps_frame = tk.Frame(self.dialog)
        self.steps_frame.pack(fill="x", padx=20, pady=10)

        # Étapes de vérification
        self.steps = [
            ("mac", "Adresse MAC"),
            ("ip", "Adresse IP"),
            ("model", "Type d'appareil"),
            ("adb_wifi", "ADB over WiFi"),
            ("proximity", "Proximity sensor désactivé")
        ]

        self.step_labels = {}
        self.step_status = {}

        for key, text in self.steps:
            frame = tk.Frame(self.steps_frame)
            frame.pack(fill="x", pady=2)

            status_label = tk.Label(frame, text="[ ]", width=4)
            status_label.pack(side="left")
            self.step_status[key] = status_label

            text_label = tk.Label(frame, text=text, anchor="w", width=25)
            text_label.pack(side="left", padx=5)

            value_label = tk.Label(frame, text="...", anchor="w", fg="gray")
            value_label.pack(side="left", padx=5)
            self.step_labels[key] = value_label

        # Boutons
        self.btn_frame = tk.Frame(self.dialog)
        self.btn_frame.pack(pady=20)

        self.cancel_btn = tk.Button(
            self.btn_frame,
            text="Annuler",
            command=self.cancel,
            width=15
        )
        self.cancel_btn.pack(side="left", padx=10)

        # Lancer la configuration
        self.dialog.after(500, self.run_setup)

    def update_step(self, key, success, value=""):
        """Met à jour l'affichage d'une étape"""
        if success:
            self.step_status[key].config(text="[OK]", fg="green")
            self.step_labels[key].config(text=value, fg="black")
        else:
            self.step_status[key].config(text="[X]", fg="red")
            self.step_labels[key].config(text=value, fg="red")
        self.dialog.update()

    def run_setup(self):
        """Exécute les étapes de configuration"""
        device_id = self.device_info['device_id']
        success = True
        print(f"[Setup] Démarrage pour {device_id}")

        # 1. MAC Address
        print(f"[Setup] Étape 1: MAC Address...")
        mac = self.adb.get_device_mac(device_id)
        if mac:
            self.device_info['mac'] = mac
            self.update_step("mac", True, mac)
            print(f"[Setup] MAC: {mac}")
        else:
            self.update_step("mac", False, "Non trouvée")
            print(f"[Setup] MAC: ÉCHEC")
            success = False

        # 2. IP Address
        print(f"[Setup] Étape 2: IP Address...")
        ip = self.adb.get_device_ip(device_id)
        if ip:
            self.device_info['ip'] = ip
            self.update_step("ip", True, ip)
            print(f"[Setup] IP: {ip}")
        else:
            self.update_step("ip", False, "Non trouvée")
            print(f"[Setup] IP: ÉCHEC")
            success = False

        # 3. Model (déjà récupéré)
        self.update_step("model", True, self.device_info['model'])
        print(f"[Setup] Modèle: {self.device_info['model']}")

        # 4. ADB over WiFi
        print(f"[Setup] Étape 4: ADB over WiFi...")
        if success:
            if self.adb.enable_wifi_adb(device_id):
                print(f"[Setup] tcpip 5555 OK, attente 3s...")
                time.sleep(3)
                if ip and self.adb.connect_wifi(ip):
                    self.update_step("adb_wifi", True, f"{ip}:5555")
                    print(f"[Setup] Connexion WiFi: OK")
                else:
                    self.update_step("adb_wifi", False, "Connexion échouée")
                    print(f"[Setup] Connexion WiFi: ÉCHEC")
                    success = False
            else:
                self.update_step("adb_wifi", False, "Activation échouée")
                print(f"[Setup] tcpip 5555: ÉCHEC")
                success = False
        else:
            self.update_step("adb_wifi", False, "Étape précédente échouée")
            print(f"[Setup] ADB WiFi: sauté (erreur précédente)")

        # 5. Disable proximity
        print(f"[Setup] Étape 5: Désactiver proximity...")
        if success:
            wifi_device_id = f"{ip}:5555"
            if self.adb.disable_proximity_sensor(wifi_device_id):
                self.update_step("proximity", True, "Commande OK")
                print(f"[Setup] Proximity: commande envoyée (rc=0)")
            else:
                self.update_step("proximity", False, "Commande échouée")
                print(f"[Setup] Proximity: commande ÉCHOUÉE (rc!=0)")
                success = False
        else:
            self.update_step("proximity", False, "Étape précédente échouée")
            print(f"[Setup] Proximity: sauté (erreur précédente)")

        # Résultat
        print(f"[Setup] Résultat: {'SUCCÈS' if success else 'ÉCHEC'}")
        if success:
            self.result = self.device_info
            self.ask_nickname()
        else:
            messagebox.showerror(
                "Erreur",
                "La configuration a échoué. Veuillez reconnecter l'appareil et réessayer.",
                parent=self.dialog
            )

    def ask_nickname(self):
        """Demande le nickname de l'appareil"""
        default_name = self.device_info.get('mac', 'Device')

        nickname = simpledialog.askstring(
            "Nom de l'appareil",
            f"Quel est le nom de cet appareil?\n(exemple: Q3-07 ou A-13)\n\nPar défaut: {default_name}",
            initialvalue=default_name,
            parent=self.dialog
        )

        if nickname:
            self.device_info['nickname'] = nickname
        else:
            self.device_info['nickname'] = default_name

        self.dialog.destroy()

    def cancel(self):
        self.result = None
        self.dialog.destroy()


# =============================================================================
# APPLICATION PRINCIPALE
# =============================================================================

class VRCastingManager:
    """Application principale"""

    def __init__(self, session_mode):
        self.root = tk.Tk()
        self.root.title("VR Casting Manager")
        self.root.geometry("1100x700")

        # Gestionnaires
        self.config = ConfigManager()
        self.session = SessionManager()
        self.log_manager = LogManager()
        self.adb = ADBManager()
        self.scrcpy = ScrcpyManager()

        # État
        self.usb_detection_active = False
        self.usb_detection_thread = None
        self.device_widgets = {}
        self.proximity_states = {}  # Track proximity sensor state per device (True=enabled, False=disabled)

        # Traiter le mode de session
        if session_mode == "new":
            self.session.clear_all()
            self.log("Nouvelle session démarrée")
        else:
            self.log("Session précédente reprise")

        # Créer l'interface
        self.create_interface()

        # Vérifier le SSID après un court délai
        self.root.after(500, self.check_ssid_on_startup)

    def log(self, message):
        """Ajoute un message au log"""
        log_line = self.log_manager.log(message)
        if hasattr(self, 'log_text'):
            self.log_text.insert(tk.END, log_line + "\n")
            self.log_text.see(tk.END)
        print(log_line)

    def check_ssid_on_startup(self):
        """Vérifie le SSID au démarrage"""
        configured_ssid = self.config.get("ssid")
        current_ssid = get_pc_ssid()

        if not configured_ssid:
            if current_ssid:
                messagebox.showinfo(
                    "Configuration WiFi",
                    f"Ton SSID actuel est '{current_ssid}' et sera utilisé pour le casting."
                )
                self.config.set("ssid", current_ssid)
                self.update_ssid_display()
            else:
                messagebox.showwarning(
                    "WiFi non détecté",
                    "Impossible de détecter ton réseau WiFi. Assure-toi d'être connecté."
                )
        else:
            if current_ssid and current_ssid != configured_ssid:
                result = messagebox.askquestion(
                    "SSID différent",
                    f"Ton SSID actuel ({current_ssid}) ne correspond pas à celui configuré ({configured_ssid}).\n\n"
                    f"Assure-toi d'être sur le bon réseau!\n\n"
                    f"Veux-tu utiliser '{current_ssid}' à la place?",
                    icon='warning'
                )
                if result == 'yes':
                    self.config.set("ssid", current_ssid)
            self.update_ssid_display()

    def update_ssid_display(self):
        """Met à jour l'affichage du SSID"""
        ssid = self.config.get("ssid", "Non configuré")
        self.ssid_label.config(text=f"SSID: {ssid}")

    def create_interface(self):
        """Crée l'interface principale"""
        # Frame supérieur avec infos et boutons
        top_frame = tk.Frame(self.root)
        top_frame.pack(fill="x", padx=10, pady=5)

        # Info SSID
        self.ssid_label = tk.Label(top_frame, text="SSID: ...", font=("Helvetica", 11))
        self.ssid_label.pack(side="left", padx=10)

        # Boutons
        btn_frame = tk.Frame(top_frame)
        btn_frame.pack(side="right")

        self.usb_detect_btn = tk.Button(
            btn_frame,
            text="Détection USB",
            command=self.toggle_usb_detection,
            width=15
        )
        self.usb_detect_btn.pack(side="left", padx=5)

        tk.Button(
            btn_frame,
            text="Reconnection/Refresh",
            command=self.reconnect_refresh,
            width=18
        ).pack(side="left", padx=5)

        tk.Button(
            btn_frame,
            text="Effacer les IPs",
            command=self.clear_ips,
            width=12,
            state="disabled"
        ).pack(side="left", padx=5)

        # Séparateur
        ttk.Separator(self.root, orient="horizontal").pack(fill="x", padx=10, pady=5)

        # Frame pour le tableau des appareils
        table_frame = tk.Frame(self.root)
        table_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # Canvas avec scrollbar pour le tableau
        self.canvas = tk.Canvas(table_frame)
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)

        # En-têtes du tableau
        headers = ["Nom", "IP", "Modèle", "Proximity", "App", "Volume", "Batterie", "Manettes", "Casting"]
        header_frame = tk.Frame(self.scrollable_frame)
        header_frame.pack(fill="x", pady=5)

        widths = [12, 15, 10, 8, 25, 8, 8, 12, 8]
        for i, (header, width) in enumerate(zip(headers, widths)):
            tk.Label(
                header_frame,
                text=header,
                font=("Helvetica", 10, "bold"),
                width=width,
                anchor="w"
            ).grid(row=0, column=i, padx=2)

        # Frame pour les appareils
        self.devices_frame = tk.Frame(self.scrollable_frame)
        self.devices_frame.pack(fill="both", expand=True)

        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Bind mousewheel
        self.canvas.bind("<MouseWheel>", lambda e: self.canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

        # Séparateur
        ttk.Separator(self.root, orient="horizontal").pack(fill="x", padx=10, pady=5)

        # Zone de logs
        log_frame = tk.Frame(self.root)
        log_frame.pack(fill="x", padx=10, pady=5)

        tk.Label(log_frame, text="Logs:", font=("Helvetica", 10, "bold")).pack(anchor="w")

        self.log_text = tk.Text(log_frame, height=8, font=("Consolas", 9))
        log_scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scrollbar.set)

        self.log_text.pack(side="left", fill="both", expand=True)
        log_scrollbar.pack(side="right", fill="y")

        # Charger les appareils existants
        self.refresh_devices_display()

    def toggle_usb_detection(self):
        """Active/désactive la détection USB"""
        if self.usb_detection_active:
            self.usb_detection_active = False
            self.usb_detect_btn.config(relief="raised", bg="SystemButtonFace")
            self.log("Détection USB désactivée")
        else:
            self.usb_detection_active = True
            self.usb_detect_btn.config(relief="sunken", bg="lightgreen")
            self.log("Détection USB activée")
            self.usb_detection_thread = threading.Thread(target=self.usb_detection_loop, daemon=True)
            self.usb_detection_thread.start()

    def usb_detection_loop(self):
        """Boucle de détection des appareils USB"""
        known_macs = set()
        seen_usb_devices = set()  # Track les device_id USB actuellement branchés

        # Récupérer les MAC des appareils déjà connus
        for mac, info in self.session.get_devices().items():
            known_macs.add(mac)

        self.root.after(0, lambda: self.log(f"Détection USB: {len(known_macs)} appareil(s) déjà connu(s)"))

        while self.usb_detection_active:
            try:
                devices = self.adb.get_devices()
                usb_devices = [d for d in devices if ':' not in d]
                current_usb_set = set(usb_devices)

                # Détecter les NOUVEAUX appareils USB (branchés depuis le dernier scan)
                new_usb_devices = current_usb_set - seen_usb_devices

                # Mettre à jour les appareils vus (retirer les débranchés, ajouter les nouveaux)
                seen_usb_devices = current_usb_set

                if new_usb_devices:
                    self.root.after(0, lambda devs=new_usb_devices: self.log(f"Nouveau(x) branchement(s): {len(devs)} appareil(s)"))

                for device_id in new_usb_devices:
                    # Récupérer la MAC
                    mac = self.adb.get_device_mac(device_id)

                    if not mac:
                        self.root.after(0, lambda d=device_id: self.log(f"  - {d}: impossible de récupérer la MAC"))
                        continue

                    if mac in known_macs:
                        # Casque connu - vérifier IP et refaire connexion ADB WiFi
                        self.root.after(0, lambda d=device_id, m=mac: self.log(f"  - {d}: déjà connu (MAC: {m}), vérification..."))
                        self.root.after(0, lambda d=device_id, m=mac: self.handle_known_device_reconnect(d, m))
                        continue

                    # Nouvel appareil détecté
                    self.root.after(0, lambda d=device_id, m=mac: self.log(f"  - {d}: NOUVEAU! (MAC: {m})"))
                    self.root.after(0, lambda d=device_id, m=mac: self.handle_new_device(d, m))
                    known_macs.add(mac)

                time.sleep(3)
            except Exception as e:
                self.root.after(0, lambda err=str(e): self.log(f"Erreur détection: {err}"))
                time.sleep(5)

    def handle_new_device(self, device_id, mac):
        """Gère un nouvel appareil détecté"""
        self.log(f"Configuration de {device_id}...")

        # Vérifier le SSID
        self.log(f"  Vérification du SSID...")
        device_ssid = self.adb.get_device_ssid(device_id)
        configured_ssid = self.config.get("ssid")
        self.log(f"  SSID appareil: {device_ssid}, SSID config: {configured_ssid}")

        if device_ssid != configured_ssid:
            self.log(f"  ERREUR: Mauvais SSID!")
            messagebox.showwarning(
                "Mauvais réseau WiFi",
                f"L'appareil est sur '{device_ssid}' plutôt que '{configured_ssid}'!\n\n"
                f"Connecte-le au bon réseau et réessaie.",
                parent=self.root
            )
            # Ouvrir les paramètres WiFi
            self.adb.open_wifi_settings(device_id)
            return

        # Récupérer le modèle
        self.log(f"  Récupération du modèle...")
        model = self.adb.get_device_model(device_id)
        self.log(f"  Modèle: {model}")

        # Vérifier si on a déjà un nickname pour cette MAC
        existing = self.session.get_device(mac)
        existing_nickname = existing.get('nickname') if existing else None
        if existing_nickname:
            self.log(f"  Nickname existant trouvé: {existing_nickname}")

        device_info = {
            'device_id': device_id,
            'mac': mac,
            'model': model,
            'ssid': device_ssid
        }

        # Ouvrir le dialogue de configuration
        self.log(f"  Ouverture du dialogue de configuration...")
        setup_dialog = DeviceSetupDialog(self.root, device_info, self.adb, self.log)
        self.root.wait_window(setup_dialog.dialog)

        if setup_dialog.result:
            # Utiliser le nickname existant si disponible
            if existing_nickname:
                setup_dialog.result['nickname'] = existing_nickname

            # Sauvegarder l'appareil
            self.session.add_device(mac, setup_dialog.result)
            self.log(f"Appareil configuré: {setup_dialog.result['nickname']}")

            # Initialiser l'état de proximité comme désactivé (fait pendant le setup)
            ip = setup_dialog.result.get('ip')
            if ip:
                self.proximity_states[f"{ip}:5555"] = False

            # Rafraîchir l'affichage
            self.refresh_devices_display()
        else:
            self.log(f"  Configuration annulée ou échouée")

    def handle_known_device_reconnect(self, device_id, mac):
        """Gère la reconnexion d'un casque déjà connu via USB"""
        existing = self.session.get_device(mac)
        if not existing:
            self.log(f"  Erreur: appareil {mac} non trouvé dans la session")
            return

        nickname = existing.get('nickname', mac)
        old_ip = existing.get('ip', '')
        self.log(f"  Reconnexion de {nickname}...")

        # 1. Vérifier le SSID
        device_ssid = self.adb.get_device_ssid(device_id)
        configured_ssid = self.config.get("ssid")
        if device_ssid != configured_ssid:
            self.log(f"  {nickname}: ERREUR - mauvais WiFi ({device_ssid} au lieu de {configured_ssid})")
            messagebox.showwarning(
                "Mauvais réseau WiFi",
                f"{nickname} est sur '{device_ssid}' au lieu de '{configured_ssid}'!\n\n"
                f"Connecte-le au bon réseau WiFi.",
                parent=self.root
            )
            return

        # 2. Récupérer l'IP actuelle
        new_ip = self.adb.get_device_ip(device_id)
        if not new_ip:
            self.log(f"  {nickname}: impossible de récupérer l'IP (WiFi connecté?)")
            return

        # 3. Comparer les IPs
        if new_ip != old_ip:
            self.log(f"  {nickname}: IP changée ({old_ip} -> {new_ip})")
            self.session.update_device(mac, 'ip', new_ip)
        else:
            self.log(f"  {nickname}: même IP ({new_ip})")

        # 4. Activer ADB over WiFi (tcpip 5555)
        self.log(f"  {nickname}: activation ADB WiFi... (accepte le USB Debug dans le casque si demandé!)")
        if not self.adb.enable_wifi_adb(device_id):
            self.log(f"  {nickname}: ÉCHEC tcpip 5555 - as-tu accepté le USB Debug dans le casque?")
            messagebox.showwarning(
                "USB Debug requis",
                f"{nickname}: La connexion ADB a échoué.\n\n"
                f"As-tu accepté la demande 'Autoriser le débogage USB' dans le casque?\n\n"
                f"Débranche et rebranche le casque, puis accepte la demande.",
                parent=self.root
            )
            return

        # Attendre que le mode TCP soit actif
        time.sleep(2)

        # 5. Connexion WiFi
        self.log(f"  {nickname}: connexion à {new_ip}:5555...")
        if self.adb.connect_wifi(new_ip):
            self.log(f"  {nickname}: connecté!")
            # Rafraîchir l'affichage
            self.root.after(0, self.refresh_devices_display)
        else:
            self.log(f"  {nickname}: ÉCHEC connexion WiFi")

    def reconnect_refresh(self):
        """Reconnecte tous les appareils et rafraîchit les infos"""
        self.log("Reconnexion et rafraîchissement...")

        def do_refresh():
            devices = self.session.get_devices()

            for mac, info in devices.items():
                ip = info.get('ip')
                if ip:
                    nickname = info.get('nickname', mac)
                    if self.adb.connect_wifi(ip):
                        self.root.after(0, lambda n=nickname: self.log(f"Connecté: {n}"))
                    else:
                        self.root.after(0, lambda n=nickname: self.log(f"Échec connexion: {n}"))

            # Rafraîchir l'affichage
            self.root.after(0, self.refresh_devices_display)

        thread = threading.Thread(target=do_refresh, daemon=True)
        thread.start()

    def clear_ips(self):
        """Efface toutes les IPs"""
        if messagebox.askyesno("Confirmation", "Effacer toutes les adresses IP?"):
            self.session.clear_ips()
            self.refresh_devices_display()
            self.log("Adresses IP effacées")

    def refresh_devices_display(self):
        """Rafraîchit l'affichage des appareils"""
        # Supprimer les widgets existants
        for widget in self.devices_frame.winfo_children():
            widget.destroy()
        self.device_widgets.clear()

        devices = self.session.get_devices()
        self.log(f"[DEBUG] Appareils chargés: {len(devices)}")
        for mac, info in devices.items():
            self.log(f"[DEBUG]   {info.get('nickname', mac)}: IP={info.get('ip', 'VIDE')}")

        # Récupérer la liste des appareils connectés UNE SEULE FOIS avant la boucle
        connected_devices = self.adb.get_devices()

        for mac, info in devices.items():
            ip = info.get('ip', '')
            if not ip:
                continue

            device_id = f"{ip}:5555"

            # Vérifier si l'appareil est connecté
            is_connected = device_id in connected_devices
            text_color = "black" if is_connected else "red"

            # Créer une ligne pour cet appareil
            row_frame = tk.Frame(self.devices_frame)
            row_frame.pack(fill="x", pady=2)

            # Nom
            nickname = info.get('nickname', mac)
            tk.Label(row_frame, text=nickname, width=12, anchor="w", fg=text_color).grid(row=0, column=0, padx=2)

            # IP
            tk.Label(row_frame, text=ip, width=15, anchor="w", fg=text_color).grid(row=0, column=1, padx=2)

            # Modèle
            model = info.get('model', 'Unknown')
            tk.Label(row_frame, text=model, width=10, anchor="w", fg=text_color).grid(row=0, column=2, padx=2)

            # Proximity (cliquable) - par défaut désactivé car on le désactive au setup
            is_prox_enabled = self.proximity_states.get(device_id, False)  # False = désactivé par défaut (setup)
            prox_text = "ON" if is_prox_enabled else "OFF"
            prox_color = "lightgreen" if is_prox_enabled else "salmon"
            prox_btn = tk.Button(
                row_frame, text=prox_text, width=8, bg=prox_color,
                command=lambda d=device_id: self.toggle_proximity(d)
            )
            prox_btn.grid(row=0, column=3, padx=2)

            # App en cours (cliquable pour fermer)
            app_label = tk.Label(row_frame, text="...", width=25, anchor="w", cursor="hand2", fg="blue")
            app_label.grid(row=0, column=4, padx=2)
            app_label.bind("<Button-1>", lambda e, d=device_id, l=app_label: self.show_app_menu(e, d, l))

            # Volume avec + et -
            vol_frame = tk.Frame(row_frame)
            vol_frame.grid(row=0, column=5, padx=2)
            tk.Button(vol_frame, text="-", width=2, command=lambda d=device_id: self.volume_down(d)).pack(side="left")
            vol_label = tk.Label(vol_frame, text="...", width=3)
            vol_label.pack(side="left")
            tk.Button(vol_frame, text="+", width=2, command=lambda d=device_id: self.volume_up(d)).pack(side="left")

            # Batterie casque
            battery_label = tk.Label(row_frame, text="...%", width=8, anchor="w", fg=text_color)
            battery_label.grid(row=0, column=6, padx=2)

            # Batteries manettes
            controllers_label = tk.Label(row_frame, text="L:.. R:..", width=12, anchor="w", fg=text_color)
            controllers_label.grid(row=0, column=7, padx=2)

            # Bouton casting
            cast_btn = tk.Button(
                row_frame, text="Cast", width=8, bg="lightblue",
                command=lambda d=device_id, n=nickname, m=model: self.start_casting(d, n, m)
            )
            cast_btn.grid(row=0, column=8, padx=2)

            # Stocker les références
            self.device_widgets[mac] = {
                'row': row_frame,
                'app': app_label,
                'volume': vol_label,
                'battery': battery_label,
                'controllers': controllers_label,
                'device_id': device_id,
                'prox_btn': prox_btn
            }

        # Mettre à jour les infos
        if self.device_widgets:
            self.update_devices_info()

    def update_devices_info(self):
        """Met à jour les informations de tous les appareils"""
        def do_update():
            for mac, widgets in list(self.device_widgets.items()):
                device_id = widgets['device_id']

                try:
                    # App en cours
                    app = self.adb.get_current_app(device_id)
                    if app:
                        display_app = app[:25] + "..." if len(app) > 25 else app
                        self.root.after(0, lambda w=widgets['app'], a=display_app: w.config(text=a))

                    # Volume
                    vol = self.adb.get_volume(device_id)
                    if vol is not None:
                        self.root.after(0, lambda w=widgets['volume'], v=vol: w.config(text=str(v)))

                    # Batterie
                    battery = self.adb.get_battery_level(device_id)
                    if battery is not None:
                        self.root.after(0, lambda w=widgets['battery'], b=battery: w.config(text=f"{b}%"))

                    # Manettes
                    left, right = self.adb.get_controller_batteries(device_id)
                    ctrl_text = f"L:{left or '?'} R:{right or '?'}"
                    self.root.after(0, lambda w=widgets['controllers'], t=ctrl_text: w.config(text=t))

                except Exception:
                    pass

        thread = threading.Thread(target=do_update, daemon=True)
        thread.start()

    def toggle_proximity(self, device_id):
        """Toggle le capteur de proximité"""
        # Récupérer l'état actuel (par défaut: activé)
        current_state = self.proximity_states.get(device_id, True)

        if current_state:
            # Actuellement activé -> désactiver
            success = self.adb.disable_proximity_sensor(device_id)
            if success:
                self.proximity_states[device_id] = False
                self.log(f"Proximity: commande désactivation envoyée")
                # Mettre à jour le bouton
                self.update_proximity_button(device_id, False)
            else:
                self.log(f"Proximity: ÉCHEC désactivation (commande ADB échouée)")
        else:
            # Actuellement désactivé -> activer
            success = self.adb.enable_proximity_sensor(device_id)
            if success:
                self.proximity_states[device_id] = True
                self.log(f"Proximity: commande activation envoyée")
                # Mettre à jour le bouton
                self.update_proximity_button(device_id, True)
            else:
                self.log(f"Proximity: ÉCHEC activation (commande ADB échouée)")

    def update_proximity_button(self, device_id, is_enabled):
        """Met à jour l'apparence du bouton proximity"""
        for mac, widgets in self.device_widgets.items():
            if widgets.get('device_id') == device_id:
                btn = widgets.get('prox_btn')
                if btn:
                    if is_enabled:
                        btn.config(text="ON", bg="lightgreen")
                    else:
                        btn.config(text="OFF", bg="salmon")
                break

    def show_app_menu(self, event, device_id, label):
        """Affiche un menu pour l'app en cours"""
        app = label.cget("text")
        if app and app != "...":
            menu = tk.Menu(self.root, tearoff=0)
            menu.add_command(label=f"Fermer {app}", command=lambda: self.close_current_app(device_id, app))
            menu.post(event.x_root, event.y_root)

    def close_current_app(self, device_id, app):
        """Ferme l'application en cours"""
        self.adb.close_app(device_id, app)
        self.log(f"App fermée: {app}")
        self.root.after(1000, self.update_devices_info)

    def volume_up(self, device_id):
        """Augmente le volume"""
        self.adb.set_volume_up(device_id)
        self.root.after(500, self.update_devices_info)

    def volume_down(self, device_id):
        """Diminue le volume"""
        self.adb.set_volume_down(device_id)
        self.root.after(500, self.update_devices_info)

    def start_casting(self, device_id, nickname, model):
        """Démarre le casting pour un appareil"""
        presets = self.config.get("scrcpy_presets", {})

        params = presets.get("default", ["--no-audio"])
        for key in presets:
            if key.lower() in model.lower():
                params = presets[key]
                break

        success, message = self.scrcpy.start_casting(device_id, nickname, params)
        if success:
            self.log(f"Casting demandé: {nickname}")
        else:
            self.log(f"Erreur casting {nickname}: {message}")
            messagebox.showerror("Erreur", f"Impossible de démarrer le casting:\n{message}")

    def run(self):
        """Lance l'application"""
        self.root.mainloop()


# =============================================================================
# POINT D'ENTRÉE
# =============================================================================

if __name__ == "__main__":
    # Afficher d'abord le dialogue de démarrage
    choice = show_startup_dialog()

    if choice:
        # Lancer l'application principale
        app = VRCastingManager(choice)
        app.run()
