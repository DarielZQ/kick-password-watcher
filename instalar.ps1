# Instalador de kick-password-watcher para Windows.
#
# Uso (desde la carpeta del proyecto):
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\instalar.ps1
#   o doble clic en instalar.bat
#
# Opciones:
#   -AccesoDirecto      crea el acceso directo en el Escritorio sin preguntar
#   -SinAccesoDirecto   no crea el acceso directo ni pregunta
#
# Se puede ejecutar las veces que haga falta: reutiliza el entorno, no sobrescribe
# config\local.yaml y actualiza el acceso directo si ya existe. No instala Python, uv
# ni nada del sistema: si falta algo, explica cómo instalarlo y se detiene.

[CmdletBinding()]
param(
    [switch]$AccesoDirecto,
    [switch]$SinAccesoDirecto
)

$ErrorActionPreference = "Stop"
$Raiz = $PSScriptRoot
$PythonMinimo = [version]"3.12"

function Paso([string]$Texto) { Write-Host ""; Write-Host "==> $Texto" -ForegroundColor Cyan }
function Ok([string]$Texto) { Write-Host "    $Texto" -ForegroundColor Green }
function Aviso([string]$Texto) { Write-Host "    $Texto" -ForegroundColor Yellow }
function Falla([string[]]$Lineas) {
    Write-Host ""
    foreach ($l in $Lineas) { Write-Host $l -ForegroundColor Red }
    exit 1
}

# Devuelve la versión de un intérprete de Python o $null si no responde.
function VersionDePython([string]$Exe, [string[]]$Argumentos) {
    try {
        $salida = & $Exe @Argumentos -c "import sys; print('%d.%d.%d' % sys.version_info[:3])" 2>$null
        if ($LASTEXITCODE -eq 0 -and $salida -match '^\d+\.\d+\.\d+$') { return [version]$salida }
    } catch { }
    return $null
}

# ---------------------------------------------------------------------------
Paso "Comprobando el sistema"

if ([System.Environment]::OSVersion.Platform -ne [System.PlatformID]::Win32NT) {
    Falla @("Este bot solo funciona en Windows 10/11: usa el OCR, las notificaciones y el",
            "sonido de Windows.")
}
Ok "Windows $([System.Environment]::OSVersion.Version)"

if ($PSVersionTable.PSVersion -lt [version]"5.1") {
    Falla @("Hace falta PowerShell 5.1 o superior (tienes $($PSVersionTable.PSVersion)).",
            "Windows 10/11 ya trae Windows PowerShell 5.1; también sirve PowerShell 7:",
            "  winget install --id Microsoft.PowerShell -e")
}
Ok "PowerShell $($PSVersionTable.PSVersion)"

$uv = Get-Command uv -ErrorAction SilentlyContinue
$python = $null
if ($uv) {
    Ok "uv encontrado: $($uv.Source)"
} else {
    Aviso "No se encontró uv; se buscará Python $PythonMinimo o superior para usar venv + pip."
    $candidatos = @(
        @{ Exe = "py"; Args = @("-3.12") },
        @{ Exe = "py"; Args = @("-3") },
        @{ Exe = "python"; Args = @() }
    )
    foreach ($c in $candidatos) {
        if (-not (Get-Command $c.Exe -ErrorAction SilentlyContinue)) { continue }
        $v = VersionDePython $c.Exe $c.Args
        if ($v -and $v -ge $PythonMinimo) { $python = $c; Ok "Python $v ($($c.Exe) $($c.Args -join ' '))"; break }
    }
    if (-not $python) {
        Falla @("No se encontró uv ni Python $PythonMinimo o superior. Instala uno de los dos y vuelve a",
                "ejecutar este instalador:",
                "",
                "  Opción recomendada, uv (gestiona Python y las dependencias):",
                "    winget install --id astral-sh.uv -e",
                "    o sigue https://docs.astral.sh/uv/getting-started/installation/",
                "",
                "  Opción alternativa, Python 3.12 o superior:",
                "    winget install --id Python.Python.3.12 -e",
                "    o descárgalo de https://www.python.org/downloads/windows/",
                "",
                "Después cierra y abre de nuevo la consola para que se actualice el PATH.")
    }
}

