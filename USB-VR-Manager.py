import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import subprocess
import os
import csv
from datetime import datetime
import threading
from pathlib import Path

class USBVRManager:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("USB-VR-Manager by Carl")
        self.root.geometry("900x700")
        
        # Configuration
        self.adb_path = self.find_adb_path()
        self.devices_file = "devices.csv"
        self.config_file = "config.csv"
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
        
        self.load_devices()
        self.load_config()
        self.create_interface()
        
    def find_adb_path(self):
        """Trouve le chemin vers adb.exe"""
        # Chemin SideQuest par défaut
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
    
    def load_devices(self):
        """Charge la liste des devices depuis le CSV"""
        if os.path.exists(self.devices_file):
            with open(self.devices_file, 'r', newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                for row in reader:
                    if len(row) >= 3:
                        device_id, nickname, last_seen = row
                        self.devices[device_id] = {"nickname": nickname, "last_seen": last_seen}
    
    def save_devices(self):
        """Sauvegarde la liste des devices dans le CSV"""
        with open(self.devices_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            for device_id, info in self.devices.items():
                writer.writerow([device_id, info["nickname"], info["last_seen"]])
    
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
    
    def run_adb_command(self, command, device_id=None):
        """Exécute une commande ADB"""
        try:
            if device_id:
                cmd = [self.adb_path, "-s", device_id] + command
            else:
                cmd = [self.adb_path] + command
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return result.stdout, result.stderr, result.returncode
        except subprocess.TimeoutExpired:
            return "", "Command timeout", 1
        except Exception as e:
            return "", str(e), 1
    
    def log_message(self, message):
        """Affiche un message dans la zone de logs"""
        self.log_text.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] {message}\n")
        self.log_text.see(tk.END)
        self.root.update()
    
    def create_interface(self):
        """Crée l'interface utilisateur"""
        # Création du notebook (onglets)
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Onglet 1: Scan for devices
        self.create_scan_tab(notebook)
        
        # Onglet 2: Install APK
        self.create_install_tab(notebook)
        
        # Onglet 3: Scan for missing APKs
        self.create_missing_apk_tab(notebook)
        
        # Onglet 4: Uninstall APK
        self.create_uninstall_tab(notebook)
        
        # Onglet 5: Sync folder
        self.create_sync_tab(notebook)
        
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
        
        # Bouton scan
        scan_btn = tk.Button(frame, text="Scan for connected devices", command=self.scan_devices)
        scan_btn.pack(pady=10)
        
        # Liste des devices avec couleurs
        self.devices_listbox = tk.Listbox(frame, height=15)
        self.devices_listbox.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Bouton pour renommer
        rename_btn = tk.Button(frame, text="Set nickname for selected device", command=self.set_nickname)
        rename_btn.pack(pady=5)
        
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
        
        device_btn_frame = tk.Frame(device_frame)
        device_btn_frame.pack(fill="x")
        
        tk.Button(device_btn_frame, text="Refresh devices", command=self.refresh_install_devices).pack(side="left", padx=5)
        tk.Button(device_btn_frame, text="Select all", command=self.select_all_devices).pack(side="left", padx=5)
        tk.Button(device_btn_frame, text="Deselect all", command=self.deselect_all_devices).pack(side="left", padx=5)
        
        # Frame pour les checkboxes des devices
        self.install_devices_frame = tk.Frame(device_frame)
        self.install_devices_frame.pack(fill="both", expand=True, pady=5)
        
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
        
        # Contrôles
        control_frame = tk.Frame(frame)
        control_frame.pack(fill="x", padx=10, pady=5)
        
        scan_missing_btn = tk.Button(control_frame, text="Scan all devices for installed packages", command=self.scan_missing_apks)
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
        
        # Sélection du device
        device_frame = tk.Frame(frame)
        device_frame.pack(fill="x", padx=10, pady=5)
        
        tk.Label(device_frame, text="Select device:").pack(anchor="w")
        self.uninstall_device_var = tk.StringVar()
        self.uninstall_device_combo = ttk.Combobox(device_frame, textvariable=self.uninstall_device_var, state="readonly")
        self.uninstall_device_combo.pack(fill="x", pady=5)
        
        controls_frame = tk.Frame(device_frame)
        controls_frame.pack(fill="x", pady=5)
        
        tk.Button(controls_frame, text="Refresh devices", command=self.refresh_uninstall_devices).pack(side="left", padx=5)
        tk.Button(controls_frame, text="Load packages", command=self.load_device_packages).pack(side="left", padx=5)
        
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
        tk.Button(uninstall_frame, text="Uninstall from ALL devices", command=self.uninstall_from_all_devices).pack(side="left", padx=5)
        
        # Stocker tous les packages pour le filtrage
        self.all_packages = []
        self.system_packages = set()
    
    def create_sync_tab(self, notebook):
        """Crée l'onglet Sync folder"""
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="Sync folder")
        
        # Configuration des chemins
        config_frame = tk.LabelFrame(frame, text="Sync paths configuration")
        config_frame.pack(fill="x", padx=10, pady=5)
        
        # Videos path
        tk.Label(config_frame, text="Default videos path:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.videos_path_var = tk.StringVar(value=self.sync_paths["videos"])
        tk.Entry(config_frame, textvariable=self.videos_path_var, width=50).grid(row=0, column=1, padx=5, pady=2)
        
        # Photos path
        tk.Label(config_frame, text="Default photos path:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        self.photos_path_var = tk.StringVar(value=self.sync_paths["photos"])
        tk.Entry(config_frame, textvariable=self.photos_path_var, width=50).grid(row=1, column=1, padx=5, pady=2)
        
        tk.Button(config_frame, text="Save default paths", command=self.save_sync_paths).grid(row=2, column=1, sticky="e", padx=5, pady=5)
        
        # Sync operations
        sync_frame = tk.LabelFrame(frame, text="Sync operations")
        sync_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
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
                                   values=["Default Videos", "Default Photos", "Custom"], state="readonly")
        headset_combo.pack(side="left", padx=(0, 5))
        headset_combo.bind("<<ComboboxSelected>>", self.on_headset_folder_type_change)
        
        tk.Button(dropdown_frame, text="Browse Headset", command=self.browse_headset_folder).pack(side="right")
        
        # Champ de destination
        self.headset_folder_var = tk.StringVar()
        tk.Entry(headset_frame, textvariable=self.headset_folder_var).pack(fill="x", pady=2)
        
        # Bouton de synchronisation
        tk.Button(sync_frame, text="Start sync", command=self.start_sync).pack(pady=10)
    
    def scan_devices(self):
        """Scanne les devices connectés"""
        self.log_message("Scanning for connected devices...")
        
        stdout, stderr, returncode = self.run_adb_command(["devices"])
        
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
                    
                    if device_id not in self.devices:
                        self.devices[device_id] = {
                            "nickname": f"Device_{device_id[:8]}",
                            "last_seen": datetime.now().strftime('%Y-%m-%d')
                        }
                    else:
                        self.devices[device_id]["last_seen"] = datetime.now().strftime('%Y-%m-%d')
        
        self.save_devices()
        self.refresh_devices_list()
        self.log_message(f"Found {len(current_devices)} connected device(s)")
    
    def refresh_devices_list(self):
        """Rafraîchit la liste des devices dans l'onglet scan"""
        self.devices_listbox.delete(0, tk.END)
        
        # Vérifier quels devices sont actuellement connectés
        stdout, stderr, returncode = self.run_adb_command(["devices"])
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
        
        # Créer une liste triée par nickname
        sorted_devices = sorted(self.devices.items(), key=lambda x: x[1]["nickname"].lower())
        
        for device_id, info in sorted_devices:
            status = current_devices.get(device_id, "OFFLINE")
            if status == "UNAUTHORIZED":
                status += " (Accept USB debugging on headset)"
            
            display_text = f"{info['nickname']} ({device_id}) - {status} - Last seen: {info['last_seen']}"
            self.devices_listbox.insert(tk.END, display_text)
            
            # Définir les couleurs
            index = self.devices_listbox.size() - 1
            if status.startswith("OFFLINE"):
                self.devices_listbox.itemconfig(index, fg="red")
            elif status.startswith("UNAUTHORIZED"):
                self.devices_listbox.itemconfig(index, fg="orange")
            elif status == "DEVICE":
                self.devices_listbox.itemconfig(index, fg="green")
    
    def set_nickname(self):
        """Définit un nickname pour le device sélectionné"""
        selection = self.devices_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a device first")
            return
        
        # Extraire l'ID du device de la sélection
        item_text = self.devices_listbox.get(selection[0])
        device_id = item_text.split('(')[1].split(')')[0]
        
        current_nickname = self.devices[device_id]["nickname"]
        new_nickname = simpledialog.askstring("Set nickname", f"Enter nickname for device {device_id}:", initialvalue=current_nickname)
        
        if new_nickname:
            self.devices[device_id]["nickname"] = new_nickname
            self.save_devices()
            self.refresh_devices_list()
            self.log_message(f"Device {device_id} renamed to '{new_nickname}'")
    
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
        
        # Obtenir les devices connectés
        stdout, stderr, returncode = self.run_adb_command(["devices"])
        
        if returncode != 0:
            self.log_message(f"Error getting devices: {stderr}")
            return
        
        lines = stdout.strip().split('\n')[1:]
        
        for line in lines:
            if '\tdevice' in line or '\tunauthorized' in line or '\toffline' in line:
                parts = line.split('\t')
                if len(parts) >= 2:
                    device_id = parts[0]
                    status = parts[1]
                    nickname = self.devices.get(device_id, {}).get("nickname", f"Device_{device_id[:8]}")
                    
                    var = tk.BooleanVar()
                    status_text = f" - {status.upper()}" if status != "device" else ""
                    checkbox = tk.Checkbutton(self.install_devices_frame, 
                                            text=f"{nickname} ({device_id}){status_text}", 
                                            variable=var,
                                            state="disabled" if status != "device" else "normal")
                    checkbox.pack(anchor="w")
                    
                    if status == "device":
                        self.device_checkboxes[device_id] = var
    
    def select_all_devices(self):
        """Sélectionne tous les devices"""
        for var in self.device_checkboxes.values():
            var.set(True)
    
    def deselect_all_devices(self):
        """Désélectionne tous les devices"""
        for var in self.device_checkboxes.values():
            var.set(False)
    
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
        """Thread pour l'installation des APK"""
        apk_files = [self.apk_listbox.get(i) for i in range(self.apk_listbox.size())]
        
        total_operations = len(apk_files) * len(selected_devices)
        current_operation = 0
        
        for device_id in selected_devices:
            device_name = self.devices.get(device_id, {}).get("nickname", device_id)
            self.log_message(f"Starting installation on {device_name}")
            
            for apk_file in apk_files:
                current_operation += 1
                apk_name = os.path.basename(apk_file)
                self.log_message(f"[{current_operation}/{total_operations}] Installing {apk_name} on {device_name}...")
                
                stdout, stderr, returncode = self.run_adb_command(["install", apk_file], device_id)
                
                if returncode == 0:
                    self.log_message(f"✓ {apk_name} installed successfully on {device_name}")
                else:
                    self.log_message(f"✗ Failed to install {apk_name} on {device_name}: {stderr}")
        
        self.log_message("Installation process completed!")
    
    def scan_missing_apks(self):
        """Scanne tous les devices pour les packages installés"""
        self.log_message("Scanning all devices for installed packages...")
        
        # Nettoyer le tableau
        self.missing_tree.delete(*self.missing_tree.get_children())
        self.all_packages_data = []
        
        # Obtenir les devices connectés
        stdout, stderr, returncode = self.run_adb_command(["devices"])
        
        if returncode != 0:
            self.log_message(f"Error getting devices: {stderr}")
            return
        
        lines = stdout.strip().split('\n')[1:]
        connected_devices = []
        
        for line in lines:
            if '\tdevice' in line:  # Seulement les devices autorisés
                device_id = line.split('\t')[0]
                connected_devices.append(device_id)
        
        if not connected_devices:
            self.log_message("No connected devices found")
            return
        
        # Scanner les packages de chaque device
        all_packages = set()
        device_packages = {}
        
        for device_id in connected_devices:
            device_name = self.devices.get(device_id, {}).get("nickname", device_id)
            self.log_message(f"Scanning packages on {device_name}...")
            
            stdout, stderr, returncode = self.run_adb_command(["shell", "pm", "list", "packages"], device_id)
            
            if returncode == 0:
                packages = [line.replace("package:", "") for line in stdout.strip().split('\n') if line.startswith("package:")]
                device_packages[device_id] = set(packages)
                all_packages.update(packages)
            else:
                self.log_message(f"Error scanning {device_name}: {stderr}")
                device_packages[device_id] = set()
        
        # Créer les colonnes du tableau
        columns = ["Package"] + [self.devices.get(device_id, {}).get("nickname", device_id) for device_id in connected_devices]
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
        stdout, stderr, returncode = self.run_adb_command(["devices"])
        
        devices = []
        if returncode == 0:
            lines = stdout.strip().split('\n')[1:]
            for line in lines:
                if '\tdevice' in line:  # Only show authorized devices for uninstall
                    device_id = line.split('\t')[0]
                    nickname = self.devices.get(device_id, {}).get("nickname", device_id)
                    devices.append(f"{nickname} ({device_id})")
        
        self.uninstall_device_combo["values"] = devices
        if devices:
            self.uninstall_device_combo.current(0)
    
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
    
    def save_sync_paths(self):
        """Sauvegarde les chemins de synchronisation"""
        self.sync_paths["videos"] = self.videos_path_var.get()
        self.sync_paths["photos"] = self.photos_path_var.get()
        self.save_config()
        self.log_message("Default sync paths saved")
    
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
        
        if folder_type == "Default Videos":
            self.headset_folder_var.set(self.sync_paths["videos"])
        elif folder_type == "Default Photos":
            self.headset_folder_var.set(self.sync_paths["photos"])
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
        """Démarre la synchronisation"""
        pc_folder = self.pc_folder_var.get()
        headset_folder = self.headset_folder_var.get()
        
        if not pc_folder or not headset_folder:
            messagebox.showwarning("Warning", "Please specify both PC folder and headset folder")
            return
        
        if not os.path.exists(pc_folder):
            messagebox.showerror("Error", "PC folder does not exist")
            return
        
        # Obtenir les devices connectés
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
            messagebox.showerror("Error", "No connected devices found")
            return
        
        if not messagebox.askyesno("Confirm sync", 
                                 f"Sync {pc_folder} to {headset_folder} on {len(connected_devices)} device(s)?"):
            return
        
        # Réinitialiser les options globales
        self.apply_to_all_devices = False
        self.apply_to_all_files = False
        
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
                
                # Créer le dossier de destination si nécessaire
                remote_dir = '/'.join(remote_path.split('/')[:-1])
                self.run_adb_command(["shell", "mkdir", "-p", remote_dir], device_id)
                
                # Copier le fichier
                stdout, stderr, returncode = self.run_adb_command(["push", local_path, remote_path], device_id)
                
                if returncode == 0:
                    self.log_message(f"✓ {relative_path} -> {device_name}")
                else:
                    self.log_message(f"✗ Failed to copy {relative_path} to {device_name}: {stderr}")
        
        self.log_message("Sync completed!")
    
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
    
    def run(self):
        """Lance l'application"""
        self.log_message("USB VR Manager started")
        self.log_message(f"ADB path: {self.adb_path}")
        self.root.mainloop()

if __name__ == "__main__":
    app = USBVRManager()
    app.run()