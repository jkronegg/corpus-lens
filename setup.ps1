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
        [string[]]$Args
    )
    if ($Py.PrefixArgs.Count -gt 0) {
        & $Py.Command @($Py.PrefixArgs + $Args)
    } else {
        & $Py.Command @Args
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Commande Python echouee: $($Py.Command) $($Args -join ' ')"
    }
}

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repoRoot

Write-Step "Resolution de Python 3.14+"
$py = Resolve-Python -Requested $PythonExe
Write-Host "Python detecte: $($py.Version) via '$($py.Command) $($py.PrefixArgs -join ' ')'"

Write-Step "Creation du venv: $VenvPath"
Invoke-Python -Py $py -Args @("-m", "venv", $VenvPath)

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
        & $venvPython -m pip install hunspell
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "hunspell non installe (toolchain native manquante). spylls reste disponible."
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
    & $venvPython -m spacy download fr_core_news_lg
    if ($LASTEXITCODE -ne 0) {
        throw "Echec d'installation du modele spaCy fr_core_news_lg"
    }
    & $venvPython -m spacy download de_core_news_lg
    if ($LASTEXITCODE -ne 0) {
        throw "Echec d'installation du modele spaCy de_core_news_lg"
    }
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
