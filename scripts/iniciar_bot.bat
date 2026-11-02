@echo off
REM Arranca kick-password-watcher. Cierra esta ventana o pulsa Ctrl+C para detenerlo.
cd /d "%~dp0.."
uv run kick-password-watcher run
pause
