# USB-VR-Manager

**USB-VR-Manager** est un outil de gestion centralisée pour plusieurs casques Meta Quest (Quest 1, Quest 2, Quest 3 et futurs modèles). Il permet de gérer facilement l'installation d'APK, la synchronisation de fichiers, et la maintenance de multiples casques VR depuis un seul ordinateur.

## 🎯 Fonctionnalités principales

- **Gestion multi-casques** : Connectez et gérez jusqu'à 10+ casques simultanément
- **Installation d'APK** : Installation en lot sur plusieurs casques sélectionnés
- **Synchronisation de fichiers** : Système intelligent de sync PC ↔ Casques avec résolution de conflits
- **Audit des packages** : Comparaison des applications installées entre casques
- **Désinstallation sécurisée** : Protection contre la suppression d'apps système critiques
- **Interface graphique intuitive** : Onglets organisés pour chaque fonction

## 📋 Prérequis

### Logiciels requis
- **Windows 10/11**
- **Python 3.7+** ([Télécharger ici](https://www.python.org/downloads/))
- **SideQuest** installé ou une instance de adb.exe ([sidequestvr.com](https://sidequestvr.com/))

### Configuration des casques
- **Mode développeur activé** sur chaque casque
- **Débogage USB autorisé** 
- **Câbles USB de qualité** (éviter les câbles charge seule)

### Installation
1. Téléchargez le script `USB-VR-Manager.py`
2. Placez-le dans un dossier dédié
3. Exécutez : `python USB-VR-Manager.py`

*Aucune installation de dépendances supplémentaire requise - utilise uniquement les bibliothèques Python standard.*

## 🚀 Guide d'utilisation

### 🔍 **Onglet 1 : Scan for devices**

**Objectif :** Détecter et gérer les casques connectés

1. **Connectez vos casques** via USB
2. Cliquez **"Scan for connected devices"**
3. **Autorisez le débogage USB** sur chaque casque (popup sur l'écran VR)
4. Les casques apparaissent avec **codes couleur** :
   - 🟢 **Vert** : Connecté et autorisé
   - 🟠 **Orange** : Connecté mais non autorisé
   - 🔴 **Rouge** : Hors ligne

**Gestion des nicknames :**
- Sélectionnez un casque → **"Set nickname"**
- Utilisez des noms explicites : "Casque Bureau", "Quest Salle A", etc.

---

### 📱 **Onglet 2 : Install APK**

**Objectif :** Installer des applications sur plusieurs casques

1. **Ajoutez des APK** : Cliquez "Add APK files" et sélectionnez vos fichiers
2. **Sélectionnez les casques cibles** : Cochez les casques voulus
   - Boutons **"Select all"** / **"Deselect all"** pour gagner du temps
3. **Lancez l'installation** : Cliquez "Install APKs"

⚠️ **Important :** Ne débranchez JAMAIS les casques pendant l'installation !

**Logs en temps réel :** Suivez la progression dans la zone de logs en bas

---

### 📊 **Onglet 3 : Scan for missing APKs**

**Objectif :** Comparer les applications installées entre casques

1. **Scannez tous les casques** : "Scan all devices for installed packages"
2. **Analysez le tableau** : 
   - Colonne par casque
   - ✓ = Application installée
   - Vide = Application manquante
3. **Filtrage intelligent** : Cochez "Show missing packages only" pour voir uniquement les incohérences

**Cas d'usage :** Vérifier que tous les casques d'un événement ont les mêmes apps installées

---

### 🗑️ **Onglet 4 : Uninstall APK**

**Objectif :** Désinstaller des applications de manière sécurisée

1. **Sélectionnez un casque** dans la liste déroulante
2. **Chargez les packages** : "Load packages"
3. **Filtrage sécurisé** : Les apps système sont cachées par défaut
   - Cochez "Show system apps" pour les voir (⚠️ **Dangereux !**)
4. **Désinstallez** :
   - **Un casque** : "Uninstall from selected device"
   - **Tous les casques** : "Uninstall from ALL devices"

**Protection système :** Avertissement rouge pour les apps système critiques

---

### 📁 **Onglet 5 : Sync folder**

**Objectif :** Synchroniser des fichiers entre PC et casques avec gestion intelligente des conflits

#### Configuration initiale
1. **Définissez les chemins par défaut** :
   - Videos : `/sdcard/Movies/` (modifiable)
   - Photos : `/sdcard/Pictures/` (modifiable)
2. **Sauvegardez** : "Save default paths"

#### Synchronisation
1. **Dossier PC** : Sélectionnez ou naviguez vers votre dossier source
2. **Dossier casque** : Choisissez via dropdown :
   - "Default Videos" → Utilise le chemin vidéos configuré
   - "Default Photos" → Utilise le chemin photos configuré  
   - "Custom" → Saisissez un chemin personnalisé
3. **Lancez l'analyse** : "Start sync"

#### Système de résolution de conflits (🆕 **Nouveau !**)

**Phase 1 - Analyse :**
- Scanne PC et tous les casques
- Ignore automatiquement les fichiers cachés (`.DS_Store`, `.thumbs.db`, etc.)
- Détecte tous les conflits avant de commencer

**Phase 2 - Résolution :**
Interface de conflit avec tableau interactif :

| File | Conflict Type | Devices Affected | Action |
|------|---------------|------------------|---------|
| video.mp4 | overwrite | Casque A, Casque B | overwrite |
| photo.jpg | delete | Casque C | keep |

**Actions possibles :**
- **Overwrite** : Écraser le fichier existant
- **Skip** : Ignorer ce fichier  
- **Rename** : Renommer avec timestamp
- **Delete** : Supprimer du casque
- **Keep** : Conserver sur le casque

**Boutons d'action rapide :**
- "Overwrite all existing files"
- "Skip all existing files"  
- "Delete all orphaned files"
- "Keep all orphaned files"

**Modification individuelle :** Double-clic sur une ligne pour changer l'action

**Phase 3 - Exécution :**
Synchronisation automatique selon le plan défini, avec logs détaillés et compteur de progression.

## 📁 Structure des fichiers

Le script crée automatiquement :

```
USB-VR-Manager.py          # Script principal
devices.csv              # Liste des casques et nicknames
config.csv               # Configuration des chemins de sync
```

### Format devices.csv
```csv
DEVICE_ID,Nickname,Last_seen
2G0YC5ZG03027G,Casque Bureau,2025-06-18
3H1ZD6AH04138H,Quest Salon,2025-06-17
```

### Format config.csv  
```csv
videos,/sdcard/Movies/
photos,/sdcard/Pictures/
others,
last_pc_folder,C:\Users\username\Videos
```

## 🔧 Fonctionnalités avancées

### Gestion intelligente ADB
- **Détection automatique** du chemin SideQuest
- **Fallback manuel** si SideQuest non trouvé
- **Gestion des timeouts** et erreurs de connexion

### Sécurité
- **Détection apps système** via `dumpsys package`
- **Avertissements explicites** pour les actions dangereuses
- **Confirmation multiple** pour les suppressions en masse

### Performance
- **Threading intelligent** pour éviter le freeze de l'interface
- **Gestion de plusieurs casques** en parallèle ou séquentiel selon l'opération
- **Logs temps réel** avec horodatage

### Filtrage automatique
- **Fichiers cachés** ignorés automatiquement (commençant par `.`)
- **Apps système** cachées par défaut dans la désinstallation
- **Packages manquants** filtrables dans l'audit

## 🚨 Dépannage

### Casque non détecté
1. **Vérifiez le câble USB** (certains ne font que la charge)
2. **Autorisez le débogage USB** sur le casque (popup VR)
3. **Redémarrez ADB** : `adb kill-server` puis `adb start-server`
4. **Changez de port USB** ou utilisez un hub alimenté

### "unauthorized" persistant
1. **Révocation** : Paramètres → Développeur → Révoquer autorisations USB
2. **Reconnectez** le casque
3. **Acceptez à nouveau** l'autorisation de débogage

### Installation APK échoue
1. **Vérifiez l'espace libre** sur le casque
2. **APK compatibles** avec la version Quest
3. **Sources inconnues activées** dans les paramètres

### Sync lente ou échoue
1. **Casques non branchés** pendant l'opération
2. **Câbles USB de qualité** requise
3. **Fermer autres apps** utilisant ADB (SideQuest)
4. **Vérifier permissions** dossiers de destination

### Erreur "ADB not found"
1. **Réinstallez SideQuest** 
2. **Sélectionnez manuellement** `adb.exe` quand demandé
3. **Chemin type** : `C:\Users\[USERNAME]\AppData\Local\Programs\SideQuest\...\adb.exe`

## 💡 Conseils d'utilisation

### Workflow recommandé pour événements
1. **Préparez les casques** : Mode dev + débogage activés
2. **Scannez et renommez** tous les casques avec des noms logiques
3. **Installez les APK** requis sur tous les casques
4. **Vérifiez avec l'audit** que toutes les apps sont présentes
5. **Synchronisez le contenu** (vidéos, photos, fichiers)

### Gestion de flotte importante (10+ casques)
- **Hubs USB alimentés** recommandés
- **Installation séquentielle** plus stable que parallèle
- **Tests par petits groupes** avant déploiement complet
- **Câbles identiques** pour éviter les problèmes de compatibilité

### Bonnes pratiques
- **Sauvegardez régulièrement** `devices.csv` et `config.csv`
- **Nommage cohérent** des casques (lieu, numéro, usage)
- **Testez toujours** sur un casque avant déploiement masse
- **Surveillez les logs** pour détecter les problèmes rapidement

## 📋 Limitations connues

- **Windows uniquement** (dépendance chemin SideQuest)
- **Casques Meta Quest** seulement (utilise ADB Android)
- **Navigation casque limitée** (pas d'explorateur intégré)
- **Threading simple** (pas de pool de workers avancé)

## 🔮 Améliorations futures possibles

- Support Linux/macOS
- Interface web pour accès distant
- Sauvegarde/restauration complète de casques
- Déploiement d'apps par profils/groupes
- Monitoring de l'état des casques en temps réel
- API REST pour intégration dans d'autres systèmes

---

**Développé pour la gestion efficace de flottes de casques Meta Quest**
*Compatible : Quest 1, Quest 2, Quest 3, et modèles futurs*
