@echo off
chcp 65001 >nul
setlocal

set "SCRIPT_DIR=%~dp0"
set "PYTHON_PORTABLE=%SCRIPT_DIR%python\python.exe"
set "SCRIPT=%SCRIPT_DIR%VR-Casting-Manager.py"

:: Vérifier si le script existe
if not exist "%SCRIPT%" (
    echo [ERREUR] Script non trouve: %SCRIPT%
    pause
    exit /b 1
)

:: Essayer Python portable d'abord
if exist "%PYTHON_PORTABLE%" (
    echo Lancement avec Python portable...
    cd /d "%SCRIPT_DIR%"
    "%PYTHON_PORTABLE%" "%SCRIPT%"
    goto :end
)

:: Sinon essayer Python système
where python >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo Lancement avec Python systeme...
    cd /d "%SCRIPT_DIR%"
    python "%SCRIPT%"
    goto :end
)

:: Aucun Python trouvé
echo.
echo [ERREUR] Python non trouve!
echo.
echo Solutions:
echo 1. Executez setup_portable.bat pour installer Python portable
echo 2. Ou installez Python depuis https://www.python.org/downloads/
echo.
pause
exit /b 1

:end
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [!] Le programme s'est termine avec une erreur.
    pause
)
