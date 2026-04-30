import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import subprocess
import os
import csv
import time
import re
from datetime import datetime
import threading
from pathlib import Path


# =============================================================================
# GESTIONNAIRE ADB (copié de VR-Casting-Manager)
# =============================================================================

class ADBManager:
    """Gestion des commandes ADB"""

    def __init__(self, adb_path=None):
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

    def get_device_mac(self, device_id):
        """Récupère l'adresse MAC de l'appareil"""
        stdout, _, rc = self.run_command(["shell", "dumpsys wifi | grep mWifiInfo | head -1"], device_id)
        if rc == 0:
            match = re.search(r'MAC: ([0-9a-fA-F:]+)', stdout)
            if match:
                return match.group(1).lower()
        return None

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

    def disable_proximity_sensor(self, device_id):
        """Désactive le capteur de proximité"""
        stdout, stderr, rc = self.run_command(
            ["shell", "am", "broadcast", "-a", "com.oculus.vrpowermanager.prox_close"],
            device_id
        )
        return rc == 0


# =============================================================================
# DIALOGUE DE CONFIGURATION D'APPAREIL (copié de VR-Casting-Manager)
# =============================================================================

class DeviceSetupDialog:
    """Dialogue de configuration d'un nouvel appareil (copié de VR-Casting-Manager)"""

    def __init__(self, parent, device_info, adb_manager, log_callback=None):
        self.result = None
        self.device_info = device_info
        self.adb = adb_manager
        self.log = log_callback if log_callback else print

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


