param(
    [string]$PythonExe = "",
    [string]$VenvPath = ".venv",
    [switch]$SkipOptional,
    [switch]$SkipPlaywrightBrowsers,
    [switch]$SkipSpacyModels,
    [switch]$SkipDbInit
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Test-PythonVersion {
    param([string]$Executable)
    try {
        $version = & $Executable -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"
        if ($LASTEXITCODE -ne 0 -or -not $version) {
            return $null
        }
        return $version.Trim()
    } catch {
        return $null
    }
}

function Resolve-Python {
    param([string]$Requested)

    $candidates = @()
    if ($Requested) {
        $candidates += $Requested
    } else {
        $candidates += "py -3.14"
        $candidates += "python"
    }

    foreach ($candidate in $candidates) {
        if ($candidate -eq "py -3.14") {
            try {
                $v = & py -3.14 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"
                if ($LASTEXITCODE -eq 0 -and $v) {
                    return @{ Command = "py"; PrefixArgs = @("-3.14"); Version = $v.Trim() }
                }
            } catch {
                continue
            }
        } else {
            $v = Test-PythonVersion -Executable $candidate
            if ($v) {
                $parts = $v.Split(".")
                $major = [int]$parts[0]
                $minor = [int]$parts[1]
                if ($major -gt 3 -or ($major -eq 3 -and $minor -ge 14)) {
                    return @{ Command = $candidate; PrefixArgs = @(); Version = $v }
                }
            }
        }
    }

    throw "Python 3.14+ introuvable. Installez Python 3.14 ou utilisez -PythonExe <chemin>."
}

function Invoke-Python {
    param(
        [hashtable]$Py,
        [string[]]$PythonArgs
    )
    if ($Py.PrefixArgs.Count -gt 0) {
        & $Py.Command @($Py.PrefixArgs + $PythonArgs)
    } else {
        & $Py.Command @PythonArgs
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Commande Python echouee: $($Py.Command) $($PythonArgs -join ' ')"
    }
}

function Import-VsDevEnvironment {
    # Charge l'environnement MSVC (cl.exe, link.exe, etc.) dans la session PowerShell courante.
    if (-not $IsWindows) {
        return $false
    }

    $vswhere = Join-Path ${env:ProgramFiles(x86)} "Microsoft Visual Studio\Installer\vswhere.exe"
    if (-not (Test-Path $vswhere)) {
        return $false
    }

    $installPath = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
    if ($LASTEXITCODE -ne 0 -or -not $installPath) {
        return $false
    }

    $vsDevCmd = Join-Path $installPath "Common7\Tools\VsDevCmd.bat"
    if (-not (Test-Path $vsDevCmd)) {
        return $false
    }

    $envDump = & cmd /c "`"$vsDevCmd`" -no_logo -arch=x64 -host_arch=x64 >nul && set"
    if ($LASTEXITCODE -ne 0 -or -not $envDump) {
        return $false
    }

    foreach ($line in $envDump) {
        if ($line -match "^[^=]+=.*$") {
            $idx = $line.IndexOf("=")
            if ($idx -gt 0) {
                $name = $line.Substring(0, $idx)
                $value = $line.Substring($idx + 1)
                [System.Environment]::SetEnvironmentVariable($name, $value, "Process")
            }
        }
    }

    return $true
}

function Install-SpacyModel {
    param(
        [string]$VenvPython,
        [string]$Model,
        [int]$MaxAttempts = 3
    )

    $pipPackage = $Model -replace "_", "-"

    for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
        if ($attempt -gt 1) {
            Write-Warning "Nouvelle tentative ($attempt/$MaxAttempts) pour $Model..."
            # Evite de re-utiliser un artefact pip potentiellement corrompu.
            try {
                & $VenvPython -m pip cache purge | Out-Null
            } catch {
                # best effort
            }
            Start-Sleep -Seconds ([Math]::Min(5 * ($attempt - 1), 15))
        }

        $previousNoCache = $env:PIP_NO_CACHE_DIR
        if ($attempt -gt 1) {
            $env:PIP_NO_CACHE_DIR = "1"
        }

        try {
            & $VenvPython -m spacy download $Model
            if ($LASTEXITCODE -eq 0) {
                return
            }
        } finally {
            if ($null -eq $previousNoCache) {
                Remove-Item Env:PIP_NO_CACHE_DIR -ErrorAction SilentlyContinue
            } else {
                $env:PIP_NO_CACHE_DIR = $previousNoCache
            }
        }
    }

    Write-Warning "Echec via 'spacy download' pour $Model. Tentative de secours via pip (--no-cache-dir)."
    & $VenvPython -m pip install --no-cache-dir --upgrade $pipPackage
    if ($LASTEXITCODE -ne 0) {
        throw "Echec d'installation du modele spaCy $Model"
    }
}

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repoRoot

Write-Step "Resolution de Python 3.14+"
$py = Resolve-Python -Requested $PythonExe
Write-Host "Python detecte: $($py.Version) via '$($py.Command) $($py.PrefixArgs -join ' ')'"

Write-Step "Creation du venv: $VenvPath (can take some time, please wait)"
Invoke-Python -Py $py -PythonArgs @("-m", "venv", $VenvPath)

$venvPython = Join-Path $repoRoot (Join-Path $VenvPath "Scripts\python.exe")
if (-not (Test-Path $venvPython)) {
    throw "Python du venv introuvable: $venvPython"
}

Write-Step "Mise a jour de pip/setuptools/wheel"
& $venvPython -m pip install --upgrade pip setuptools wheel
if ($LASTEXITCODE -ne 0) {
    throw "Echec de mise a jour pip/setuptools/wheel"
}

$requiredReq = Join-Path $repoRoot "requirements-required.txt"
$optionalReq = Join-Path $repoRoot "requirements-optional.txt"

Write-Step "Installation des dependances obligatoires"
& $venvPython -m pip install -r $requiredReq
if ($LASTEXITCODE -ne 0) {
    throw "Echec d'installation des dependances obligatoires"
}

if (-not $SkipOptional) {
    Write-Step "Installation des dependances optionnelles"
    & $venvPython -m pip install -r $optionalReq
    if ($LASTEXITCODE -ne 0) {
        throw "Echec d'installation des dependances optionnelles"
    }

    Write-Step "Installation optionnelle native (best effort): hunspell"
    try {
        if ($IsWindows -and -not (Get-Command cl.exe -ErrorAction SilentlyContinue)) {
            Write-Host "MSVC (cl.exe) non detecte dans PATH. Tentative de chargement via VsDevCmd..."
            if (-not (Import-VsDevEnvironment)) {
                Write-Warning "Impossible de charger l'environnement Visual Studio C++ automatiquement."
                Write-Warning "Si hunspell echoue, lancez setup.ps1 depuis 'x64 Native Tools Command Prompt for VS'."
            }
        }

        & $venvPython -m pip install hunspell
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "hunspell non installe (toolchain native ou dependances C manquantes). spylls reste disponible."
            if ($IsWindows) {
                Write-Warning "Sur Windows, verifiez que le workload 'Desktop development with C++' est installe."
            }
        }
    } catch {
        Write-Warning "hunspell non installe ($($_.Exception.Message)). spylls reste disponible."
    }
}

if (-not $SkipPlaywrightBrowsers) {
    Write-Step "Installation des navigateurs Playwright (Chromium)"
    & $venvPython -m playwright install chromium
    if ($LASTEXITCODE -ne 0) {
        throw "Echec d'installation des navigateurs Playwright"
    }
}

if (-not $SkipSpacyModels) {
    Write-Step "Installation des modeles spaCy fr/de"
    & $venvPython -m pip install click
    if ($LASTEXITCODE -ne 0) {
        throw "Echec d'installation de click (requis pour l'installation des modeles spaCy)"
    }

    Install-SpacyModel -VenvPython $venvPython -Model "fr_core_news_lg"
    Install-SpacyModel -VenvPython $venvPython -Model "de_core_news_lg"
}

if (-not $SkipDbInit) {
    Write-Step "Initialisation de la base SQLite"
    & $venvPython ".agents\skills\manage-named-entities-db\scripts\init_db.py"
    if ($LASTEXITCODE -ne 0) {
        throw "Echec de l'initialisation de la base SQLite"
    }
}

Write-Step "Setup termine"
Write-Host "Activez le venv avec: .\$VenvPath\Scripts\Activate.ps1"
