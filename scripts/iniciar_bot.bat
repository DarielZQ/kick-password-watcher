@echo off
REM Arranca kick-password-watcher. Cierra esta ventana o pulsa Ctrl+C para detenerlo.
REM Usa uv si está instalado; si no, el entorno .venv que crea instalar.ps1 con venv + pip.
cd /d "%~dp0.."
where uv >nul 2>&1
if not errorlevel 1 (
    uv run kick-password-watcher run
) else if exist ".venv\Scripts\kick-password-watcher.exe" (
    ".venv\Scripts\kick-password-watcher.exe" run
) else (
    echo Falta instalar el bot: ejecuta primero instalar.bat en la carpeta del proyecto.
)
pause
