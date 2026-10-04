param(
    [string]$GevPath = (Join-Path (Split-Path $PSScriptRoot -Parent) 'GodsEyeView'),
    [string]$NodePath = (Join-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) 'work\runtime\node-v24.21.0-win-x64\node.exe'),
    [string]$Distribution = 'Ubuntu-24.04',
    [string]$PythonPath = '/home/gabriel/syn-geo-venv/bin/python',
    [string]$MemoryPath = '/home/gabriel/synergesis-geo-noto'
)
$ErrorActionPreference = 'Stop'
$synGlobeProcess = $null
try {
    if (-not (Test-Path -LiteralPath $NodePath -PathType Leaf)) { throw 'Node portable absent. Consultez GODS_EYE_SYN.md.' }
    if (-not (Test-Path -LiteralPath (Join-Path $GevPath 'dist\syn.html') -PathType Leaf)) { throw 'Globe construit absent. Consultez GODS_EYE_SYN.md.' }
    $synExistingListeners = Get-NetTCPConnection -State Listen -LocalPort 5173,8765 -ErrorAction SilentlyContinue
    if ($synExistingListeners) { throw 'Une session utilise déjà le port 5173 ou 8765. Fermez cette session avant de relancer.' }
    # Fixed argv; no concatenated shell command, credentials or policy bypass.
    $synWslRepo = & wsl.exe -d $Distribution -- wslpath -a -u $PSScriptRoot
    if ($LASTEXITCODE -ne 0) { throw 'Ubuntu ou le dossier Syn est inaccessible.' }
    $synWslRepo = $synWslRepo.Trim()
    $synViteScript = Join-Path $GevPath 'node_modules\vite\bin\vite.js'
    $synArguments = @(('"' + $synViteScript + '"'), 'preview', '--config', 'vite.syn.config.js', '--configLoader', 'native')
    $synGlobeProcess = Start-Process -FilePath $NodePath -ArgumentList $synArguments -WorkingDirectory $GevPath -WindowStyle Hidden -PassThru
    Write-Host 'Le globe va ouvrir. Attendez que Syn affiche Globe dans ce terminal, puis cliquez Relire le journal.'
    # Only the static loopback UI is opened. Syn remains in this terminal.
    Start-Process 'http://127.0.0.1:5173/syn.html'
    & wsl.exe -d $Distribution --cd $synWslRepo -- $PythonPath synergesis_gods_eye.py --root $MemoryPath --allow-usgs --collect --message "Qu'as-tu observé dans cette région, qu'est-ce qui a changé et sur quelles données t'appuies-tu ?" --serve --interactive
    if ($LASTEXITCODE -ne 0) { throw 'La session Syn a échoué ; ses journaux restent conservés.' }
} catch {
    Write-Host ('Lancement arrêté : ' + $_.Exception.Message)
} finally {
    # Stop only the stateless process started by this launcher.
    if ($synGlobeProcess -and -not $synGlobeProcess.HasExited) {
        Stop-Process -Id $synGlobeProcess.Id -ErrorAction SilentlyContinue
    }
}