# Aviso (no bloqueante): el OCR necesita un idioma español instalado en Windows.
try {
    $null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
    $idiomas = @([Windows.Media.Ocr.OcrEngine]::AvailableRecognizerLanguages | ForEach-Object { $_.LanguageTag })
    if ($idiomas | Where-Object { $_ -like "es*" }) {
        Ok "OCR de Windows en español disponible ($((@($idiomas | Where-Object { $_ -like 'es*' })) -join ', '))"
    } else {
        Aviso "No hay un idioma OCR español instalado; sin él no se leen bien tildes ni ñ."
        Aviso "Configuración > Hora e idioma > Idioma > Español > Opciones > Reconocimiento óptico de caracteres."
    }
} catch {
    Aviso "No se pudo comprobar el idioma OCR de Windows desde esta consola (se revisa al arrancar el bot)."
}

# ---------------------------------------------------------------------------
Push-Location $Raiz
try {
    if ($uv) {
        Paso "Instalando dependencias con uv sync"
        Aviso "uv descarga Python 3.12 por su cuenta si no lo tienes (ver .python-version)."
        & uv sync
        if ($LASTEXITCODE -ne 0) { Falla @("uv sync terminó con error ($LASTEXITCODE). Revisa el mensaje anterior.") }
        Ok "Entorno listo en .venv"
    } else {
        Paso "Instalando dependencias con venv + pip"
        $venvPython = Join-Path $Raiz ".venv\Scripts\python.exe"
        if (Test-Path $venvPython) {
            Ok "Se reutiliza el entorno existente .venv"
        } else {
            & $python.Exe @($python.Args) -m venv .venv
            if ($LASTEXITCODE -ne 0) { Falla @("No se pudo crear el entorno virtual .venv.") }
            Ok "Creado el entorno virtual .venv"
        }
        & $venvPython -m pip install --upgrade pip
        if ($LASTEXITCODE -ne 0) { Falla @("No se pudo actualizar pip dentro de .venv.") }
        # Proyecto en modo editable (lee config\ desde la carpeta del proyecto) y grupo dev (pytest).
        & $venvPython -m pip install -e . --group dev
        if ($LASTEXITCODE -ne 0) { Falla @("pip install terminó con error ($LASTEXITCODE). Revisa el mensaje anterior.") }
        Ok "Dependencias instaladas en .venv"
    }

    # -----------------------------------------------------------------------
    Paso "Configuración local"
    $local = Join-Path $Raiz "config\local.yaml"
    $ejemplo = Join-Path $Raiz "config\local.example.yaml"
    if (Test-Path $local) {
        Ok "config\local.yaml ya existe: no se toca."
    } elseif (Test-Path $ejemplo) {
        Copy-Item $ejemplo $local
        Ok "Creado config\local.yaml a partir de config\local.example.yaml."
        Aviso "Edítalo y rellena source.urls y output.discord_webhook_url antes de arrancar el bot."
    } else {
        Aviso "No se encontró config\local.example.yaml; crea config\local.yaml a mano (ver README)."
    }

    # -----------------------------------------------------------------------
    Paso "Acceso directo en el Escritorio"
    $crear = $false
    if ($AccesoDirecto) {
        $crear = $true
    } elseif (-not $SinAccesoDirecto) {
        try {
            $respuesta = Read-Host "    ¿Crear un acceso directo 'Kick Password Watcher' en el Escritorio? [s/N]"
            $crear = $respuesta -match '^(s|si|sí|y|yes)$'
        } catch {
            Aviso "Consola no interactiva: no se crea el acceso directo (usa -AccesoDirecto)."
        }
    }
    if ($crear) {
        $escritorio = [Environment]::GetFolderPath("Desktop")
        $enlace = Join-Path $escritorio "Kick Password Watcher.lnk"
        $existia = Test-Path $enlace
        $shell = New-Object -ComObject WScript.Shell
        $atajo = $shell.CreateShortcut($enlace)
        $atajo.TargetPath = Join-Path $Raiz "scripts\iniciar_bot.bat"
        $atajo.WorkingDirectory = $Raiz
        $atajo.Description = "Arranca kick-password-watcher"
        $atajo.Save()
        if ($existia) { Ok "Acceso directo actualizado en el Escritorio." } else { Ok "Acceso directo creado en el Escritorio." }
    } else {
        Ok "Sin acceso directo. Puedes arrancar el bot con scripts\iniciar_bot.bat."
    }
} finally {
    Pop-Location
}

# ---------------------------------------------------------------------------
Paso "Listo"
if ($uv) {
    Write-Host "    Probar la salida:  uv run kick-password-watcher test-output prueba"
    Write-Host "    Arrancar el bot:   uv run kick-password-watcher run"
} else {
    Write-Host "    Probar la salida:  .venv\Scripts\kick-password-watcher test-output prueba"
    Write-Host "    Arrancar el bot:   .venv\Scripts\kick-password-watcher run"
}
Write-Host "    O doble clic en scripts\iniciar_bot.bat (o en el acceso directo)."
