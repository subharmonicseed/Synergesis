@echo off
setlocal
set "SYN_TARGET=%LOCALAPPDATA%\SynPrisme\extension-v0.1"
if not exist "%~dp0extension\manifest.json" (
  echo Extraire toute l'archive avant de lancer ce fichier.
  pause
  exit /b 1
)
robocopy "%~dp0extension" "%SYN_TARGET%" /E /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 (
  echo La copie a echoue. Aucun navigateur n'a ete modifie.
  pause
  exit /b 1
)
set "SYN_BROWSER="
if exist "%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe" set "SYN_BROWSER=%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"
if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" set "SYN_BROWSER=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set "SYN_BROWSER=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
set "SYN_PAGE=chrome://extensions"
if not defined SYN_BROWSER (
  if exist "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" set "SYN_BROWSER=%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"
  if exist "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe" set "SYN_BROWSER=%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"
  set "SYN_PAGE=edge://extensions"
)
(<nul set /p "=%SYN_TARGET%") | clip
start "" explorer.exe "%SYN_TARGET%"
if defined SYN_BROWSER start "" "%SYN_BROWSER%" "%SYN_PAGE%"
echo.
echo SYN Prisme : fichiers prepares. L'extension n'est pas encore activee.
echo Dans la page Extensions du navigateur :
echo 1. Activer Mode developpeur.
echo 2. Charger l'extension non empaquetee.
echo 3. Coller le chemin deja copie avec Ctrl+V et valider.
echo Puis ouvrir YouTube. Pas d'IA payante activee.
echo.
echo Dossier : %SYN_TARGET%
echo Si le navigateur ne s'est pas ouvert, ouvrir chrome://extensions.
pause