class USBVRManager:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("USB-VR-Manager by Carl")
        self.root.geometry("900x700")

        # Répertoire du script (pour chemins relatifs)
        self.script_dir = os.path.dirname(os.path.abspath(__file__))

        # Configuration
        self.adb_path = self.find_adb_path()
        self.adb_manager = ADBManager(self.adb_path)
        self.scrcpy_path = self.find_scrcpy_path()
        self.devices_file = os.path.join(self.script_dir, "devices.csv")
        self.config_file = os.path.join(self.script_dir, "config.csv")
        self.devices = {}
        self.sync_paths = {
            "videos": "/sdcard/Movies/",
            "photos": "/sdcard/Pictures/",
            "others": "",
            "last_pc_folder": ""
        }
        
        # Variables pour les cases à cocher sync (utilisées dans pop-ups)
        self.apply_to_all_devices = False
        self.apply_to_all_files = False

        # État des accordéons (groupes repliés/dépliés) dans Install APK
        self.group_collapsed = {}  # {"Quest 3": False, "Pico 4": True}

        # USB detection state
        self.usb_detection_active = False
        self.usb_detection_thread = None

        self.load_devices()
        self.load_config()
        self.create_interface()
        
    def find_adb_path(self):
        """Trouve le chemin vers adb.exe"""
        # Chercher d'abord dans le dossier scrcpy local (relatif au script)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        local_adb = os.path.join(script_dir, "scrcpy-win64-v3.3.1-quest3-fix", "adb.exe")
        if os.path.exists(local_adb):
            return local_adb

        # Sinon, chercher dans SideQuest
        username = os.environ.get('USERNAME', 'User')
        sidequest_path = f"C:\\Users\\{username}\\AppData\\Local\\Programs\\SideQuest\\resources\\app.asar.unpacked\\build\\platform-tools\\adb.exe"
        if os.path.exists(sidequest_path):
            return sidequest_path

        # Si pas trouvé, demander à l'utilisateur
        messagebox.showwarning("ADB not found", "adb not found, select path to adb.exe")
        adb_path = filedialog.askopenfilename(
            title="Select adb.exe",
            filetypes=[("Executable files", "*.exe"), ("All files", "*.*")]
        )

        if not adb_path:
            messagebox.showerror("Error", "ADB path is required. Exiting.")
            exit()

        return adb_path

    def find_scrcpy_path(self):
        """Trouve le chemin vers scrcpy.exe"""
        # Chercher dans le dossier du script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        scrcpy_dir = os.path.join(script_dir, "scrcpy-win64-v3.3.1-quest3-fix")
        scrcpy_path = os.path.join(scrcpy_dir, "scrcpy.exe")

        if os.path.exists(scrcpy_path):
            return scrcpy_path

        # Si pas trouvé, demander à l'utilisateur
        messagebox.showwarning("scrcpy not found", "scrcpy.exe not found, select path to scrcpy.exe")
        scrcpy_path = filedialog.askopenfilename(
            title="Select scrcpy.exe",
            filetypes=[("Executable files", "*.exe"), ("All files", "*.*")]
        )

        if not scrcpy_path:
            return None  # Optionnel, le casting ne fonctionnera pas

        return scrcpy_path

    def load_devices(self):
        """Charge la liste des devices depuis le CSV"""
        if os.path.exists(self.devices_file):
            with open(self.devices_file, 'r', newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                for row in reader:
                    if len(row) >= 3:
                        device_id, nickname, last_seen = row[0], row[1], row[2]
                        ip_address = row[3] if len(row) >= 4 else ""
                        group = row[4] if len(row) >= 5 else "Non assigné"
                        mac_address = row[5] if len(row) >= 6 else ""
                        self.devices[device_id] = {
                            "nickname": nickname,
                            "last_seen": last_seen,
                            "ip_address": ip_address,
                            "group": group,
                            "mac_address": mac_address
                        }

    def save_devices(self):
        """Sauvegarde la liste des devices dans le CSV"""
        with open(self.devices_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            for device_id, info in self.devices.items():
                writer.writerow([
                    device_id,
                    info["nickname"],
                    info["last_seen"],
                    info.get("ip_address", ""),
                    info.get("group", "Non assigné"),
                    info.get("mac_address", "")
                ])
    
    def load_config(self):
        """Charge la configuration depuis le CSV"""
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r', newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                for row in reader:
                    if len(row) >= 2:
                        key, value = row[0], row[1]
                        if key in self.sync_paths:
                            self.sync_paths[key] = value
    
    def save_config(self):
        """Sauvegarde la configuration dans le CSV"""
        with open(self.config_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            for key, value in self.sync_paths.items():
                writer.writerow([key, value])
    
    def run_adb_command(self, command, device_id=None, retry_wireless=True, timeout=60):
        """Exécute une commande ADB avec reconnexion auto pour wireless"""
        try:
            if device_id:
                cmd = [self.adb_path, "-s", device_id] + command
            else:
                cmd = [self.adb_path] + command

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

            # Si échec et device wireless, tenter reconnexion
            if result.returncode != 0 and retry_wireless and device_id and ":" in device_id:
                ip = device_id.split(":")[0]
                # Tenter reconnexion
                reconnect_cmd = [self.adb_path, "connect", f"{ip}:5555"]
                subprocess.run(reconnect_cmd, capture_output=True, text=True, timeout=10)
                # Réessayer la commande (sans retry pour éviter boucle infinie)
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

            return result.stdout, result.stderr, result.returncode
        except subprocess.TimeoutExpired:
            return "", "Command timeout", 1
        except Exception as e:
            return "", str(e), 1

    def get_device_ip(self, device_id):
        """Récupère l'IP WiFi d'un device USB connecté"""
        stdout, stderr, rc = self.run_adb_command(
            ["shell", "ip", "addr", "show", "wlan0"], device_id, retry_wireless=False)
        if rc == 0:
            # Parse "inet 192.168.x.x/24"
            match = re.search(r'inet (\d+\.\d+\.\d+\.\d+)', stdout)
            if match:
                return match.group(1)
        return None

    def get_device_mac(self, device_id):
        """Récupère l'adresse MAC WiFi de l'appareil"""
        stdout, stderr, rc = self.run_adb_command(
            ["shell", "dumpsys wifi | grep mWifiInfo | head -1"], device_id, retry_wireless=False)
        if rc == 0:
            match = re.search(r'MAC: ([0-9a-fA-F:]+)', stdout)
            if match:
                return match.group(1).lower()
        return None

    def find_device_by_mac(self, mac):
        """Trouve un device enregistré par son adresse MAC"""
        if not mac:
            return None, None
        mac_lower = mac.lower()
        for device_id, info in self.devices.items():
            if info.get("mac_address", "").lower() == mac_lower:
                return device_id, info
        return None, None

    def setup_wireless(self, device_id):
        """Active le mode wireless sur un device USB et connecte automatiquement"""
        nickname = self.devices.get(device_id, {}).get("nickname", device_id)

        # 1. Récupérer l'IP
        ip = self.get_device_ip(device_id)
        if not ip:
            self.log_message(f"✗ Impossible de récupérer l'IP WiFi de {nickname}")
            return False

        self.log_message(f"IP détectée pour {nickname}: {ip}")

        # 2. Activer tcpip 5555
        stdout, stderr, rc = self.run_adb_command(["tcpip", "5555"], device_id, retry_wireless=False)
        if rc != 0:
            self.log_message(f"✗ Échec activation tcpip pour {nickname}: {stderr}")
            return False

        self.log_message(f"Mode TCP/IP activé sur {nickname}, connexion en cours...")
        time.sleep(2)  # Attendre que le device redémarre adb en mode TCP

        # 3. Connecter en wireless
        stdout, stderr, rc = self.run_adb_command(["connect", f"{ip}:5555"], retry_wireless=False)

        if "connected" in stdout.lower() or "already connected" in stdout.lower():
            self.log_message(f"✓ Wireless activé: {nickname} → {ip}:5555")
            # Sauvegarder l'IP
            if device_id in self.devices:
                self.devices[device_id]["ip_address"] = ip
            else:
                self.devices[device_id] = {
                    "nickname": f"Device_{device_id[:8]}",
                    "last_seen": datetime.now().strftime('%Y-%m-%d'),
                    "ip_address": ip
                }
            self.save_devices()
            return True
        else:
            if "10060" in stderr or "timeout" in stderr.lower() or "n'a pas répondu" in stderr:
                self.log_message(f"✗ Échec connexion wireless pour {nickname}")
                self.log_message(f"   → Vérifiez que le PC et le casque sont sur le même réseau WiFi !")
            else:
                self.log_message(f"✗ Échec connexion wireless pour {nickname}: {stderr}")
            return False

    def try_reconnect_wireless(self, device_id, timeout=5):
        """Tente de reconnecter un device via son IP sauvegardée"""
        info = self.devices.get(device_id, {})
        ip = info.get("ip_address")

        if not ip:
            return False

        try:
            cmd = [self.adb_path, "connect", f"{ip}:5555"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            stdout = result.stdout.lower()
            if "connected" in stdout or "already connected" in stdout:
                return True
        except subprocess.TimeoutExpired:
            pass
        except Exception:
            pass
        return False

    def _try_reconnect_with_log(self, device_id, info):
        """Thread-safe reconnection avec logging"""
        nickname = info.get("nickname", device_id)
        ip = info.get("ip_address")

        if self.try_reconnect_wireless(device_id, timeout=5):
            self.log_message(f"✓ Reconnecté: {nickname} via {ip}:5555")
        else:
            self.log_message(f"✗ {nickname} non disponible ({ip})")

    def is_wireless_device(self, device_id):
        """Vérifie si un device_id est une adresse wireless (IP:port)"""
        return ":" in device_id and device_id.split(":")[0].replace(".", "").isdigit()

    def detect_device_model(self, device_id):
        """Détecte le modèle du casque via ADB"""
        stdout, _, rc = self.run_adb_command(
            ["shell", "getprop", "ro.product.model"], device_id, retry_wireless=False)
        if rc == 0 and stdout.strip():
            return stdout.strip()
        return "Unknown"

    def get_all_groups(self):
        """Retourne la liste unique des groupes"""
        groups = set()
        for info in self.devices.values():
            group = info.get("group", "Non assigné")
            if group:
                groups.add(group)
        return sorted(groups)

    def get_devices_by_group(self, group):
        """Retourne les device_ids d'un groupe"""
        if group == "All" or group == "Tous":
            return list(self.devices.keys())
        return [d for d, info in self.devices.items()
                if info.get("group") == group]

    def get_connected_devices_by_group(self, group):
        """Retourne les device_ids connectés d'un groupe"""
        stdout, _, rc = self.run_adb_command(["devices"], retry_wireless=False)
        connected = set()
        if rc == 0:
            for line in stdout.strip().split('\n')[1:]:
                if '\tdevice' in line:
                    device_id = line.split('\t')[0]
                    connected.add(device_id)

        # Si aucun device connecté, retourner liste vide
        if not connected:
            return []

        device_ids = self.get_devices_by_group(group)
        result = []
        matched_connected = set()  # Track which connected devices we've matched

        for device_id in device_ids:
            info = self.devices.get(device_id, {})
            ip = info.get("ip_address", "")
            wireless_id = f"{ip}:5555" if ip else None

            # Connecté en USB ou WiFi ?
            if device_id in connected:
                result.append(device_id)
                matched_connected.add(device_id)
            elif wireless_id and wireless_id in connected:
                result.append(wireless_id)
                matched_connected.add(wireless_id)

        # Ajouter les devices WiFi connectés qui ne sont pas dans self.devices
        # (utile si "Tous" est sélectionné ou si devices non enregistrés)
        if group == "All" or group == "Tous":
            for conn_id in connected:
                if conn_id not in matched_connected:
                    result.append(conn_id)

        return result

    def log_message(self, message):
        """Affiche un message dans la zone de logs"""
        log_line = f"[{datetime.now().strftime('%H:%M:%S')}] {message}"
        print(log_line, flush=True)  # Console output
        self.log_text.insert(tk.END, log_line + "\n")
        self.log_text.see(tk.END)
        self.root.update()
    
    def create_interface(self):
        """Crée l'interface utilisateur"""
        # Création du notebook (onglets)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=5)

        # Onglet 1: Scan for devices
        self.create_scan_tab(self.notebook)

        # Onglet 2: Install APK
        self.create_install_tab(self.notebook)

        # Onglet 3: Scan for missing APKs
        self.create_missing_apk_tab(self.notebook)

        # Onglet 4: Uninstall APK
        self.create_uninstall_tab(self.notebook)

        # Onglet 5: Sync folder
        self.create_sync_tab(self.notebook)

        # Onglet 6: Enable Disable App
        self.create_enable_disable_tab(self.notebook)

        # Onglet 7: Casting
        self.create_casting_tab(self.notebook)

        # Auto-refresh au changement d'onglet
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)
        
        # Zone de logs en bas
        log_frame = tk.Frame(self.root)
        log_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        tk.Label(log_frame, text="Logs:").pack(anchor="w")
        
        self.log_text = tk.Text(log_frame, height=8)
        log_scrollbar = tk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scrollbar.set)
        
        self.log_text.pack(side="left", fill="both", expand=True)
        log_scrollbar.pack(side="right", fill="y")
    
    def create_scan_tab(self, notebook):
        """Crée l'onglet Scan for devices"""
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="Scan for devices")

        # Control buttons frame
        control_frame = tk.Frame(frame)
        control_frame.pack(fill="x", padx=10, pady=10)

        # USB Detection toggle button
        self.usb_detect_btn = tk.Button(
            control_frame,
            text="Start USB Detection",
            command=self.toggle_usb_detection,
            width=18
        )
        self.usb_detect_btn.pack(side="left", padx=5)

        # Manual scan button
        tk.Button(control_frame, text="Manual Scan", command=self.scan_devices).pack(side="left", padx=5)

        # Reconnect All WiFi button
        tk.Button(control_frame, text="Reconnect All WiFi", command=self.reconnect_all_wifi).pack(side="left", padx=5)

        # Status label
        self.detection_status_label = tk.Label(frame, text="USB Detection: OFF", fg="gray", font=("Arial", 9))
        self.detection_status_label.pack(anchor="w", padx=10)

        # Liste des devices avec couleurs
        self.devices_listbox = tk.Listbox(frame, height=15)
        self.devices_listbox.pack(fill="both", expand=True, padx=10, pady=5)

        # Menu contextuel (clic droit)
        self.device_context_menu = tk.Menu(self.devices_listbox, tearoff=0)
        self.device_context_menu.add_command(label="Set nickname", command=self.set_nickname)
        self.device_context_menu.add_command(label="Set group", command=self.set_device_group)
        self.device_context_menu.add_separator()
        self.device_context_menu.add_command(label="Forget device (remove from list)", command=self.forget_device)
        self.device_context_menu.add_command(label="Reconnect WiFi", command=self.reconnect_selected_device)

        # Bind clic droit
        self.devices_listbox.bind("<Button-3>", self.show_device_context_menu)

        # Boutons pour renommer et assigner groupe
        btn_frame = tk.Frame(frame)
        btn_frame.pack(pady=5)
        tk.Button(btn_frame, text="Set nickname", command=self.set_nickname).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Set group", command=self.set_device_group).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Forget device", command=self.forget_device).pack(side="left", padx=5)

        self.refresh_devices_list()
    
    def create_install_tab(self, notebook):
        """Crée l'onglet Install APK"""
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="Install APK")
        
        # Sélection des APK
        apk_frame = tk.Frame(frame)
        apk_frame.pack(fill="x", padx=10, pady=5)
        
        tk.Label(apk_frame, text="Selected APKs:").pack(anchor="w")
        self.apk_listbox = tk.Listbox(apk_frame, height=5)
        self.apk_listbox.pack(fill="x", pady=5)
        
        apk_btn_frame = tk.Frame(apk_frame)
        apk_btn_frame.pack(fill="x")
        
        tk.Button(apk_btn_frame, text="Add APK files", command=self.add_apk_files).pack(side="left", padx=5)
        tk.Button(apk_btn_frame, text="Clear list", command=lambda: self.apk_listbox.delete(0, tk.END)).pack(side="left", padx=5)
        
        # Sélection des devices
        device_frame = tk.Frame(frame)
        device_frame.pack(fill="both", expand=True, padx=10, pady=5)

        tk.Label(device_frame, text="Target devices:").pack(anchor="w")

        # Sélection par groupe
        group_frame = tk.Frame(device_frame)
        group_frame.pack(fill="x", pady=5)
        tk.Label(group_frame, text="Filter by group:").pack(side="left")
        self.install_group_var = tk.StringVar(value="Tous")
        self.install_group_combo = ttk.Combobox(group_frame, textvariable=self.install_group_var, state="readonly", width=20)
        self.install_group_combo.pack(side="left", padx=5)
        tk.Button(group_frame, text="Select group", command=self.select_group_devices).pack(side="left", padx=5)

        device_btn_frame = tk.Frame(device_frame)
        device_btn_frame.pack(fill="x")

        tk.Button(device_btn_frame, text="Refresh devices", command=self.refresh_install_devices).pack(side="left", padx=5)
        tk.Button(device_btn_frame, text="Select all", command=self.select_all_devices).pack(side="left", padx=5)
        tk.Button(device_btn_frame, text="Deselect all", command=self.deselect_all_devices).pack(side="left", padx=5)

        # Frame scrollable pour les checkboxes des devices (supporte 40-50+ devices)
        scroll_container = tk.Frame(device_frame)
        scroll_container.pack(fill="both", expand=True, pady=5)

        self.install_canvas = tk.Canvas(scroll_container, highlightthickness=0)
        scrollbar = tk.Scrollbar(scroll_container, orient="vertical", command=self.install_canvas.yview)
        self.install_canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        self.install_canvas.pack(side="left", fill="both", expand=True)

        self.install_devices_frame = tk.Frame(self.install_canvas)
        self.install_canvas_window = self.install_canvas.create_window((0, 0), window=self.install_devices_frame, anchor="nw")

        # Configurer le scroll
        def on_frame_configure(event):
            self.install_canvas.configure(scrollregion=self.install_canvas.bbox("all"))

        def on_canvas_configure(event):
            self.install_canvas.itemconfig(self.install_canvas_window, width=event.width)

        self.install_devices_frame.bind("<Configure>", on_frame_configure)
        self.install_canvas.bind("<Configure>", on_canvas_configure)

        # Support molette souris
        def on_mousewheel(event):
            self.install_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        self.install_canvas.bind_all("<MouseWheel>", on_mousewheel)
        
        # Message d'avertissement
        warning_label = tk.Label(frame, text="The APKs will be installed on selected devices, one after the other.\nDo NOT disconnect headsets during installation.", 
                               fg="red", font=("Arial", 10, "bold"))
        warning_label.pack(pady=10)
        
        # Bouton d'installation
        install_btn = tk.Button(frame, text="Install APKs", command=self.install_apks, bg="lightgreen")
        install_btn.pack(pady=10)
        
        self.device_checkboxes = {}
    
    def create_missing_apk_tab(self, notebook):
        """Crée l'onglet Scan for missing APKs"""
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="Scan for missing APKs")

        # Sélection du groupe
        group_frame = tk.Frame(frame)
        group_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(group_frame, text="Filter by group:").pack(side="left")
        self.missing_group_var = tk.StringVar(value="Tous")
        self.missing_group_combo = ttk.Combobox(group_frame, textvariable=self.missing_group_var, state="readonly", width=20)
        self.missing_group_combo.pack(side="left", padx=5)

        # Contrôles
        control_frame = tk.Frame(frame)
        control_frame.pack(fill="x", padx=10, pady=5)

        scan_missing_btn = tk.Button(control_frame, text="Scan devices for installed packages", command=self.scan_missing_apks)
        scan_missing_btn.pack(side="left", padx=5)

        self.show_missing_only = tk.BooleanVar()
        missing_checkbox = tk.Checkbutton(control_frame, text="Show missing packages only",
                                        variable=self.show_missing_only, command=self.filter_missing_packages)
        missing_checkbox.pack(side="left", padx=20)
        
        # Tableau avec scrollbars
        table_frame = tk.Frame(frame)
        table_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.missing_tree = ttk.Treeview(table_frame)
        
        # Scrollbars
        v_scrollbar = tk.Scrollbar(table_frame, orient="vertical", command=self.missing_tree.yview)
        h_scrollbar = tk.Scrollbar(table_frame, orient="horizontal", command=self.missing_tree.xview)
        self.missing_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Grid layout pour les scrollbars
        self.missing_tree.grid(row=0, column=0, sticky="nsew")
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        h_scrollbar.grid(row=1, column=0, sticky="ew")
        
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)
        
        # Stocker les données pour le filtrage
        self.all_packages_data = []
    
    def create_uninstall_tab(self, notebook):
        """Crée l'onglet Uninstall APK"""
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="Uninstall APK")

        # Sélection par groupe
        group_frame = tk.Frame(frame)
        group_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(group_frame, text="Filter by group:").pack(side="left")
        self.uninstall_group_var = tk.StringVar(value="Tous")
        self.uninstall_group_combo = ttk.Combobox(group_frame, textvariable=self.uninstall_group_var, state="readonly", width=20)
        self.uninstall_group_combo.pack(side="left", padx=5)
        self.uninstall_group_combo.bind("<<ComboboxSelected>>", lambda e: self.refresh_uninstall_devices())

        # Sélection du device
        device_frame = tk.Frame(frame)
        device_frame.pack(fill="x", padx=10, pady=5)

        tk.Label(device_frame, text="Select device:").pack(anchor="w")
        self.uninstall_device_var = tk.StringVar()
        self.uninstall_device_combo = ttk.Combobox(device_frame, textvariable=self.uninstall_device_var, state="readonly")
        self.uninstall_device_combo.pack(fill="x", pady=5)
        # Auto-load packages quand on sélectionne un device
        self.uninstall_device_combo.bind("<<ComboboxSelected>>", lambda e: self.load_device_packages())

        controls_frame = tk.Frame(device_frame)
        controls_frame.pack(fill="x", pady=5)

        tk.Button(controls_frame, text="Refresh devices", command=self.refresh_uninstall_devices).pack(side="left", padx=5)
        
        # Case à cocher pour afficher les apps système
        self.show_system_apps = tk.BooleanVar()
        system_checkbox = tk.Checkbutton(controls_frame, text="Show system apps", 
                                       variable=self.show_system_apps, command=self.filter_packages)
        system_checkbox.pack(side="left", padx=20)
        
        # Liste des packages
        package_frame = tk.Frame(frame)
        package_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        tk.Label(package_frame, text="Installed packages:").pack(anchor="w")
        self.packages_listbox = tk.Listbox(package_frame, height=10)
        package_scrollbar = tk.Scrollbar(package_frame, orient="vertical", command=self.packages_listbox.yview)
        self.packages_listbox.configure(yscrollcommand=package_scrollbar.set)
        
        self.packages_listbox.pack(side="left", fill="both", expand=True)
        package_scrollbar.pack(side="right", fill="y")
        
        # Boutons d'action
        uninstall_frame = tk.Frame(frame)
        uninstall_frame.pack(fill="x", padx=10, pady=5)

        tk.Button(uninstall_frame, text="Uninstall from selected device", command=self.uninstall_from_device).pack(side="left", padx=5)
        tk.Button(uninstall_frame, text="Uninstall from group", command=self.uninstall_from_group, bg="orange").pack(side="left", padx=5)
        tk.Button(uninstall_frame, text="Uninstall from ALL devices", command=self.uninstall_from_all_devices).pack(side="left", padx=5)
        
        # Stocker tous les packages pour le filtrage
        self.all_packages = []
        self.system_packages = set()
    
    def create_sync_tab(self, notebook):
        """Crée l'onglet Sync folder"""
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="Sync folder")

        # Sélection du groupe
        group_frame = tk.Frame(frame)
        group_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(group_frame, text="Configure paths for group:").pack(side="left")
        self.sync_group_var = tk.StringVar(value="Default")
        self.sync_group_combo = ttk.Combobox(group_frame, textvariable=self.sync_group_var, state="readonly", width=20)
        self.sync_group_combo.pack(side="left", padx=5)
        self.sync_group_combo.bind("<<ComboboxSelected>>", self.on_sync_group_change)
        tk.Button(group_frame, text="Refresh groups", command=self.refresh_sync_groups).pack(side="left", padx=5)

        # Configuration des chemins
        config_frame = tk.LabelFrame(frame, text="Sync paths configuration")
        config_frame.pack(fill="x", padx=10, pady=5)

        # Videos path
        tk.Label(config_frame, text="Videos path:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.videos_path_var = tk.StringVar(value=self.sync_paths["videos"])
        tk.Entry(config_frame, textvariable=self.videos_path_var, width=50).grid(row=0, column=1, padx=5, pady=2)

        # Photos path
        tk.Label(config_frame, text="Photos path:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        self.photos_path_var = tk.StringVar(value=self.sync_paths["photos"])
        tk.Entry(config_frame, textvariable=self.photos_path_var, width=50).grid(row=1, column=1, padx=5, pady=2)

        self.sync_path_info_label = tk.Label(config_frame, text="(Default paths for all groups)", fg="gray")
        self.sync_path_info_label.grid(row=2, column=0, columnspan=2, sticky="w", padx=5)

        tk.Button(config_frame, text="Save paths for this group", command=self.save_sync_paths).grid(row=3, column=1, sticky="e", padx=5, pady=5)

        # Sync operations
        sync_frame = tk.LabelFrame(frame, text="Sync operations")
        sync_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # Target group selection for sync
        target_frame = tk.Frame(sync_frame)
        target_frame.pack(fill="x", padx=5, pady=5)
        tk.Label(target_frame, text="Sync to group:").pack(side="left")
        self.sync_target_group_var = tk.StringVar(value="Tous")
        self.sync_target_group_combo = ttk.Combobox(target_frame, textvariable=self.sync_target_group_var, state="readonly", width=20)
        self.sync_target_group_combo.pack(side="left", padx=5)

        # PC folder
        pc_frame = tk.Frame(sync_frame)
        pc_frame.pack(fill="x", padx=5, pady=5)

        tk.Label(pc_frame, text="PC folder:").pack(anchor="w")
        pc_folder_frame = tk.Frame(pc_frame)
        pc_folder_frame.pack(fill="x", pady=2)

        self.pc_folder_var = tk.StringVar(value=self.sync_paths.get("last_pc_folder", ""))
        tk.Entry(pc_folder_frame, textvariable=self.pc_folder_var).pack(side="left", fill="x", expand=True)
        tk.Button(pc_folder_frame, text="Browse", command=self.browse_pc_folder).pack(side="right", padx=5)

        # Headset folder
        headset_frame = tk.Frame(sync_frame)
        headset_frame.pack(fill="x", padx=5, pady=5)

        tk.Label(headset_frame, text="Headset folder:").pack(anchor="w")

        # Dropdown pour les options
        dropdown_frame = tk.Frame(headset_frame)
        dropdown_frame.pack(fill="x", pady=2)

        self.headset_folder_type = tk.StringVar(value="Custom")
        headset_combo = ttk.Combobox(dropdown_frame, textvariable=self.headset_folder_type,
                                   values=["Videos (group path)", "Photos (group path)", "Custom"], state="readonly")
        headset_combo.pack(side="left", padx=(0, 5))
        headset_combo.bind("<<ComboboxSelected>>", self.on_headset_folder_type_change)

        tk.Button(dropdown_frame, text="Browse Headset", command=self.browse_headset_folder).pack(side="right")

        # Champ de destination
        self.headset_folder_var = tk.StringVar()
        tk.Entry(headset_frame, textvariable=self.headset_folder_var).pack(fill="x", pady=2)

        # Bouton de synchronisation
        tk.Button(sync_frame, text="Start sync to selected group", command=self.start_sync, bg="lightgreen").pack(pady=10)

        # Initialiser les groupes
        self.refresh_sync_groups()
        
    def create_enable_disable_tab(self, notebook):
        """Crée l'onglet Enable/Disable App"""
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="Enable / Disable App")

        # Variables pour les checkboxes des devices
        self.ed_device_checkboxes = {}
        self.ed_device_groups = {}

        # --- Sélection par groupe ---
        group_frame = tk.Frame(frame)
        group_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(group_frame, text="Filter by group:").pack(side="left")
        self.ed_group_var = tk.StringVar(value="Tous")
        self.ed_group_combo = ttk.Combobox(group_frame, textvariable=self.ed_group_var, state="readonly", width=20)
        self.ed_group_combo.pack(side="left", padx=5)
        tk.Button(group_frame, text="Select group", command=self.select_ed_group_devices).pack(side="left", padx=5)

        # --- Boutons de contrôle devices ---
        device_btn_frame = tk.Frame(frame)
        device_btn_frame.pack(fill="x", padx=10, pady=5)
        tk.Button(device_btn_frame, text="Refresh devices", command=self.refresh_ed_devices).pack(side="left", padx=5)
        tk.Button(device_btn_frame, text="Select all", command=self.select_all_ed_devices).pack(side="left", padx=5)
        tk.Button(device_btn_frame, text="Deselect all", command=self.deselect_all_ed_devices).pack(side="left", padx=5)

        # --- Frame scrollable pour les checkboxes des devices ---
        device_scroll_container = tk.Frame(frame)
        device_scroll_container.pack(fill="x", padx=10, pady=5)

        self.ed_canvas = tk.Canvas(device_scroll_container, height=100, highlightthickness=0)
        ed_scrollbar = tk.Scrollbar(device_scroll_container, orient="vertical", command=self.ed_canvas.yview)
        self.ed_canvas.configure(yscrollcommand=ed_scrollbar.set)

        ed_scrollbar.pack(side="right", fill="y")
        self.ed_canvas.pack(side="left", fill="both", expand=True)

        self.ed_devices_frame = tk.Frame(self.ed_canvas)
        self.ed_canvas_window = self.ed_canvas.create_window((0, 0), window=self.ed_devices_frame, anchor="nw")

        def on_ed_frame_configure(event):
            self.ed_canvas.configure(scrollregion=self.ed_canvas.bbox("all"))

        def on_ed_canvas_configure(event):
            self.ed_canvas.itemconfig(self.ed_canvas_window, width=event.width)

        self.ed_devices_frame.bind("<Configure>", on_ed_frame_configure)
        self.ed_canvas.bind("<Configure>", on_ed_canvas_configure)

        # --- Option pour tous les utilisateurs ---
        self.ed_all_users_var = tk.BooleanVar(value=True)
        tk.Checkbutton(frame, text="Apply to all users on device",
                      variable=self.ed_all_users_var).pack(anchor="w", padx=10)

        # --- Liste des apps ---
        list_frame = tk.Frame(frame)
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)

        tk.Label(list_frame, text="Installed packages (red = disabled on first selected device):").pack(anchor="w")
        self.ed_listbox = tk.Listbox(list_frame, height=10, selectmode=tk.EXTENDED)
        scrollbar = tk.Scrollbar(list_frame, orient="vertical", command=self.ed_listbox.yview)
        self.ed_listbox.configure(yscrollcommand=scrollbar.set)
        self.ed_listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # --- Boutons d'action ---
        btn_frame = tk.Frame(frame)
        btn_frame.pack(fill="x", pady=10)
        tk.Button(btn_frame, text="Load packages", command=self.load_ed_packages).pack(side="left", padx=10)
        tk.Button(btn_frame, text="Disable selected apps", bg="orange", command=self.disable_selected_apps).pack(side="left", padx=10)
        tk.Button(btn_frame, text="Enable selected apps", bg="lightgreen", command=self.enable_selected_apps).pack(side="left", padx=10)

    def create_casting_tab(self, notebook):
        """Crée l'onglet Casting"""
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="Casting")

        # Variables pour les checkboxes des devices
        self.casting_checkboxes = {}
        self.casting_device_groups = {}
        self.casting_group_collapsed = {}

        # Sélection par groupe
        group_frame = tk.Frame(frame)
        group_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(group_frame, text="Filter by group:").pack(side="left")
        self.casting_group_var = tk.StringVar(value="Tous")
        self.casting_group_combo = ttk.Combobox(group_frame, textvariable=self.casting_group_var, state="readonly", width=20)
        self.casting_group_combo.pack(side="left", padx=5)
        tk.Button(group_frame, text="Select group", command=self.select_casting_group_devices).pack(side="left", padx=5)

        # Boutons de contrôle
        device_btn_frame = tk.Frame(frame)
        device_btn_frame.pack(fill="x", padx=10, pady=5)
        tk.Button(device_btn_frame, text="Refresh devices", command=self.refresh_casting_devices).pack(side="left", padx=5)
        tk.Button(device_btn_frame, text="Select all", command=self.select_all_casting_devices).pack(side="left", padx=5)
        tk.Button(device_btn_frame, text="Deselect all", command=self.deselect_all_casting_devices).pack(side="left", padx=5)

        # Frame scrollable pour les checkboxes des devices
        scroll_container = tk.Frame(frame)
        scroll_container.pack(fill="both", expand=True, padx=10, pady=5)

        self.casting_canvas = tk.Canvas(scroll_container, highlightthickness=0)
        scrollbar = tk.Scrollbar(scroll_container, orient="vertical", command=self.casting_canvas.yview)
        self.casting_canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        self.casting_canvas.pack(side="left", fill="both", expand=True)

        self.casting_devices_frame = tk.Frame(self.casting_canvas)
        self.casting_canvas_window = self.casting_canvas.create_window((0, 0), window=self.casting_devices_frame, anchor="nw")

        # Configurer le scroll
        def on_frame_configure(event):
            self.casting_canvas.configure(scrollregion=self.casting_canvas.bbox("all"))

        def on_canvas_configure(event):
            self.casting_canvas.itemconfig(self.casting_canvas_window, width=event.width)

        self.casting_devices_frame.bind("<Configure>", on_frame_configure)
        self.casting_canvas.bind("<Configure>", on_canvas_configure)

        # Support molette souris
        def on_mousewheel(event):
            self.casting_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        self.casting_canvas.bind("<MouseWheel>", on_mousewheel)

        # Info sur les presets
        info_label = tk.Label(frame, text="Preset auto: Quest 3 (angle+crop), Quest 2 (crop), Autres (no crop)",
                             fg="gray", font=("Arial", 9))
        info_label.pack(pady=5)

        # Bouton Start Casting
        cast_btn = tk.Button(frame, text="Start Casting", command=self.start_casting, bg="lightgreen",
                            font=("Arial", 11, "bold"))
        cast_btn.pack(pady=10)

    def scan_devices(self):
        """Scanne les devices connectés avec support wireless automatique"""
        self.log_message("Scanning for connected devices...")

        # 1. Obtenir la liste des devices déjà connectés UNE SEULE FOIS
        stdout, _, _ = self.run_adb_command(["devices"], retry_wireless=False)
        already_connected = set()
        if stdout:
            for line in stdout.strip().split('\n')[1:]:
                if '\tdevice' in line or '\tunauthorized' in line:
                    already_connected.add(line.split('\t')[0])

        # Log already connected devices
        if already_connected:
            self.log_message(f"Already connected: {len(already_connected)} device(s)")
            for dev_id in already_connected:
                self.log_message(f"  - {dev_id}")

        # 2. Tenter de reconnecter les devices wireless connus EN PARALLELE
        devices_to_reconnect = []
        devices_skipped_no_ip = []
        devices_skipped_connected = []

        for device_id, info in list(self.devices.items()):
            if info.get("ip_address"):
                wireless_id = f"{info['ip_address']}:5555"
                if wireless_id not in already_connected:
                    devices_to_reconnect.append((device_id, info))
                else:
                    devices_skipped_connected.append((info.get("nickname", device_id), wireless_id))
            else:
                devices_skipped_no_ip.append(info.get("nickname", device_id))

        # Log skipped devices
        if devices_skipped_connected:
            self.log_message(f"Skipped (already connected): {len(devices_skipped_connected)}")
            for name, ip in devices_skipped_connected:
                self.log_message(f"  - {name} ({ip})")
        if devices_skipped_no_ip:
            self.log_message(f"Skipped (no IP saved): {len(devices_skipped_no_ip)}")
            for name in devices_skipped_no_ip:
                self.log_message(f"  - {name}")

        if devices_to_reconnect:
            self.log_message(f"Tentative reconnexion de {len(devices_to_reconnect)} device(s) en parallèle...")
            threads = []
            for device_id, info in devices_to_reconnect:
                t = threading.Thread(target=self._try_reconnect_with_log, args=(device_id, info))
                t.daemon = True
                threads.append(t)
                t.start()

            # Attendre toutes les reconnexions (max 5 secondes chacune)
            for t in threads:
                t.join(timeout=6)

        # 2. Scanner tous les devices (USB + WiFi)
        stdout, stderr, returncode = self.run_adb_command(["devices"], retry_wireless=False)

        if returncode != 0:
            self.log_message(f"Error scanning devices: {stderr}")
            return

        lines = stdout.strip().split('\n')[1:]  # Skip header
        current_devices = {}

        for line in lines:
            if '\tdevice' in line or '\tunauthorized' in line or '\toffline' in line:
                parts = line.split('\t')
                if len(parts) >= 2:
                    device_id = parts[0]
                    status = parts[1]
                    current_devices[device_id] = status

        # 3. Pour chaque device USB autorisé sans IP, activer wireless auto
        for device_id, status in current_devices.items():
            if status == "device" and not self.is_wireless_device(device_id):
                # C'est un device USB
                is_new_device = device_id not in self.devices
                if is_new_device:
                    # Détecter le modèle automatiquement
                    detected_model = self.detect_device_model(device_id)
                    self.log_message(f"Modèle détecté: {detected_model}")

                    self.devices[device_id] = {
                        "nickname": f"Device_{device_id[:8]}",
                        "last_seen": datetime.now().strftime('%Y-%m-%d'),
                        "ip_address": "",
                        "group": detected_model
                    }
                else:
                    self.devices[device_id]["last_seen"] = datetime.now().strftime('%Y-%m-%d')
                    # Si pas de groupe assigné, détecter le modèle
                    if not self.devices[device_id].get("group") or self.devices[device_id].get("group") == "Non assigné":
                        detected_model = self.detect_device_model(device_id)
                        self.devices[device_id]["group"] = detected_model
                        self.log_message(f"Modèle détecté pour {self.devices[device_id]['nickname']}: {detected_model}")

                # Si pas d'IP sauvegardée, activer wireless automatiquement
                if not self.devices[device_id].get("ip_address"):
                    self.log_message(f"Nouveau device USB détecté: {self.devices[device_id]['nickname']}")
                    self.log_message("Activation wireless automatique...")
                    self.setup_wireless(device_id)

        self.save_devices()
        self.refresh_devices_list()

        # Compter les devices connectés
        usb_count = sum(1 for d in current_devices if not self.is_wireless_device(d))
        wifi_count = sum(1 for d in current_devices if self.is_wireless_device(d))
        self.log_message(f"Found {len(current_devices)} device(s): {usb_count} USB, {wifi_count} WiFi")

    def toggle_usb_detection(self):
        """Active/désactive la détection USB automatique"""
        if self.usb_detection_active:
            self.usb_detection_active = False
            self.usb_detect_btn.config(relief="raised", bg="SystemButtonFace", text="Start USB Detection")
            self.detection_status_label.config(text="USB Detection: OFF", fg="gray")
            self.log_message("USB detection stopped")
        else:
            self.usb_detection_active = True
            self.usb_detect_btn.config(relief="sunken", bg="lightgreen", text="Stop USB Detection")
            self.detection_status_label.config(text="USB Detection: ON - Waiting for device...", fg="green")
            self.log_message("USB detection started - Connect a headset via USB...")
            self.usb_detection_thread = threading.Thread(target=self.usb_detection_loop, daemon=True)
            self.usb_detection_thread.start()

    def usb_detection_loop(self):
        """Boucle de détection des appareils USB avec logique 'wait for disconnect'"""
        known_macs = set()
        current_usb_mac = None  # Track the currently connected USB device's MAC

        # Récupérer les MAC des appareils déjà connus
        for device_id, info in self.devices.items():
            mac = info.get("mac_address", "")
            if mac:
                known_macs.add(mac.lower())

        self.root.after(0, lambda: self.log_message(f"USB Detection: {len(known_macs)} known device(s) by MAC"))

        while self.usb_detection_active:
            try:
                # Get USB devices only (not WiFi connections)
                stdout, stderr, rc = self.run_adb_command(["devices"], retry_wireless=False)
                usb_devices = []

                if rc == 0:
                    for line in stdout.strip().split('\n')[1:]:
                        if '\tdevice' in line:
                            device_id = line.split('\t')[0]
                            # Only USB devices (no ':' in ID)
                            if ':' not in device_id:
                                usb_devices.append(device_id)

                if usb_devices:
                    # Only process ONE USB device (the first one)
                    device_id = usb_devices[0]
                    mac = self.get_device_mac(device_id)

                    if mac:
                        mac_lower = mac.lower()

                        if current_usb_mac is None:
                            # First detection or after disconnect
                            current_usb_mac = mac_lower

                            if mac_lower in known_macs:
                                self.root.after(0, lambda m=mac: self.log_message(f"Known device reconnected (MAC: {m}), re-configuring..."))
                            else:
                                self.root.after(0, lambda m=mac: self.log_message(f"NEW device detected (MAC: {m})"))

                            # Configure the device
                            self.root.after(0, lambda d=device_id, m=mac: self.handle_new_usb_device(d, m))
                            known_macs.add(mac_lower)

                        elif current_usb_mac != mac_lower:
                            # Different device connected
                            self.root.after(0, lambda m=mac: self.log_message(f"Different device detected (MAC: {m})"))
                            current_usb_mac = mac_lower
                            self.root.after(0, lambda d=device_id, m=mac: self.handle_new_usb_device(d, m))
                            known_macs.add(mac_lower)
                        # If same device still connected (current_usb_mac == mac_lower) → wait

                else:
                    # No USB device connected - reset tracker
                    if current_usb_mac is not None:
                        self.root.after(0, lambda: self.log_message("USB device disconnected, ready for next device..."))
                        self.root.after(0, lambda: self.detection_status_label.config(
                            text="USB Detection: ON - Waiting for device...", fg="green"))
                        current_usb_mac = None

                time.sleep(3)  # Poll every 3 seconds

            except Exception as e:
                self.root.after(0, lambda err=str(e): self.log_message(f"Detection error: {err}"))
                time.sleep(5)

    def handle_new_usb_device(self, device_id, mac):
        """Gère un nouvel appareil USB détecté"""
        self.log_message(f"Configuring {device_id}...")
        self.detection_status_label.config(text=f"USB Detection: Configuring {device_id[:8]}...", fg="orange")

        # Récupérer le modèle
        model = self.detect_device_model(device_id)
        self.log_message(f"  Model: {model}")

        device_info = {
            'device_id': device_id,
            'mac': mac,
            'model': model
        }

        # Open setup dialog
        setup_dialog = DeviceSetupDialog(self.root, device_info, self.adb_manager, self.log_message)
        self.root.wait_window(setup_dialog.dialog)

        if setup_dialog.result:
            result = setup_dialog.result
            # Save device with new device_id (could be different from before if reconnected)
            self.devices[device_id] = {
                "nickname": result.get('nickname', f"Device_{device_id[:8]}"),
                "last_seen": datetime.now().strftime('%Y-%m-%d'),
                "ip_address": result.get('ip', ''),
                "group": model,
                "mac_address": mac
            }
            self.save_devices()
            self.log_message(f"Device configured: {result.get('nickname')} (IP: {result.get('ip')}:5555)")
            self.refresh_devices_list()
        else:
            self.log_message("Configuration cancelled or failed")

        self.detection_status_label.config(text="USB Detection: ON - Waiting for device...", fg="green")

    def reconnect_all_wifi(self):
        """Tente de reconnecter tous les devices WiFi connus"""
        self.log_message("Reconnecting all WiFi devices...")

        def do_reconnect():
            count_ok = 0
            count_fail = 0
            for device_id, info in self.devices.items():
                ip = info.get("ip_address")
                if ip:
                    nickname = info.get("nickname", device_id)
                    if self.try_reconnect_wireless(device_id, timeout=5):
                        self.root.after(0, lambda n=nickname: self.log_message(f"  OK: {n}"))
                        count_ok += 1
                    else:
                        self.root.after(0, lambda n=nickname: self.log_message(f"  FAILED: {n}"))
                        count_fail += 1

            self.root.after(0, lambda: self.log_message(f"Reconnection done: {count_ok} OK, {count_fail} failed"))
            self.root.after(0, self.refresh_devices_list)

        thread = threading.Thread(target=do_reconnect, daemon=True)
        thread.start()

    def refresh_devices_list(self):
        """Rafraîchit la liste des devices dans l'onglet scan"""
        self.devices_listbox.delete(0, tk.END)

        # Vérifier quels devices sont actuellement connectés
        stdout, stderr, returncode = self.run_adb_command(["devices"], retry_wireless=False)
        current_devices = {}

        if returncode == 0:
            lines = stdout.strip().split('\n')[1:]
            for line in lines:
                if '\tdevice' in line or '\tunauthorized' in line or '\toffline' in line:
                    parts = line.split('\t')
                    if len(parts) >= 2:
                        device_id = parts[0]
                        status = parts[1].upper()
                        current_devices[device_id] = status

        # Track which connected devices we've displayed
        displayed_connected = set()

        # Créer une liste triée par nickname (devices enregistrés)
        sorted_devices = sorted(self.devices.items(), key=lambda x: x[1]["nickname"].lower())

        # Collecter les device_ids déjà couverts par self.devices (USB serial + wireless IDs)
        known_ids = set()
        for device_id, info in self.devices.items():
            known_ids.add(device_id)
            ip_address = info.get("ip_address", "")
            if ip_address:
                known_ids.add(f"{ip_address}:5555")

        for device_id, info in sorted_devices:
            # Vérifier si connecté en USB ou WiFi
            ip_address = info.get("ip_address", "")
            wireless_id = f"{ip_address}:5555" if ip_address else None

            # Déterminer le statut et le type de connexion
            is_wifi_connected = wireless_id and wireless_id in current_devices
            is_usb_connected = device_id in current_devices

            if is_wifi_connected:
                status = current_devices.get(wireless_id, "OFFLINE")
                connection_type = "[WiFi]"
                display_id = wireless_id
                displayed_connected.add(wireless_id)
            elif is_usb_connected:
                status = current_devices.get(device_id, "OFFLINE")
                connection_type = "[USB]"
                display_id = device_id
                displayed_connected.add(device_id)
            else:
                status = "OFFLINE"
                connection_type = "[WiFi]" if ip_address else ""
                display_id = wireless_id if ip_address else device_id

            if status == "UNAUTHORIZED":
                status += " (Accept USB debugging on headset)"

            group = info.get("group", "Non assigné")
            display_text = f"{info['nickname']} ({display_id}) [{group}] {connection_type} - {status}"
            self.devices_listbox.insert(tk.END, display_text)

            # Définir les couleurs
            index = self.devices_listbox.size() - 1
            if status.startswith("OFFLINE"):
                self.devices_listbox.itemconfig(index, fg="red")
            elif status.startswith("UNAUTHORIZED"):
                self.devices_listbox.itemconfig(index, fg="orange")
            elif status == "DEVICE":
                self.devices_listbox.itemconfig(index, fg="green")

        # Afficher les devices WiFi connectés mais non enregistrés
        for device_id, status in current_devices.items():
            if device_id not in displayed_connected:
                # Device connecté mais pas dans self.devices
                is_wifi = self.is_wireless_device(device_id)
                connection_type = "[WiFi]" if is_wifi else "[USB]"

                if status == "UNAUTHORIZED":
                    status_display = "UNAUTHORIZED (Accept USB debugging on headset)"
                else:
                    status_display = status

                display_text = f"New device ({device_id}) [Non enregistré] {connection_type} - {status_display}"
                self.devices_listbox.insert(tk.END, display_text)

                # Définir les couleurs
                index = self.devices_listbox.size() - 1
                if status == "OFFLINE":
                    self.devices_listbox.itemconfig(index, fg="red")
                elif status == "UNAUTHORIZED":
                    self.devices_listbox.itemconfig(index, fg="orange")
                elif status == "DEVICE":
                    self.devices_listbox.itemconfig(index, fg="green")
    
    def find_device_by_display_id(self, display_id):
        """Trouve le device_id original à partir de l'ID affiché (peut être IP:port)"""
        # Si c'est directement dans devices, retourner tel quel
        if display_id in self.devices:
            return display_id

        # Sinon, chercher par IP wireless
        for device_id, info in self.devices.items():
            ip = info.get("ip_address", "")
            if ip and f"{ip}:5555" == display_id:
                return device_id

        return None

    def set_nickname(self):
        """Définit un nickname pour le device sélectionné"""
        selection = self.devices_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a device first")
            return

        # Extraire l'ID du device de la sélection
        item_text = self.devices_listbox.get(selection[0])
        display_id = item_text.split('(')[1].split(')')[0]

        # Trouver le vrai device_id (peut être différent si affiché avec IP)
        device_id = self.find_device_by_display_id(display_id)
        if not device_id:
            messagebox.showerror("Error", f"Device not found: {display_id}")
            return

        current_nickname = self.devices[device_id]["nickname"]
        new_nickname = simpledialog.askstring("Set nickname", f"Enter nickname for device {device_id}:", initialvalue=current_nickname)

        if new_nickname:
            self.devices[device_id]["nickname"] = new_nickname
            self.save_devices()
            self.refresh_devices_list()
            self.log_message(f"Device {device_id} renamed to '{new_nickname}'")

    def set_device_group(self):
        """Définit le groupe pour le device sélectionné"""
        selection = self.devices_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a device first")
            return

        # Extraire l'ID du device de la sélection
        item_text = self.devices_listbox.get(selection[0])
        display_id = item_text.split('(')[1].split(')')[0]

        # Trouver le vrai device_id
        device_id = self.find_device_by_display_id(display_id)
        if not device_id:
            messagebox.showerror("Error", f"Device not found: {display_id}")
            return

        # Créer un dialog pour choisir le groupe
        dialog = tk.Toplevel(self.root)
        dialog.title("Set Group")
        dialog.geometry("350x200")
        dialog.grab_set()

        current_group = self.devices[device_id].get("group", "Non assigné")
        nickname = self.devices[device_id]["nickname"]

        tk.Label(dialog, text=f"Set group for: {nickname}", font=("Arial", 10, "bold")).pack(pady=10)

        # Liste des groupes existants + option nouveau
        groups = self.get_all_groups()
        if "Non assigné" not in groups:
            groups.insert(0, "Non assigné")

        tk.Label(dialog, text="Select existing group:").pack(anchor="w", padx=20)
        group_var = tk.StringVar(value=current_group)
        group_combo = ttk.Combobox(dialog, textvariable=group_var, values=groups, state="readonly")
        group_combo.pack(fill="x", padx=20, pady=5)

        tk.Label(dialog, text="Or create new group:").pack(anchor="w", padx=20)
        new_group_var = tk.StringVar()
        new_group_entry = tk.Entry(dialog, textvariable=new_group_var)
        new_group_entry.pack(fill="x", padx=20, pady=5)

        def save_group():
            new_group = new_group_var.get().strip()
            selected_group = new_group if new_group else group_var.get()

            if selected_group:
                self.devices[device_id]["group"] = selected_group
                self.save_devices()
                self.refresh_devices_list()
                self.log_message(f"Device {nickname} assigned to group '{selected_group}'")
            dialog.destroy()

        tk.Button(dialog, text="Save", command=save_group, bg="lightgreen").pack(pady=10)

    def show_device_context_menu(self, event):
        """Affiche le menu contextuel sur clic droit"""
        # Sélectionner l'item sous le curseur
        index = self.devices_listbox.nearest(event.y)
        if index >= 0:
            self.devices_listbox.selection_clear(0, tk.END)
            self.devices_listbox.selection_set(index)
            self.devices_listbox.activate(index)
            # Afficher le menu
            try:
                self.device_context_menu.tk_popup(event.x_root, event.y_root)
            finally:
                self.device_context_menu.grab_release()

    def forget_device(self):
        """Oublie/supprime un device de la liste (peut être reconnecté plus tard)"""
        selection = self.devices_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a device first")
            return

        item_text = self.devices_listbox.get(selection[0])
        display_id = item_text.split('(')[1].split(')')[0]

        # Trouver le vrai device_id
        device_id = self.find_device_by_display_id(display_id)

        if not device_id:
            # C'est peut-être un device non enregistré (WiFi connecté mais pas sauvegardé)
            messagebox.showinfo("Info", "This device is not registered yet, nothing to forget.")
            return

        nickname = self.devices[device_id].get("nickname", device_id)

        # Demander confirmation
        if not messagebox.askyesno("Confirm",
                                   f"Forget device '{nickname}'?\n\n"
                                   f"The device will be removed from the list.\n"
                                   f"You can reconnect it later by scanning or using 'adb connect'."):
            return

        # Supprimer le device de la liste
        del self.devices[device_id]
        self.save_devices()
        self.refresh_devices_list()
        self.log_message(f"Device '{nickname}' ({device_id}) removed from list")

    def reconnect_selected_device(self):
        """Tente de reconnecter le device WiFi sélectionné"""
        selection = self.devices_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a device first")
            return

        item_text = self.devices_listbox.get(selection[0])
        display_id = item_text.split('(')[1].split(')')[0]

        # Trouver le device_id et son IP
        device_id = self.find_device_by_display_id(display_id)

        if device_id and device_id in self.devices:
            info = self.devices[device_id]
            ip = info.get("ip_address")
            nickname = info.get("nickname", device_id)

            if ip:
                self.log_message(f"Reconnecting {nickname} via {ip}:5555...")
                if self.try_reconnect_wireless(device_id, timeout=10):
                    self.log_message(f"✓ Reconnected {nickname}")
                else:
                    self.log_message(f"✗ Failed to reconnect {nickname}")
                self.refresh_devices_list()
            else:
                messagebox.showinfo("Info", f"No IP address saved for {nickname}.\nConnect via USB first to enable WiFi.")
        else:
            # Peut-être un device WiFi non enregistré - essayer de connecter directement
            if self.is_wireless_device(display_id):
                self.log_message(f"Reconnecting {display_id}...")
                stdout, stderr, rc = self.run_adb_command(["connect", display_id], retry_wireless=False)
                if "connected" in stdout.lower():
                    self.log_message(f"✓ Reconnected {display_id}")
                else:
                    self.log_message(f"✗ Failed to reconnect {display_id}: {stderr}")
                self.refresh_devices_list()
            else:
                messagebox.showinfo("Info", "This is a USB device. Reconnection is not applicable.")

    def add_apk_files(self):
        """Ajoute des fichiers APK à la liste d'installation"""
        files = filedialog.askopenfilenames(
            title="Select APK files",
            filetypes=[("APK files", "*.apk"), ("All files", "*.*")]
        )
        
        for file in files:
            self.apk_listbox.insert(tk.END, file)
    
    def refresh_install_devices(self):
        """Rafraîchit la liste des devices pour l'installation"""
        # Nettoyer les anciens checkboxes
        for widget in self.install_devices_frame.winfo_children():
            widget.destroy()

        self.device_checkboxes.clear()
        self.device_groups = {}  # Pour stocker le groupe de chaque device

        # Mettre à jour le dropdown des groupes
        groups = ["Tous"] + self.get_all_groups()
        self.install_group_combo["values"] = groups

        # Obtenir les devices connectés
        stdout, stderr, returncode = self.run_adb_command(["devices"])

        if returncode != 0:
            self.log_message(f"Error getting devices: {stderr}")
            return

        lines = stdout.strip().split('\n')[1:]

        # Organiser les devices par groupe
        devices_by_group = {}
        for line in lines:
            if '\tdevice' in line or '\tunauthorized' in line or '\toffline' in line:
                parts = line.split('\t')
                if len(parts) >= 2:
                    device_id = parts[0]
                    status = parts[1]

                    # Trouver le groupe (chercher par ID USB ou par IP)
                    group = "Non assigné"
                    nickname = f"Device_{device_id[:8]}"
                    for did, info in self.devices.items():
                        ip = info.get("ip_address", "")
                        if did == device_id or (ip and f"{ip}:5555" == device_id):
                            group = info.get("group", "Non assigné")
                            nickname = info.get("nickname", nickname)
                            break

                    if group not in devices_by_group:
                        devices_by_group[group] = []
                    devices_by_group[group].append((device_id, nickname, status))

        # Afficher les devices groupés avec accordéons
        for group in sorted(devices_by_group.keys()):
            device_count = len(devices_by_group[group])
            is_collapsed = self.group_collapsed.get(group, False)

            # Frame conteneur pour le groupe
            group_frame = tk.Frame(self.install_devices_frame)
            group_frame.pack(fill="x", anchor="w", pady=(5, 0))

            # Bouton accordéon (header cliquable)
            arrow = "▶" if is_collapsed else "▼"
            header_btn = tk.Button(
                group_frame,
                text=f"{arrow} {group} ({device_count} devices)",
                font=("Arial", 9, "bold"),
                fg="blue",
                bd=0,
                cursor="hand2",
                anchor="w",
                command=lambda g=group: self.toggle_group_collapse(g)
            )
            header_btn.pack(fill="x", anchor="w")

            # Frame pour les devices (caché si replié)
            devices_frame = tk.Frame(group_frame)
            if not is_collapsed:
                devices_frame.pack(fill="x", anchor="w", padx=(20, 0))

            for device_id, nickname, status in devices_by_group[group]:
                var = tk.BooleanVar()
                status_text = f" - {status.upper()}" if status != "device" else ""
                checkbox = tk.Checkbutton(devices_frame,
                                        text=f"{nickname} ({device_id}){status_text}",
                                        variable=var,
                                        state="disabled" if status != "device" else "normal")
                checkbox.pack(anchor="w")

                if status == "device":
                    self.device_checkboxes[device_id] = var
                    self.device_groups[device_id] = group

    def select_all_devices(self):
        """Sélectionne tous les devices"""
        for var in self.device_checkboxes.values():
            var.set(True)

    def deselect_all_devices(self):
        """Désélectionne tous les devices"""
        for var in self.device_checkboxes.values():
            var.set(False)

    def select_group_devices(self):
        """Sélectionne tous les devices du groupe choisi"""
        selected_group = self.install_group_var.get()

        for device_id, var in self.device_checkboxes.items():
            device_group = self.device_groups.get(device_id, "Non assigné")
            if selected_group == "Tous" or device_group == selected_group:
                var.set(True)
            else:
                var.set(False)

    def toggle_group_collapse(self, group):
        """Toggle l'état replié/déplié d'un groupe dans Install APK"""
        # Sauvegarder les devices sélectionnés avant refresh
        selected_devices = [d for d, var in self.device_checkboxes.items() if var.get()]

        self.group_collapsed[group] = not self.group_collapsed.get(group, False)
        self.refresh_install_devices()

        # Restaurer les sélections
        for device_id in selected_devices:
            if device_id in self.device_checkboxes:
                self.device_checkboxes[device_id].set(True)

    def install_apks(self):
        """Installe les APK sur les devices sélectionnés"""
        # Vérifier qu'il y a des APK et des devices sélectionnés
        apk_count = self.apk_listbox.size()
        if apk_count == 0:
            messagebox.showwarning("Warning", "Please select at least one APK file")
            return
        
        selected_devices = [device_id for device_id, var in self.device_checkboxes.items() if var.get()]
        if not selected_devices:
            messagebox.showwarning("Warning", "Please select at least one device")
            return
        
        # Confirmation
        if not messagebox.askyesno("Confirm installation", 
                                 f"Install {apk_count} APK(s) on {len(selected_devices)} device(s)?"):
            return
        
        # Installation en arrière-plan
        thread = threading.Thread(target=self._install_apks_thread, args=(selected_devices,))
        thread.daemon = True
        thread.start()
    
    def _install_apks_thread(self, selected_devices):
        """Thread pour l'installation des APK (push → vérification taille → pm install)"""
        apk_files = [self.apk_listbox.get(i) for i in range(self.apk_listbox.size())]

        total_operations = len(apk_files) * len(selected_devices)
        current_operation = 0

        for device_id in selected_devices:
            device_name = self.devices.get(device_id, {}).get("nickname", device_id)
            self.log_message(f"Starting installation on {device_name}")

            for apk_file in apk_files:
                current_operation += 1
                apk_name = os.path.basename(apk_file)
                remote_path = f"/data/local/tmp/{apk_name}"

                # Taille locale
                local_size = os.path.getsize(apk_file)
                self.log_message(f"[{current_operation}/{total_operations}] Transfert de {apk_name} ({local_size // 1024 // 1024} Mo) vers {device_name}...")

                # Calculer un timeout selon la taille : 60s de base + 1s par Mo (min 120s)
                size_mb = local_size / (1024 * 1024)
                push_timeout = max(120, 60 + int(size_mb))

                # Étape 1 : push
                stdout, stderr, returncode = self.run_adb_command(
                    ["push", apk_file, remote_path], device_id, timeout=push_timeout)

                if returncode != 0:
                    self.log_message(f"✗ Échec du transfert de {apk_name} vers {device_name}: {stderr}")
                    continue

                # Étape 2 : vérifier que la taille du fichier distant correspond
                stdout, stderr, rc = self.run_adb_command(
                    ["shell", "stat", "-c", "%s", remote_path], device_id)
                if rc != 0:
                    self.log_message(f"✗ Impossible de vérifier la taille distante de {apk_name} sur {device_name}: {stderr}")
                    self.run_adb_command(["shell", "rm", "-f", remote_path], device_id)
                    continue

                remote_size = int(stdout.strip()) if stdout.strip().isdigit() else -1
                if remote_size != local_size:
                    self.log_message(f"✗ Transfert incomplet de {apk_name} sur {device_name}: "
                                     f"{remote_size} octets reçus / {local_size} attendus — installation annulée")
                    self.run_adb_command(["shell", "rm", "-f", remote_path], device_id)
                    continue

                self.log_message(f"Transfert OK ({remote_size} octets). Installation en cours...")

                # Étape 3 : installer depuis le casque
                stdout, stderr, returncode = self.run_adb_command(
                    ["shell", "pm", "install", "-r", remote_path], device_id, timeout=120)

                # Étape 4 : nettoyage du fichier temporaire
                self.run_adb_command(["shell", "rm", "-f", remote_path], device_id)

                if returncode == 0 and "Success" in stdout:
                    self.log_message(f"✓ {apk_name} installé avec succès sur {device_name}")
                else:
                    error = stdout.strip() or stderr.strip()
                    self.log_message(f"✗ Échec installation de {apk_name} sur {device_name}: {error}")

        self.log_message("Installation process completed!")

    # ==================== CASTING METHODS ====================

    def refresh_casting_devices(self):
        """Rafraîchit la liste des devices pour le casting"""
        # Nettoyer les anciens checkboxes
        for widget in self.casting_devices_frame.winfo_children():
            widget.destroy()

        self.casting_checkboxes.clear()
        self.casting_device_groups.clear()

        # Mettre à jour le dropdown des groupes
        groups = ["Tous"] + self.get_all_groups()
        self.casting_group_combo["values"] = groups

        # Obtenir les devices connectés
        stdout, stderr, returncode = self.run_adb_command(["devices"])

        if returncode != 0:
            self.log_message(f"Error getting devices: {stderr}")
            return

        lines = stdout.strip().split('\n')[1:]

        # Organiser les devices par groupe
        devices_by_group = {}
        for line in lines:
            if '\tdevice' in line or '\tunauthorized' in line or '\toffline' in line:
                parts = line.split('\t')
                if len(parts) >= 2:
                    device_id = parts[0]
                    status = parts[1]

                    # Trouver le groupe (chercher par ID USB ou par IP)
                    group = "Non assigné"
                    nickname = f"Device_{device_id[:8]}"
                    for did, info in self.devices.items():
                        ip = info.get("ip_address", "")
                        if did == device_id or (ip and f"{ip}:5555" == device_id):
                            group = info.get("group", "Non assigné")
                            nickname = info.get("nickname", nickname)
                            break

                    if group not in devices_by_group:
                        devices_by_group[group] = []
                    devices_by_group[group].append((device_id, nickname, status))

        # Afficher les devices groupés avec accordéons
        for group in sorted(devices_by_group.keys()):
            device_count = len(devices_by_group[group])
            is_collapsed = self.casting_group_collapsed.get(group, False)

            # Déterminer le preset pour ce groupe
            preset_info = self.get_scrcpy_preset_info(group)

            # Frame conteneur pour le groupe
            group_frame = tk.Frame(self.casting_devices_frame)
            group_frame.pack(fill="x", anchor="w", pady=(5, 0))

            # Bouton accordéon (header cliquable)
            arrow = "▶" if is_collapsed else "▼"
            header_btn = tk.Button(
                group_frame,
                text=f"{arrow} {group} ({device_count} devices) - {preset_info}",
                font=("Arial", 9, "bold"),
                fg="blue",
                bd=0,
                cursor="hand2",
                anchor="w",
                command=lambda g=group: self.toggle_casting_group_collapse(g)
            )
            header_btn.pack(fill="x", anchor="w")

            # Frame pour les devices (caché si replié)
            devices_frame = tk.Frame(group_frame)
            if not is_collapsed:
                devices_frame.pack(fill="x", anchor="w", padx=(20, 0))

            for device_id, nickname, status in devices_by_group[group]:
                var = tk.BooleanVar()
                status_text = f" - {status.upper()}" if status != "device" else ""

                # Create a row frame for checkbox + action links
                row_frame = tk.Frame(devices_frame)
                row_frame.pack(anchor="w", fill="x")

                checkbox = tk.Checkbutton(row_frame,
                                        text=f"{nickname} ({device_id}){status_text}",
                                        variable=var,
                                        state="disabled" if status != "device" else "normal")
                checkbox.pack(side="left")

                if status == "device":
                    self.casting_checkboxes[device_id] = var
                    self.casting_device_groups[device_id] = group

                    # Add action links
                    cast_link = tk.Label(row_frame, text="Cast", fg="blue", cursor="hand2")
                    cast_link.pack(side="left", padx=(10, 5))
                    cast_link.bind("<Button-1>", lambda e, d=device_id: self.cast_single_device(d))

                    disable_link = tk.Label(row_frame, text="Disable Prox", fg="orange", cursor="hand2")
                    disable_link.pack(side="left", padx=5)
                    disable_link.bind("<Button-1>", lambda e, d=device_id: self.disable_proximity_sensor(d))

                    enable_link = tk.Label(row_frame, text="Enable Prox", fg="green", cursor="hand2")
                    enable_link.pack(side="left", padx=5)
                    enable_link.bind("<Button-1>", lambda e, d=device_id: self.enable_proximity_sensor(d))

    def get_scrcpy_preset_info(self, group):
        """Retourne une description du preset pour un groupe"""
        group_lower = group.lower() if group else ""
        if "quest 3" in group_lower:
            return "angle=20, crop=1500x1500"
        elif "quest 2" in group_lower:
            return "crop=1080x900"
        else:
            return "no crop"

    def get_scrcpy_params(self, group):
        """Retourne les paramètres scrcpy selon le groupe"""
        base_params = ["--no-audio"]  # No audio on PC, keep audio on device only
        group_lower = group.lower() if group else ""
        if "quest 3" in group_lower:
            return base_params + ["--angle=20", "--crop=1500:1500:370:200"]
        elif "quest 2" in group_lower:
            return base_params + ["--crop=1080:900:270:270"]
        else:
            return base_params

    def get_device_nickname(self, device_id):
        """Récupère le nickname d'un device (USB ou WiFi)"""
        # Chercher directement
        if device_id in self.devices:
            return self.devices[device_id].get("nickname", device_id)

        # Chercher par IP wireless
        for did, info in self.devices.items():
            ip = info.get("ip_address", "")
            if ip and f"{ip}:5555" == device_id:
                return info.get("nickname", device_id)

        return device_id[:16]  # Tronquer si pas trouvé

    def select_all_casting_devices(self):
        """Sélectionne tous les devices pour le casting"""
        for var in self.casting_checkboxes.values():
            var.set(True)

    def deselect_all_casting_devices(self):
        """Désélectionne tous les devices pour le casting"""
        for var in self.casting_checkboxes.values():
            var.set(False)

    def select_casting_group_devices(self):
        """Sélectionne tous les devices du groupe choisi pour le casting"""
        selected_group = self.casting_group_var.get()

        for device_id, var in self.casting_checkboxes.items():
            device_group = self.casting_device_groups.get(device_id, "Non assigné")
            if selected_group == "Tous" or device_group == selected_group:
                var.set(True)
            else:
                var.set(False)

    def toggle_casting_group_collapse(self, group):
        """Toggle l'état replié/déplié d'un groupe dans Casting"""
        # Sauvegarder les devices sélectionnés avant refresh
        selected_devices = [d for d, var in self.casting_checkboxes.items() if var.get()]

        self.casting_group_collapsed[group] = not self.casting_group_collapsed.get(group, False)
        self.refresh_casting_devices()

        # Restaurer les sélections
        for device_id in selected_devices:
            if device_id in self.casting_checkboxes:
                self.casting_checkboxes[device_id].set(True)

    def start_casting(self):
        """Démarre le casting scrcpy pour les devices sélectionnés"""
        if not self.scrcpy_path:
            messagebox.showerror("Error", "scrcpy.exe not found. Please configure the path.")
            return

        selected = [d for d, var in self.casting_checkboxes.items() if var.get()]
        if not selected:
            messagebox.showwarning("Warning", "Please select at least one device")
            return

        self.log_message(f"Starting casting for {len(selected)} device(s)...")

        # Lancer en arrière-plan pour ne pas bloquer l'interface
        thread = threading.Thread(target=self._start_casting_thread, args=(selected,))
        thread.daemon = True
        thread.start()

    def _start_casting_thread(self, selected_devices):
        """Thread pour lancer le casting"""
        for device_id in selected_devices:
            group = self.casting_device_groups.get(device_id, "")
            nickname = self.get_device_nickname(device_id)
            params = self.get_scrcpy_params(group)

            cmd = [self.scrcpy_path, "-s", device_id] + params + ["--window-title", nickname]

            try:
                subprocess.Popen(cmd)
                self.log_message(f"✓ Started casting for {nickname}")
            except Exception as e:
                self.log_message(f"✗ Failed to start casting for {nickname}: {e}")

            time.sleep(2)  # Délai entre chaque lancement

        self.log_message("Casting started for all selected devices!")

    def cast_single_device(self, device_id):
        """Start casting for a single device"""
        if not self.scrcpy_path:
            messagebox.showerror("Error", "scrcpy.exe not found.")
            return
        group = self.casting_device_groups.get(device_id, "")
        nickname = self.get_device_nickname(device_id)
        params = self.get_scrcpy_params(group)
        cmd = [self.scrcpy_path, "-s", device_id] + params + ["--window-title", nickname]
        try:
            subprocess.Popen(cmd)
            self.log_message(f"✓ Started casting for {nickname}")
        except Exception as e:
            self.log_message(f"✗ Failed to cast {nickname}: {e}")

    def disable_proximity_sensor(self, device_id):
        """Disable proximity sensor for a device"""
        nickname = self.get_device_nickname(device_id)
        stdout, stderr, rc = self.run_adb_command(
            ["shell", "am", "broadcast", "-a", "com.oculus.vrpowermanager.prox_close"],
            device_id
        )
        if rc == 0:
            self.log_message(f"✓ Proximity sensor disabled for {nickname}")
        else:
            self.log_message(f"✗ Failed to disable proximity for {nickname}: {stderr}")

    def enable_proximity_sensor(self, device_id):
        """Enable proximity sensor for a device"""
        nickname = self.get_device_nickname(device_id)
        stdout, stderr, rc = self.run_adb_command(
            ["shell", "am", "broadcast", "-a", "com.oculus.vrpowermanager.automation_disable"],
            device_id
        )
        if rc == 0:
            self.log_message(f"✓ Proximity sensor enabled for {nickname}")
        else:
            self.log_message(f"✗ Failed to enable proximity for {nickname}: {stderr}")

    # ==================== END CASTING METHODS ====================

    def scan_missing_apks(self):
        """Scanne les devices du groupe sélectionné pour les packages installés"""
        selected_group = self.missing_group_var.get()
        group_text = f"group '{selected_group}'" if selected_group != "Tous" else "all devices"
        self.log_message(f"Scanning {group_text} for installed packages...")

        # Nettoyer le tableau
        self.missing_tree.delete(*self.missing_tree.get_children())
        self.all_packages_data = []

        # Obtenir les devices connectés du groupe sélectionné
        connected_devices = self.get_connected_devices_by_group(selected_group)

        if not connected_devices:
            self.log_message(f"No connected devices found in {group_text}")
            return
        
        # Scanner les packages de chaque device
        all_packages = set()
        device_packages = {}
        device_nicknames = {}  # Stocker les nicknames pour les colonnes

        for device_id in connected_devices:
            # Trouver le nickname (supporte USB et wireless IP:5555)
            original_id = self.find_device_by_display_id(device_id)
            if original_id and original_id in self.devices:
                device_name = self.devices[original_id].get("nickname", device_id)
            else:
                device_name = self.devices.get(device_id, {}).get("nickname", device_id)
            device_nicknames[device_id] = device_name

            self.log_message(f"Scanning packages on {device_name}...")

            stdout, stderr, returncode = self.run_adb_command(["shell", "pm", "list", "packages"], device_id)

            if returncode == 0:
                packages = [line.replace("package:", "") for line in stdout.strip().split('\n') if line.startswith("package:")]
                device_packages[device_id] = set(packages)
                all_packages.update(packages)
            else:
                self.log_message(f"Error scanning {device_name}: {stderr}")
                device_packages[device_id] = set()

        # Créer les colonnes du tableau avec nicknames
        columns = ["Package"] + [device_nicknames.get(device_id, device_id) for device_id in connected_devices]
        self.missing_tree["columns"] = columns
        self.missing_tree["show"] = "headings"
        
        for col in columns:
            self.missing_tree.heading(col, text=col)
            self.missing_tree.column(col, width=150)
        
        # Stocker les données pour le filtrage
        for package in sorted(all_packages):
            row_data = {"package": package, "devices": {}}
            row_values = [package]
            has_missing = False
            
            for device_id in connected_devices:
                if package in device_packages[device_id]:
                    row_values.append("✓")
                    row_data["devices"][device_id] = True
                else:
                    row_values.append("")
                    row_data["devices"][device_id] = False
                    has_missing = True
            
            row_data["values"] = row_values
            row_data["has_missing"] = has_missing
            self.all_packages_data.append(row_data)
        
        self.filter_missing_packages()
        self.log_message(f"Scan completed. Found {len(all_packages)} unique packages across {len(connected_devices)} devices")
    
    def filter_missing_packages(self):
        """Filtre les packages selon l'option 'show missing only'"""
        self.missing_tree.delete(*self.missing_tree.get_children())
        
        for row_data in self.all_packages_data:
            if not self.show_missing_only.get() or row_data["has_missing"]:
                self.missing_tree.insert("", "end", values=row_data["values"])
    
    def refresh_uninstall_devices(self):
        """Rafraîchit la liste des devices pour la désinstallation"""
        # Mettre à jour le dropdown des groupes
        groups = ["Tous"] + self.get_all_groups()
        self.uninstall_group_combo["values"] = groups

        selected_group = self.uninstall_group_var.get()

        stdout, stderr, returncode = self.run_adb_command(["devices"])

        devices = []
        if returncode == 0:
            lines = stdout.strip().split('\n')[1:]
            for line in lines:
                if '\tdevice' in line:  # Only show authorized devices for uninstall
                    device_id = line.split('\t')[0]

                    # Trouver le groupe du device
                    group = "Non assigné"
                    nickname = device_id
                    for did, info in self.devices.items():
                        ip = info.get("ip_address", "")
                        if did == device_id or (ip and f"{ip}:5555" == device_id):
                            group = info.get("group", "Non assigné")
                            nickname = info.get("nickname", device_id)
                            break

                    # Filtrer par groupe
                    if selected_group == "Tous" or group == selected_group:
                        devices.append(f"{nickname} ({device_id}) [{group}]")

        self.uninstall_device_combo["values"] = devices
        # Ne pas sélectionner de device par défaut - l'utilisateur doit choisir
        self.uninstall_device_var.set("")
        # Vider la liste des packages
        self.packages_listbox.delete(0, tk.END)
    
    def get_system_packages(self, device_id):
        """Obtient la liste des packages système"""
        self.log_message("Detecting system packages...")
        system_packages = set()
        
        # Utiliser dumpsys package pour détecter les flags système
        stdout, stderr, returncode = self.run_adb_command(["shell", "dumpsys", "package"], device_id)
        
        if returncode == 0:
            current_package = None
            for line in stdout.split('\n'):
                line = line.strip()
                if line.startswith('Package ['):
                    # Extraire le nom du package
                    current_package = line.split('[')[1].split(']')[0]
                elif current_package and 'flags=' in line and 'SYSTEM' in line:
                    system_packages.add(current_package)
        
        return system_packages
    
    def load_device_packages(self):
        """Charge les packages du device sélectionné"""
        if not self.uninstall_device_var.get():
            messagebox.showwarning("Warning", "Please select a device first")
            return
        
        # Extraire l'ID du device
        device_text = self.uninstall_device_var.get()
        device_id = device_text.split('(')[1].split(')')[0]
        
        self.log_message(f"Loading packages for {device_text}...")
        
        # Charger tous les packages
        stdout, stderr, returncode = self.run_adb_command(["shell", "pm", "list", "packages"], device_id)
        
        if returncode != 0:
            self.log_message(f"Error loading packages: {stderr}")
            return
        
        packages = [line.replace("package:", "") for line in stdout.strip().split('\n') if line.startswith("package:")]
        self.all_packages = sorted(packages)
        
        # Détecter les packages système
        self.system_packages = self.get_system_packages(device_id)
        
        self.log_message(f"Loaded {len(packages)} packages ({len(self.system_packages)} system packages)")
        
        # Filtrer et afficher
        self.filter_packages()
    
    def filter_packages(self):
        """Filtre les packages selon l'option 'show system apps'"""
        self.packages_listbox.delete(0, tk.END)
        
        for package in self.all_packages:
            if self.show_system_apps.get() or package not in self.system_packages:
                self.packages_listbox.insert(tk.END, package)
    
    def uninstall_from_device(self):
        """Désinstalle le package du device sélectionné"""
        if not self.uninstall_device_var.get():
            messagebox.showwarning("Warning", "Please select a device first")
            return
        
        selection = self.packages_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a package to uninstall")
            return
        
        package = self.packages_listbox.get(selection[0])
        device_text = self.uninstall_device_var.get()
        device_id = device_text.split('(')[1].split(')')[0]
        
        # Avertissement pour les apps système
        if package in self.system_packages:
            if not messagebox.askyesno("WARNING - System App", 
                                     f"'{package}' is a SYSTEM application!\n\n"
                                     f"Uninstalling system apps can cause device instability.\n\n"
                                     f"Are you sure you want to continue?"):
                return
        
        if not messagebox.askyesno("Confirm uninstall", f"Uninstall {package} from {device_text}?"):
            return
        
        self.log_message(f"Uninstalling {package} from {device_text}...")
        
        stdout, stderr, returncode = self.run_adb_command(["uninstall", package], device_id)
        
        if returncode == 0:
            self.log_message(f"✓ {package} uninstalled successfully")
            self.load_device_packages()  # Refresh list
        else:
            self.log_message(f"✗ Failed to uninstall {package}: {stderr}")
    
    def uninstall_from_all_devices(self):
        """Désinstalle le package de tous les devices connectés"""
        selection = self.packages_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a package to uninstall")
            return
        
        package = self.packages_listbox.get(selection[0])
        
        # Avertissement pour les apps système
        if package in self.system_packages:
            if not messagebox.askyesno("WARNING - System App", 
                                     f"'{package}' is a SYSTEM application!\n\n"
                                     f"Uninstalling system apps can cause device instability.\n\n"
                                     f"Are you sure you want to continue?"):
                return
        
        # Obtenir tous les devices connectés
        stdout, stderr, returncode = self.run_adb_command(["devices"])
        
        if returncode != 0:
            self.log_message(f"Error getting devices: {stderr}")
            return
        
        lines = stdout.strip().split('\n')[1:]
        connected_devices = []
        
        for line in lines:
            if '\tdevice' in line:
                device_id = line.split('\t')[0]
                connected_devices.append(device_id)
        
        if not connected_devices:
            self.log_message("No connected devices found")
            return
        
        if not messagebox.askyesno("Confirm uninstall", 
                                 f"Uninstall {package} from ALL {len(connected_devices)} connected devices?"):
            return
        
        # Désinstallation en arrière-plan
        thread = threading.Thread(target=self._uninstall_from_all_thread, args=(package, connected_devices))
        thread.daemon = True
        thread.start()
    
    def _uninstall_from_all_thread(self, package, devices):
        """Thread pour la désinstallation sur tous les devices"""
        for device_id in devices:
            device_name = self.devices.get(device_id, {}).get("nickname", device_id)
            self.log_message(f"Uninstalling {package} from {device_name}...")
            
            stdout, stderr, returncode = self.run_adb_command(["uninstall", package], device_id)
            
            if returncode == 0:
                self.log_message(f"✓ {package} uninstalled from {device_name}")
            else:
                if "not installed" in stderr.lower():
                    self.log_message(f"- {package} was not installed on {device_name}")
                else:
                    self.log_message(f"✗ Failed to uninstall {package} from {device_name}: {stderr}")
        
        self.log_message("Uninstall process completed!")

    def uninstall_from_group(self):
        """Désinstalle le package de tous les devices du groupe sélectionné"""
        selection = self.packages_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a package to uninstall")
            return

        package = self.packages_listbox.get(selection[0])
        selected_group = self.uninstall_group_var.get()

        # Avertissement pour les apps système
        if package in self.system_packages:
            if not messagebox.askyesno("WARNING - System App",
                                     f"'{package}' is a SYSTEM application!\n\n"
                                     f"Uninstalling system apps can cause device instability.\n\n"
                                     f"Are you sure you want to continue?"):
                return

        # Obtenir les devices connectés du groupe
        group_devices = self.get_connected_devices_by_group(selected_group)

        if not group_devices:
            messagebox.showinfo("Info", f"No connected devices in group '{selected_group}'")
            return

        group_text = f"group '{selected_group}'" if selected_group != "Tous" else "ALL devices"
        if not messagebox.askyesno("Confirm uninstall",
                                 f"Uninstall {package} from {len(group_devices)} device(s) in {group_text}?"):
            return

        # Désinstallation en arrière-plan
        thread = threading.Thread(target=self._uninstall_from_all_thread, args=(package, group_devices))
        thread.daemon = True
        thread.start()

    def refresh_sync_groups(self):
        """Rafraîchit les dropdowns de groupes pour Sync"""
        groups = ["Default"] + self.get_all_groups()
        self.sync_group_combo["values"] = groups

        target_groups = ["Tous"] + self.get_all_groups()
        self.sync_target_group_combo["values"] = target_groups

    def on_sync_group_change(self, event):
        """Charge les paths pour le groupe sélectionné"""
        selected_group = self.sync_group_var.get()

        if selected_group == "Default":
            # Charger les paths par défaut
            self.videos_path_var.set(self.sync_paths.get("videos", "/sdcard/Movies/"))
            self.photos_path_var.set(self.sync_paths.get("photos", "/sdcard/Pictures/"))
            self.sync_path_info_label.config(text="(Default paths for all groups)")
        else:
            # Charger les paths spécifiques au groupe, ou défaut si non définis
            videos_key = f"group_{selected_group}_videos"
            photos_key = f"group_{selected_group}_photos"
            self.videos_path_var.set(self.sync_paths.get(videos_key, self.sync_paths.get("videos", "/sdcard/Movies/")))
            self.photos_path_var.set(self.sync_paths.get(photos_key, self.sync_paths.get("photos", "/sdcard/Pictures/")))
            self.sync_path_info_label.config(text=f"(Paths for group: {selected_group})")

    def get_sync_path_for_group(self, group, path_type):
        """Retourne le path de sync pour un groupe (videos ou photos)"""
        if group and group != "Default":
            key = f"group_{group}_{path_type}"
            if key in self.sync_paths:
                return self.sync_paths[key]
        # Fallback vers le path par défaut
        return self.sync_paths.get(path_type, "")

    def save_sync_paths(self):
        """Sauvegarde les chemins de synchronisation pour le groupe sélectionné"""
        selected_group = self.sync_group_var.get()

        if selected_group == "Default":
            # Sauvegarder les paths par défaut
            self.sync_paths["videos"] = self.videos_path_var.get()
            self.sync_paths["photos"] = self.photos_path_var.get()
            self.log_message("Default sync paths saved")
        else:
            # Sauvegarder les paths pour le groupe
            self.sync_paths[f"group_{selected_group}_videos"] = self.videos_path_var.get()
            self.sync_paths[f"group_{selected_group}_photos"] = self.photos_path_var.get()
            self.log_message(f"Sync paths saved for group '{selected_group}'")

        self.save_config()

    def browse_pc_folder(self):
        """Sélectionne un dossier PC pour la synchronisation"""
        folder = filedialog.askdirectory(title="Select PC folder to sync")
        if folder:
            self.pc_folder_var.set(folder)
            # Sauvegarder le dernier dossier utilisé
            self.sync_paths["last_pc_folder"] = folder
            self.save_config()

    def on_headset_folder_type_change(self, event):
        """Gérer le changement de type de dossier headset"""
        folder_type = self.headset_folder_type.get()
        target_group = self.sync_target_group_var.get()

        # Déterminer le groupe à utiliser pour les paths
        if target_group == "Tous":
            group_for_path = "Default"
        else:
            group_for_path = target_group

        if folder_type == "Videos (group path)":
            self.headset_folder_var.set(self.get_sync_path_for_group(group_for_path, "videos"))
        elif folder_type == "Photos (group path)":
            self.headset_folder_var.set(self.get_sync_path_for_group(group_for_path, "photos"))
        elif folder_type == "Custom":
            self.headset_folder_var.set("")
    
    def browse_headset_folder(self):
        """Navigue dans l'arborescence du casque"""
        # Obtenir un device connecté
        stdout, stderr, returncode = self.run_adb_command(["devices"])
        
        if returncode != 0:
            messagebox.showerror("Error", "Cannot connect to device")
            return
        
        lines = stdout.strip().split('\n')[1:]
        device_id = None
        
        for line in lines:
            if '\tdevice' in line:
                device_id = line.split('\t')[0]
                break
        
        if not device_id:
            messagebox.showerror("Error", "No connected device found")
            return
        
        # Simple dialog pour entrer le chemin (navigation complète serait complexe)
        current_path = self.headset_folder_var.get() or "/sdcard/"
        new_path = simpledialog.askstring("Headset folder", 
                                        f"Enter headset folder path:\n(Examples: /sdcard/Movies/, /sdcard/Pictures/, /sdcard/Download/)",
                                        initialvalue=current_path)
        
        if new_path:
            # Vérifier que le dossier existe
            stdout, stderr, returncode = self.run_adb_command(["shell", "ls", new_path], device_id)
            if returncode == 0:
                self.headset_folder_var.set(new_path)
                self.headset_folder_type.set("Custom")
            else:
                if messagebox.askyesno("Folder not found", f"Folder '{new_path}' does not exist.\nCreate it?"):
                    stdout, stderr, returncode = self.run_adb_command(["shell", "mkdir", "-p", new_path], device_id)
                    if returncode == 0:
                        self.headset_folder_var.set(new_path)
                        self.headset_folder_type.set("Custom")
                        self.log_message(f"Created folder: {new_path}")
                    else:
                        messagebox.showerror("Error", f"Failed to create folder: {stderr}")
    
    def start_sync(self):
        """Démarre la synchronisation vers le groupe sélectionné"""
        pc_folder = self.pc_folder_var.get()
        headset_folder = self.headset_folder_var.get()

        if not pc_folder or not headset_folder:
            messagebox.showwarning("Warning", "Please specify both PC folder and headset folder")
            return

        if not os.path.exists(pc_folder):
            messagebox.showerror("Error", "PC folder does not exist")
            return

        # Obtenir les devices connectés du groupe sélectionné
        target_group = self.sync_target_group_var.get()
        connected_devices = self.get_connected_devices_by_group(target_group)

        if not connected_devices:
            group_text = f"group '{target_group}'" if target_group != "Tous" else "any group"
            messagebox.showerror("Error", f"No connected devices found in {group_text}")
            return

        group_text = f"group '{target_group}'" if target_group != "Tous" else "ALL devices"
        if not messagebox.askyesno("Confirm sync",
                                 f"Sync {pc_folder} to {headset_folder}\non {len(connected_devices)} device(s) in {group_text}?"):
            return

        # Réinitialiser les options globales
        self.apply_to_all_devices = False
        self.apply_to_all_files = False
        self.fat32_skipped_files = set()
        self._fs_cache = {}  # cache filesystem type par device_id

        # Synchronisation en arrière-plan
        thread = threading.Thread(target=self._sync_thread, args=(pc_folder, headset_folder, connected_devices))
        thread.daemon = True
        thread.start()
    
    def _sync_thread(self, pc_folder, headset_folder, devices):
        """Thread pour la synchronisation"""
        self.log_message(f"Starting sync: {pc_folder} -> {headset_folder}")
        
        # Obtenir la liste des fichiers à synchroniser
        files_to_sync = []
        for root, dirs, files in os.walk(pc_folder):
            for file in files:
                local_path = os.path.join(root, file)
                relative_path = os.path.relpath(local_path, pc_folder)
                files_to_sync.append((local_path, relative_path))
        
        self.log_message(f"Found {len(files_to_sync)} files to sync")
        
        for device_index, device_id in enumerate(devices):
            device_name = self.devices.get(device_id, {}).get("nickname", device_id)
            self.log_message(f"Syncing to {device_name}...")
            
            # Vérifier les fichiers existants sur le casque
            existing_files = self._get_headset_files(device_id, headset_folder)
            
            # Détecter les fichiers à supprimer (présents sur casque mais pas sur PC)
            files_to_delete = []
            pc_files = {relative_path for _, relative_path in files_to_sync}
            
            for existing_file in existing_files:
                if existing_file not in pc_files:
                    files_to_delete.append(existing_file)
            
            # Traiter les suppressions si nécessaire
            if files_to_delete and not self.apply_to_all_files:
                self._handle_deletions(device_id, device_name, headset_folder, files_to_delete, device_index == 0)
            
            # Synchroniser les fichiers
            for local_path, relative_path in files_to_sync:
                remote_path = f"{headset_folder}/{relative_path}".replace('\\', '/')
                
                # Vérifier si le fichier existe déjà
                stdout, stderr, returncode = self.run_adb_command(["shell", "ls", "-la", remote_path], device_id)
                
                file_exists = (returncode == 0)
                
                if file_exists and not self.apply_to_all_files:
                    # Fichier existe, demander quoi faire
                    action = self._handle_file_conflict(relative_path, device_name, device_index == 0)
                    if action == "skip":
                        continue
                    elif action == "rename":
                        # Pour simplicité, ajouter un timestamp
                        name, ext = os.path.splitext(remote_path)
                        timestamp = datetime.now().strftime("_%Y%m%d_%H%M%S")
                        remote_path = f"{name}{timestamp}{ext}"
                
                # Vérifier limite FAT32 (4 Go) avant le push
                FAT32_LIMIT = 4 * 1024 ** 3
                if relative_path in self.fat32_skipped_files:
                    self.log_message(f"⚠ Ignoré (FAT32 >4 Go) : {relative_path}")
                    continue
                local_size = os.path.getsize(local_path)
                if local_size >= FAT32_LIMIT:
                    fs = self._detect_filesystem(device_id, headset_folder)
                    if fs == "fat32":
                        self._warn_fat32_skip(relative_path)
                        self.log_message(f"⚠ Ignoré (FAT32 >4 Go) : {relative_path}")
                        continue

                # Créer le dossier de destination si nécessaire
                remote_dir = '/'.join(remote_path.split('/')[:-1])
                self.run_adb_command(["shell", "mkdir", "-p", remote_dir], device_id)

                # Copier le fichier (timeout dynamique : 120s min + 1s/Mo)
                size_mb = os.path.getsize(local_path) / (1024 * 1024)
                push_timeout = max(120, 60 + int(size_mb))
                stdout, stderr, returncode = self.run_adb_command(["push", local_path, remote_path], device_id, timeout=push_timeout)
                
                if returncode == 0:
                    self.log_message(f"✓ {relative_path} -> {device_name}")
                else:
                    self.log_message(f"✗ Failed to copy {relative_path} to {device_name}: {stderr}")
        
        self.log_message("Sync completed!")
    
    def _detect_filesystem(self, device_id, path):
        """Retourne 'fat32', 'exfat', ou 'other' pour le FS qui héberge path sur le device."""
        if device_id in self._fs_cache:
            return self._fs_cache[device_id]
        stdout, _, returncode = self.run_adb_command(["shell", "cat", "/proc/mounts"], device_id)
        fs_type = "other"
        if returncode == 0:
            best_len = -1
            for line in stdout.splitlines():
                parts = line.split()
                if len(parts) < 3:
                    continue
                mount_point, fstype = parts[1], parts[2].lower()
                if path.startswith(mount_point) and len(mount_point) > best_len:
                    best_len = len(mount_point)
                    if fstype in ("vfat", "fat32", "msdos"):
                        fs_type = "fat32"
                    elif fstype in ("exfat", "fuse.exfat"):
                        fs_type = "exfat"
                    else:
                        fs_type = "other"
        self._fs_cache[device_id] = fs_type
        return fs_type

    def _warn_fat32_skip(self, filename):
        """Affiche un avertissement FAT32 (thread principal) et ajoute le fichier aux skips de session."""
        event = threading.Event()

        def show():
            messagebox.showwarning(
                "Fichier trop grand (FAT32)",
                f"Le fichier suivant dépasse 4 Go et ne peut pas être copié\n"
                f"sur un volume FAT32 :\n\n{filename}\n\n"
                f"Il sera ignoré pour tous les casques de cette session."
            )
            self.fat32_skipped_files.add(filename)
            event.set()

        self.root.after(0, show)
        event.wait()

    def _get_headset_files(self, device_id, headset_folder):
        """Obtient la liste des fichiers sur le casque"""
        files = []
        stdout, stderr, returncode = self.run_adb_command(["shell", "find", headset_folder, "-type", "f"], device_id)
        
        if returncode == 0:
            for line in stdout.strip().split('\n'):
                if line and line.startswith(headset_folder):
                    relative_path = line[len(headset_folder):].lstrip('/')
                    if relative_path:
                        files.append(relative_path)
        
        return files
    
    def _handle_deletions(self, device_id, device_name, headset_folder, files_to_delete, is_first_device):
        """Gère les fichiers à supprimer"""
        if not files_to_delete:
            return
        
        # Créer le dialog dans le thread principal
        def ask_deletion():
            dialog = tk.Toplevel(self.root)
            dialog.title("Files to delete")
            dialog.geometry("500x400")
            dialog.grab_set()
            
            result = {"action": None, "apply_devices": False, "apply_files": False}
            
            tk.Label(dialog, text=f"The following files exist on {device_name} but not on PC:", 
                    font=("Arial", 10, "bold")).pack(pady=5)
            
            # Liste des fichiers
            listbox = tk.Listbox(dialog, height=10)
            scrollbar = tk.Scrollbar(dialog, orient="vertical", command=listbox.yview)
            listbox.configure(yscrollcommand=scrollbar.set)
            
            for file in files_to_delete:
                listbox.insert(tk.END, file)
            
            listbox.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=5)
            scrollbar.pack(side="right", fill="y", pady=5)
            
            # Options
            apply_devices_var = tk.BooleanVar()
            apply_files_var = tk.BooleanVar()
            
            if is_first_device:
                tk.Checkbutton(dialog, text="Apply to all headsets for this session", 
                              variable=apply_devices_var).pack(pady=2)
            
            tk.Checkbutton(dialog, text="Apply to all files for this session", 
                          variable=apply_files_var).pack(pady=2)
            
            # Boutons
            btn_frame = tk.Frame(dialog)
            btn_frame.pack(pady=10)
            
            def on_delete():
                result["action"] = "delete"
                result["apply_devices"] = apply_devices_var.get()
                result["apply_files"] = apply_files_var.get()
                dialog.destroy()
            
            def on_keep():
                result["action"] = "keep"
                result["apply_devices"] = apply_devices_var.get()
                result["apply_files"] = apply_files_var.get()
                dialog.destroy()
            
            tk.Button(btn_frame, text="Delete files", command=on_delete, bg="red", fg="white").pack(side="left", padx=5)
            tk.Button(btn_frame, text="Keep files", command=on_keep, bg="green", fg="white").pack(side="left", padx=5)
            
            dialog.wait_window()
            return result
        
        # Demander seulement si pas déjà appliqué globalement
        if not self.apply_to_all_files:
            result = self.root.after(0, ask_deletion)
            # Attendre le résultat (simplification - dans un vrai cas il faudrait une queue)
            # Pour cette démo, on va juste logger
            self.log_message(f"Found {len(files_to_delete)} files to potentially delete on {device_name}")
    
    def _handle_file_conflict(self, filename, device_name, is_first_device):
        """Gère les conflits de fichiers"""
        # Simplification - dans la vraie version il faudrait un dialog
        # Pour cette démo, on va écraser par défaut
        return "overwrite"
    def refresh_ed_devices(self):
        """Rafraîchit la liste des devices pour l'onglet Enable/Disable avec checkboxes"""
        # Nettoyer les anciens checkboxes
        for widget in self.ed_devices_frame.winfo_children():
            widget.destroy()

        self.ed_device_checkboxes.clear()
        self.ed_device_groups = {}

        # Mettre à jour le dropdown des groupes
        groups = ["Tous"] + self.get_all_groups()
        self.ed_group_combo["values"] = groups

        # Obtenir les devices connectés
        stdout, stderr, returncode = self.run_adb_command(["devices"])

        if returncode != 0:
            self.log_message(f"Error getting devices: {stderr}")
            return

        lines = stdout.strip().split('\n')[1:]

        for line in lines:
            if '\tdevice' in line:
                parts = line.split('\t')
                if len(parts) >= 2:
                    device_id = parts[0]
                    status = parts[1]

                    # Trouver le groupe et nickname
                    group = "Non assigné"
                    nickname = f"Device_{device_id[:8]}"
                    for did, info in self.devices.items():
                        ip = info.get("ip_address", "")
                        if did == device_id or (ip and f"{ip}:5555" == device_id):
                            group = info.get("group", "Non assigné")
                            nickname = info.get("nickname", nickname)
                            break

                    var = tk.BooleanVar()
                    checkbox = tk.Checkbutton(self.ed_devices_frame,
                                            text=f"{nickname} ({device_id}) [{group}]",
                                            variable=var)
                    checkbox.pack(anchor="w")

                    self.ed_device_checkboxes[device_id] = var
                    self.ed_device_groups[device_id] = group

        # Vider la liste des packages
        self.ed_listbox.delete(0, tk.END)

    def select_all_ed_devices(self):
        """Sélectionne tous les devices pour Enable/Disable"""
        for var in self.ed_device_checkboxes.values():
            var.set(True)

    def deselect_all_ed_devices(self):
        """Désélectionne tous les devices pour Enable/Disable"""
        for var in self.ed_device_checkboxes.values():
            var.set(False)

    def select_ed_group_devices(self):
        """Sélectionne les devices du groupe choisi pour Enable/Disable"""
        selected_group = self.ed_group_var.get()

        for device_id, var in self.ed_device_checkboxes.items():
            device_group = self.ed_device_groups.get(device_id, "Non assigné")
            if selected_group == "Tous" or device_group == selected_group:
                var.set(True)
            else:
                var.set(False)

    def load_ed_packages(self):
        """Charge la liste des apps installées sur le premier casque sélectionné"""
        selected_devices = [d for d, var in self.ed_device_checkboxes.items() if var.get()]

        if not selected_devices:
            messagebox.showwarning("Warning", "Select at least one device first")
            return

        # Utiliser le premier device sélectionné pour charger la liste des packages
        device_id = selected_devices[0]
        nickname = device_id
        for did, info in self.devices.items():
            ip = info.get("ip_address", "")
            if did == device_id or (ip and f"{ip}:5555" == device_id):
                nickname = info.get("nickname", device_id)
                break

        self.log_message(f"Loading packages from {nickname}...")

        # Charger tous les packages
        stdout, stderr, returncode = self.run_adb_command(["shell", "pm", "list", "packages"], device_id)
        if returncode != 0:
            self.log_message(f"Error loading packages: {stderr}")
            return
        packages = [line.replace("package:", "").strip() for line in stdout.strip().split('\n') if line.startswith("package:")]

        # Récupérer les packages désactivés pour chaque utilisateur
        disabled_packages = set()
        users = self.get_device_users(device_id)
        for user_id in users:
            stdout, stderr, returncode = self.run_adb_command(
                ["shell", "pm", "list", "packages", "-d", "--user", user_id], device_id)
            if returncode == 0:
                for line in stdout.strip().split('\n'):
                    if line.startswith("package:"):
                        pkg = line.replace("package:", "").strip()
                        disabled_packages.add(pkg)

        self.ed_listbox.delete(0, tk.END)
        for pkg in sorted(packages):
            self.ed_listbox.insert(tk.END, pkg)
            index = self.ed_listbox.size() - 1
            if pkg in disabled_packages:
                self.ed_listbox.itemconfig(index, fg="red")

        self.log_message(f"Loaded {len(packages)} packages ({len(disabled_packages)} disabled)")

    def get_device_users(self, device_id):
        """Récupère la liste des IDs utilisateurs sur le device"""
        stdout, stderr, returncode = self.run_adb_command(["shell", "pm", "list", "users"], device_id)
        users = []
        if returncode == 0:
            for line in stdout.strip().split('\n'):
                if 'UserInfo{' in line:
                    # Extraire l'ID utilisateur: UserInfo{0:Name:flags}
                    try:
                        user_id = line.split('{')[1].split(':')[0]
                        users.append(user_id)
                    except:
                        pass
        return users if users else ["0"]  # Défaut à user 0 si aucun trouvé

    def disable_selected_apps(self):
        """Désactive les applications sélectionnées sur tous les devices sélectionnés"""
        selection = self.ed_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Select at least one app first")
            return

        selected_devices = [d for d, var in self.ed_device_checkboxes.items() if var.get()]
        if not selected_devices:
            messagebox.showwarning("Warning", "Select at least one device first")
            return

        packages = [self.ed_listbox.get(i) for i in selection]

        # Confirmation
        if not messagebox.askyesno("Confirm",
                                   f"Disable {len(packages)} app(s) on {len(selected_devices)} device(s)?"):
            return

        # Exécution en arrière-plan
        thread = threading.Thread(target=self._disable_apps_thread, args=(packages, selected_devices))
        thread.daemon = True
        thread.start()

    def _disable_apps_thread(self, packages, devices):
        """Thread pour désactiver les apps sur plusieurs devices"""
        total = len(packages) * len(devices)
        current = 0

        for device_id in devices:
            # Trouver le nickname
            nickname = device_id
            for did, info in self.devices.items():
                ip = info.get("ip_address", "")
                if did == device_id or (ip and f"{ip}:5555" == device_id):
                    nickname = info.get("nickname", device_id)
                    break

            self.log_message(f"Processing {nickname}...")

            if self.ed_all_users_var.get():
                users = self.get_device_users(device_id)
            else:
                users = ["0"]

            for package in packages:
                current += 1
                for user_id in users:
                    stdout, stderr, returncode = self.run_adb_command(
                        ["shell", "pm", "disable-user", "--user", user_id, package], device_id)
                    if returncode == 0:
                        self.log_message(f"[{current}/{total}] ✓ {package} disabled on {nickname} (user {user_id})")
                    else:
                        self.log_message(f"[{current}/{total}] ✗ Failed to disable {package} on {nickname}: {stderr}")

        self.log_message("Disable operation completed!")
        # Rafraîchir la liste pour mettre à jour les couleurs
        self.root.after(0, self.load_ed_packages)

    def enable_selected_apps(self):
        """Réactive les applications sélectionnées sur tous les devices sélectionnés"""
        selection = self.ed_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Select at least one app first")
            return

        selected_devices = [d for d, var in self.ed_device_checkboxes.items() if var.get()]
        if not selected_devices:
            messagebox.showwarning("Warning", "Select at least one device first")
            return

        packages = [self.ed_listbox.get(i) for i in selection]

        # Confirmation
        if not messagebox.askyesno("Confirm",
                                   f"Enable {len(packages)} app(s) on {len(selected_devices)} device(s)?"):
            return

        # Exécution en arrière-plan
        thread = threading.Thread(target=self._enable_apps_thread, args=(packages, selected_devices))
        thread.daemon = True
        thread.start()

    def _enable_apps_thread(self, packages, devices):
        """Thread pour activer les apps sur plusieurs devices"""
        total = len(packages) * len(devices)
        current = 0

        for device_id in devices:
            # Trouver le nickname
            nickname = device_id
            for did, info in self.devices.items():
                ip = info.get("ip_address", "")
                if did == device_id or (ip and f"{ip}:5555" == device_id):
                    nickname = info.get("nickname", device_id)
                    break

            self.log_message(f"Processing {nickname}...")

            if self.ed_all_users_var.get():
                users = self.get_device_users(device_id)
            else:
                users = ["0"]

            for package in packages:
                current += 1
                for user_id in users:
                    stdout, stderr, returncode = self.run_adb_command(
                        ["shell", "pm", "enable", "--user", user_id, package], device_id)
                    if returncode == 0:
                        self.log_message(f"[{current}/{total}] ✓ {package} enabled on {nickname} (user {user_id})")
                    else:
                        self.log_message(f"[{current}/{total}] ✗ Failed to enable {package} on {nickname}: {stderr}")

        self.log_message("Enable operation completed!")
        # Rafraîchir la liste pour mettre à jour les couleurs
        self.root.after(0, self.load_ed_packages)

    def on_tab_changed(self, event):
        """Rafraîchit automatiquement les données de l'onglet actif"""
        tab_index = event.widget.index("current")
        tab_name = event.widget.tab(tab_index, "text")

        if tab_name == "Scan for devices":
            pass  # Pas de refresh auto (scan manuel)
        elif tab_name == "Install APK":
            self.refresh_install_devices()
        elif tab_name == "Scan for missing APKs":
            self.refresh_missing_groups()
        elif tab_name == "Uninstall APK":
            self.refresh_uninstall_devices()
        elif tab_name == "Sync folder":
            self.refresh_sync_groups()
        elif tab_name == "Enable / Disable App":
            self.refresh_ed_devices()
        elif tab_name == "Casting":
            self.refresh_casting_devices()

    def refresh_missing_groups(self):
        """Met à jour le dropdown des groupes dans Missing APKs"""
        if hasattr(self, 'missing_group_combo'):
            groups = ["Tous"] + self.get_all_groups()
            self.missing_group_combo["values"] = groups

    def run(self):
        """Lance l'application"""
        self.log_message("USB VR Manager started")
        self.log_message(f"ADB path: {self.adb_path}")
        self.root.mainloop()

if __name__ == "__main__":
    app = USBVRManager()
    app.run()
