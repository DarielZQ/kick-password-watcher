@echo off
REM Instala kick-password-watcher: comprueba requisitos, instala dependencias y crea config\local.yaml.
REM Se puede ejecutar varias veces sin riesgo. Opciones: -AccesoDirecto o -SinAccesoDirecto
cd /d "%~dp0"
where powershell >nul 2>&1
if errorlevel 1 (
    echo No se encuentra Windows PowerShell ^(powershell.exe^). Viene incluido en Windows 10/11:
    echo revisa que la variable PATH incluya %%SystemRoot%%\System32\WindowsPowerShell\v1.0
    pause
    exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0instalar.ps1" %*
set "CODIGO=%ERRORLEVEL%"
echo.
pause
exit /b %CODIGO%
