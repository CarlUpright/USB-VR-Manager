# USB-VR-Manager
A USB content manager for multiple VR headsets

Fonctionnalités incluses :
1. Scan for devices

Détecte automatiquement les casques connectés
Sauvegarde les IDs et nicknames dans devices.csv
Permet de renommer les casques
Affiche le statut (connecté/hors ligne)

2. Install APK

Sélection multiple d'APK
Sélection des casques cibles avec boutons "Select all"/"Deselect all"
Installation séquentielle avec logs détaillés
Message d'avertissement

3. Scan for missing APKs

Tableau comparatif avec colonnes par casque
Crochets (✓) pour indiquer la présence des packages
Liste tous les packages uniques trouvés

4. Uninstall APK

Sélection d'un casque pour voir ses packages
Désinstallation d'un casque spécifique ou de tous
Threading pour éviter le blocage de l'interface

5. Sync folder

Configuration des chemins par défaut modifiables
Synchronisation PC → casques
Options "apply to all" pour automatiser les décisions
Sauvegarde des chemins dans config.csv

Pour utiliser le script :

Sauvegardez le code dans un fichier .py
Installez Python si nécessaire
Lancez le script : python quest_manager.py

Le script va automatiquement :

Chercher ADB dans SideQuest
Créer les fichiers devices.csv et config.csv
Afficher l'interface avec les 5 onglets
