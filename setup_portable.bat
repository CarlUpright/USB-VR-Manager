@echo off
chcp 65001 >nul
setlocal

echo ============================================
echo   USB-VR-Manager - Verification Portable
echo ============================================
echo.

set "SCRIPT_DIR=%~dp0"
set "PYTHON_DIR=%SCRIPT_DIR%python"

:: Vérifier si Python portable existe
if not exist "%PYTHON_DIR%\python.exe" (
    echo [ERREUR] Python portable non trouve dans le dossier "python"
    echo.
    echo Ce package portable necessite le dossier "python" avec Python 3.13.
    echo Assurez-vous d'avoir copie le dossier complet.
    echo.
    pause
    exit /b 1
)

:: Vérifier tkinter
"%PYTHON_DIR%\python.exe" -c "import tkinter" 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERREUR] Tkinter non disponible.
    echo.
    echo Le module tkinter est manquant ou incomplet.
    echo Assurez-vous d'avoir copie les dossiers: tcl, Lib\tkinter, DLLs
    echo.
    pause
    exit /b 1
)

echo [OK] Python 3.13 portable detecte
echo [OK] Tkinter fonctionne correctement
echo.

:: Vérifier les scripts
if exist "%SCRIPT_DIR%USB-VR-Manager.py" (
    echo [OK] USB-VR-Manager.py present
) else (
    echo [!] USB-VR-Manager.py manquant
)

if exist "%SCRIPT_DIR%VR-Casting-Manager.py" (
    echo [OK] VR-Casting-Manager.py present
) else (
    echo [!] VR-Casting-Manager.py manquant
)

:: Vérifier scrcpy
if exist "%SCRIPT_DIR%scrcpy-win64-v3.3.1-quest3-fix\scrcpy.exe" (
    echo [OK] scrcpy detecte
) else (
    echo [!] scrcpy non trouve (optionnel, pour le casting)
)

echo.
echo ============================================
echo   Tout est pret!
echo ============================================
echo.
echo Double-cliquez sur:
echo   - Lancer_USB-VR-Manager.bat
echo   - Lancer_VR-Casting-Manager.bat
echo.
pause
