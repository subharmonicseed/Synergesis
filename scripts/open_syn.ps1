param([switch]$CheckOnly, [switch]$NoBrowser)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$synRepo = Split-Path -Parent $PSScriptRoot
$synOutputs = Split-Path -Parent $synRepo
$synAddress = 'http://127.0.0.1:8765'
$synProfile = '/home/gabriel/synergesis-ollama51/profil-utilisateur'
$synRoot = '/home/gabriel/synergesis-ollama51/interface-locale'
$synModel = 'syn-mistral-import:latest'
function Get-SynState {
    try { return Invoke-RestMethod -Uri ($synAddress + '/api/state') -TimeoutSec 3 }
    catch { return $null }
}
function Assert-SynInstance($state, $manifest) {
    if ($state.app -ne 'synergesis-local-ui' -or $state.profile_dir -ne $synProfile -or
        $state.root_dir -ne $synRoot -or $state.provider.model -ne $synModel) {
        throw 'Le port 8765 est utilisé par une autre application ou un autre profil. Aucun processus arrêté.'
    }
    if ($state.source_manifest_sha256 -ne $manifest) {
        throw 'Une autre version de Syn est ouverte. Arrêtez-la avec son bouton Arrêter, puis relancez ce raccourci.'
    }
}
try {
    Write-Host 'Ouverture de Syn avec votre Mistral local...'
    $synPreflight = Join-Path $synOutputs 'LANCER_SYN_OLLAMA_51.ps1'
    if (-not (Test-Path -LiteralPath $synPreflight)) { throw 'Le contrôle de votre installation Mistral est introuvable.' }
    & $synPreflight -CheckOnly
    if ($LASTEXITCODE -ne 0) { throw 'Mistral est inaccessible. Ouvrez Docker Desktop puis relancez Syn.' }
    $synManifest = (Get-FileHash -LiteralPath (Join-Path $synRepo 'MANIFEST_SHA256.json') -Algorithm SHA256).Hash.ToLowerInvariant()
    $synScript = Join-Path $PSScriptRoot 'run_syn_ui.sh'
    $synWslScript = & wsl.exe -d Ubuntu-24.04 -- wslpath -a -u $synScript.Replace('\','/')
    if ($LASTEXITCODE -ne 0) { throw 'Ubuntu-24.04 est inaccessible.' }
    & wsl.exe -d Ubuntu-24.04 -- bash $synWslScript.Trim() --expected-manifest $synManifest --check
    if ($LASTEXITCODE -ne 0) { throw 'La vérification des sources installées a échoué.' }
    if ($CheckOnly) { Write-Host 'Installation vérifiée.'; exit 0 }
    $synState = Get-SynState
    if ($null -ne $synState) {
        Assert-SynInstance $synState $synManifest
        Write-Host 'Syn est déjà ouvert ; le serveur existant est réutilisé.'
    } else {
        $synLogDir = Join-Path $synOutputs 'SynUILogs'
        New-Item -ItemType Directory -Path $synLogDir -Force | Out-Null
        $synRunId = [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss') + '-' + [Guid]::NewGuid().ToString('N').Substring(0,8)
        $synOutLog = Join-Path $synLogDir ($synRunId + '.out.log')
        $synErrLog = Join-Path $synLogDir ($synRunId + '.err.log')
        $synArgs = @('-d','Ubuntu-24.04','--','bash',('"' + $synWslScript.Trim() + '"'),'--expected-manifest',$synManifest)
        $synService = Start-Process -FilePath wsl.exe -ArgumentList $synArgs -WindowStyle Hidden -RedirectStandardOutput $synOutLog -RedirectStandardError $synErrLog -PassThru
        $synDeadline = [DateTime]::UtcNow.AddSeconds(30)
        do {
            $synState = Get-SynState
            if ($null -ne $synState) { break }
            $synService.Refresh()
            # A second shortcut may lose the service lock while the first one
            # is still starting. Wait for its matching HTTP instance as well.
            Start-Sleep -Milliseconds 400
        } while ([DateTime]::UtcNow -lt $synDeadline)
        if ($null -eq $synState) { throw ('Le serveur ne répond pas. Diagnostic : ' + $synErrLog) }
        Assert-SynInstance $synState $synManifest
    }
    if (-not $NoBrowser) { Start-Process $synAddress | Out-Null }
    Write-Host ('Syn est disponible : ' + $synAddress)
    Write-Host 'Pour arrêter le serveur : bouton Arrêter dans la navigation de Syn. Ollama reste disponible.'
} catch {
    Write-Host ('Syn ne peut pas être ouvert : ' + $_.Exception.Message) -ForegroundColor Red
    if (-not $CheckOnly -and -not $NoBrowser) { Read-Host 'Appuyez sur Entrée pour fermer' | Out-Null }
    exit 1
}
