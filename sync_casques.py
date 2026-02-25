"""
Script de synchronisation de fichiers vers casques VR
Copie un dossier du PC vers plusieurs casques VR connectés via USB
"""

import subprocess
import os
import time
import winsound
import tkinter as tk
from tkinter import filedialog

# Configuration
ADB_PATH = os.path.join(os.path.dirname(__file__), "scrcpy-win64-v3.3.1-quest3-fix", "adb.exe")
DEST_CASQUE = "/sdcard/Download/"

# Sons
def bip_succes():
    """Double bip aigu = succès"""
    winsound.Beep(1000, 200)
    winsound.Beep(1500, 200)

def bip_erreur():
    """Bip grave = erreur"""
    winsound.Beep(400, 500)

def bip_deja_copie():
    """Un seul bip = fichier déjà présent"""
    winsound.Beep(800, 150)

# Fonctions ADB
def get_casques_connectes():
    """Retourne la liste des IDs des casques connectés via USB"""
    result = subprocess.run([ADB_PATH, "devices"], capture_output=True, text=True)
    casques = []
    for line in result.stdout.strip().split('\n')[1:]:
        if '\tdevice' in line and not line.startswith('192.'):  # Exclure les connexions WiFi
            device_id = line.split('\t')[0]
            casques.append(device_id)
    return casques

def fichier_existe_sur_casque(device_id, fichier_distant):
    """Vérifie si un fichier existe sur le casque"""
    result = subprocess.run(
        [ADB_PATH, "-s", device_id, "shell", f"ls \"{fichier_distant}\" 2>/dev/null && echo EXISTE"],
        capture_output=True, text=True
    )
    return "EXISTE" in result.stdout

def copier_fichier_avec_progression(device_id, source_locale, dest_distante, taille_fichier):
    """Copie un fichier vers le casque avec barre de progression"""
    import re

    process = subprocess.Popen(
        [ADB_PATH, "-s", device_id, "push", source_locale, dest_distante],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    # Lire la sortie caractère par caractère pour capturer la progression
    output = ""
    while True:
        char = process.stdout.read(1)
        if not char:
            break

        char = char.decode('utf-8', errors='ignore')
        output += char

        # Chercher le pourcentage dans la sortie (format: "45%" ou "100%")
        if '%' in output:
            match = re.search(r'(\d+)%', output)
            if match:
                pct = int(match.group(1))
                bar_width = 30
                filled = int(bar_width * pct / 100)
                bar = '█' * filled + '░' * (bar_width - filled)
                print(f"\r    [{bar}] {pct}%", end="", flush=True)

        # Reset si retour chariot
        if char == '\r' or char == '\n':
            output = ""

    process.wait()
    print("\r" + " " * 50 + "\r", end="")  # Effacer la ligne
    return process.returncode == 0

def get_taille_fichier_casque(device_id, fichier_distant):
    """Retourne la taille d'un fichier sur le casque"""
    result = subprocess.run(
        [ADB_PATH, "-s", device_id, "shell", f"stat -c %s \"{fichier_distant}\" 2>/dev/null"],
        capture_output=True, text=True
    )
    try:
        return int(result.stdout.strip())
    except:
        return -1

def selectionner_dossier():
    """Ouvre une fenêtre pour sélectionner le dossier source"""
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    dossier = filedialog.askdirectory(title="Sélectionner le dossier à synchroniser")
    root.destroy()
    return dossier

def main():
    print("=" * 50)
    print("  SYNCHRONISATION CASQUES VR")
    print("=" * 50)

    # Étape 1: Sélectionner le dossier source
    print("\n[1] Sélection du dossier source...")
    dossier_source = selectionner_dossier()

    if not dossier_source:
        print("Aucun dossier sélectionné. Abandon.")
        return

    print(f"    Dossier: {dossier_source}")

    # Lister les fichiers à copier (récursivement)
    fichiers = []
    nom_dossier_base = os.path.basename(dossier_source)

    for racine, dossiers, noms_fichiers in os.walk(dossier_source):
        for nom in noms_fichiers:
            chemin_complet = os.path.join(racine, nom)
            # Chemin relatif pour conserver la structure
            chemin_relatif = os.path.relpath(chemin_complet, dossier_source)
            taille = os.path.getsize(chemin_complet)
            fichiers.append((chemin_relatif, chemin_complet, taille))

    if not fichiers:
        print("Aucun fichier trouvé dans le dossier. Abandon.")
        return

    taille_totale = sum(t for _, _, t in fichiers)
    print(f"    {len(fichiers)} fichier(s) à synchroniser ({taille_totale / 1024 / 1024 / 1024:.2f} GB):")
    for chemin_rel, _, taille in fichiers:
        print(f"      - {chemin_rel} ({taille / 1024 / 1024:.1f} MB)")

    # Suivi des casques traités
    casques_traites = set()

    print("\n[2] En attente de casques VR...")
    print("    (Branchez un casque USB - Ctrl+C pour quitter)\n")

    try:
        while True:
            casques = get_casques_connectes()

            for device_id in casques:
                if device_id in casques_traites:
                    continue

                print(f"\n>>> Casque détecté: {device_id}")
                casque_ok = True

                # Étape 2: Vérifier tous les fichiers d'abord
                print("    Analyse des fichiers...")
                fichiers_a_copier = []

                for chemin_relatif, chemin_local, taille_locale in fichiers:
                    chemin_distant = DEST_CASQUE + nom_dossier_base + "/" + chemin_relatif.replace("\\", "/")
                    dossier_distant = "/".join(chemin_distant.rsplit("/", 1)[:-1])

                    if fichier_existe_sur_casque(device_id, chemin_distant):
                        taille_distante = get_taille_fichier_casque(device_id, chemin_distant)
                        if taille_distante == taille_locale:
                            continue  # Fichier déjà présent, on passe

                    fichiers_a_copier.append((chemin_relatif, chemin_local, taille_locale, chemin_distant, dossier_distant))

                print(f"    {len(fichiers_a_copier)} fichier(s) à copier / {len(fichiers)} fichier(s) total")

                if len(fichiers_a_copier) == 0:
                    print("    Tous les fichiers sont déjà présents!")
                    bip_deja_copie()
                    casques_traites.add(device_id)
                    print("\n" + "-" * 40)
                    print("Débranchez ce casque et branchez le suivant...")
                    continue

                # Étape 3: Copier les fichiers manquants
                fichiers_copies = 0
                for idx, (chemin_relatif, chemin_local, taille_locale, chemin_distant, dossier_distant) in enumerate(fichiers_a_copier):
                    nom_fichier = os.path.basename(chemin_relatif)
                    print(f"\n    [{idx + 1}/{len(fichiers_a_copier)}] {nom_fichier}")

                    # Créer le dossier distant si nécessaire
                    subprocess.run(
                        [ADB_PATH, "-s", device_id, "shell", f"mkdir -p \"{dossier_distant}\""],
                        capture_output=True
                    )

                    # Copier avec progression
                    if copier_fichier_avec_progression(device_id, chemin_local, chemin_distant, taille_locale):
                        # Vérifier la copie
                        taille_copiee = get_taille_fichier_casque(device_id, chemin_distant)
                        if taille_copiee == taille_locale:
                            print(f"    OK ({taille_locale / 1024 / 1024:.1f} MB)")
                            fichiers_copies += 1
                        else:
                            print("    ERREUR DE VÉRIFICATION!")
                            casque_ok = False
                    else:
                        print("    ERREUR DE COPIE!")
                        casque_ok = False

                # Étape 4: Son de confirmation
                casques_traites.add(device_id)

                if not casque_ok:
                    print(f"\n    ERREUR sur ce casque!")
                    bip_erreur()
                else:
                    print(f"\n    TERMINÉ! {fichiers_copies} fichier(s) copié(s)")
                    bip_succes()

                print("\n" + "-" * 40)
                print("Débranchez ce casque et branchez le suivant...")

            # Étape 6: Attendre le prochain casque
            time.sleep(1)

    except KeyboardInterrupt:
        print(f"\n\nArrêt demandé. {len(casques_traites)} casque(s) traité(s).")

if __name__ == "__main__":
    main()
