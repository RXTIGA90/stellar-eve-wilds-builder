<#
Stellar Eve for Monster Hunter Wilds - installer (builds everything from YOUR OWN game files).

  install.bat (double-click) or: powershell -ExecutionPolicy Bypass -File install.ps1 [-Rows 144,147]   # tools + build + install
  uninstall.bat              or: powershell -ExecutionPolicy Bypass -File install.ps1 -Uninstall      # restore the game

-Jobs N: build N outfits at the same time (default 1; about 4 CPU threads and 6 GB RAM each).
-Rows: only those outfits (ids in data/night_queue.json; 27 / 63 = default-look innerwear beta type 2 / type 1). Outfits installed before stay installed.
install.bat opens StellarEve.exe (language choice, outfit pictures, progress, uninstall), which runs this script with
-NoGui. Run directly without -Rows, the script asks with a numbered text list; -All builds everything.
Needs: Stellar Blade and Monster Hunter Wilds installed (Steam), REFramework installed in Monster Hunter Wilds,
about 25 GB free space, internet for the tool downloads.
#>
param(
    [string]$SbPaks = "",
    [string]$MhwDir = "",
    [string]$WorkDir = "",
    [string]$Rows = "",
    [int]$Jobs = 1,
    [switch]$Uninstall,
    [switch]$SkipTools,
    [switch]$Yes,
    [switch]$NoInstall,
    [switch]$All,
    [switch]$NoGui
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Tools = Join-Path $Root "tools"
$Dl = Join-Path $Tools "_download"
$Deps = Get-Content (Join-Path $Root "deps.json") -Raw | ConvertFrom-Json
$PyExe = Join-Path $Tools "blender\5.2\python\bin\python.exe"

function Say($t) { Write-Host "[stellar-eve] $t" -ForegroundColor Cyan }

function Find-SteamGame($folder, $mustHave) {
    # Steam itself can live on any drive: ask the registry first, then the default folder
    $steams = @()
    foreach ($k in @(@("HKCU:\Software\Valve\Steam", "SteamPath"),
                     @("HKLM:\SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
                     @("HKLM:\SOFTWARE\Valve\Steam", "InstallPath"))) {
        try { $v = (Get-ItemProperty -Path $k[0] -Name $k[1] -ErrorAction Stop).($k[1]); if ($v) { $steams += $v.Replace('/', '\') } } catch {}
    }
    $steams += "C:\Program Files (x86)\Steam"
    $libs = @()
    foreach ($s in $steams) {
        $libs += $s
        $vdf = Join-Path $s "steamapps\libraryfolders.vdf"
        if (Test-Path $vdf) {
            foreach ($m in [regex]::Matches((Get-Content $vdf -Raw), '"path"\s+"([^"]+)"')) { $libs += $m.Groups[1].Value.Replace('\\', '\') }
        }
    }
    # last resort: the usual library folder names on every drive
    foreach ($d in (Get-PSDrive -PSProvider FileSystem -ErrorAction SilentlyContinue)) {
        foreach ($sub in @("SteamLibrary", "Steam", "Program Files (x86)\Steam", "Games\Steam", "Games\SteamLibrary")) { $libs += Join-Path $d.Root $sub }
    }
    foreach ($l in ($libs | Select-Object -Unique)) {
        $p = Join-Path $l "steamapps\common\$folder"
        # an empty leftover folder (uninstalled game) must not win over the real install
        if (Test-Path -LiteralPath (Join-Path $p $mustHave) -ErrorAction SilentlyContinue) { return $p }
    }
    return ""
}

function Get-File($name, $url, $hash, $algo = "SHA256") {
    New-Item -ItemType Directory -Force $Dl | Out-Null
    $out = Join-Path $Dl $name
    if (-not (Test-Path $out)) {
        # into <name>.part first (renamed only when complete), so a dropped connection never leaves a broken file;
        # curl (built into Windows 10/11) retries and resumes, Invoke-WebRequest is the fallback
        Say "downloading $name"
        $part = "$out.part"
        $curl = Join-Path $env:SystemRoot "System32\curl.exe"
        if (Test-Path $curl) {
            & $curl -L --fail --retry 5 --retry-all-errors --retry-delay 3 -C - -o $part $url
            if ($LASTEXITCODE) { throw "download failed: $name (curl exit $LASTEXITCODE). Run install.bat again to resume." }
        } else {
            for ($i = 1; ; $i++) {
                try { Invoke-WebRequest -Uri $url -OutFile $part -UseBasicParsing; break }
                catch { if ($i -ge 3) { throw "download failed: $name ($_). Run install.bat again." }; Say "retrying $name ($i)"; Start-Sleep 3 }
            }
        }
        Move-Item -Force $part $out
    }
    if ($hash) {
        $h = (Get-FileHash $out -Algorithm $algo).Hash.ToLower()
        if ($h -ne $hash.ToLower()) { Remove-Item $out; throw "checksum mismatch: $name" }
    }
    return $out
}

function Expand-Into($zip, $dest, [switch]$StripTop) {
    $tmp = Join-Path $Dl ("x_" + [IO.Path]::GetFileNameWithoutExtension($zip))
    if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
    Expand-Archive $zip $tmp
    $src = $tmp
    if ($StripTop) { $src = (Get-ChildItem $tmp -Directory | Select-Object -First 1).FullName }
    New-Item -ItemType Directory -Force $dest | Out-Null
    Copy-Item (Join-Path $src "*") $dest -Recurse -Force
    Remove-Item $tmp -Recurse -Force
}

function Enable-LooseFileLoader {
    # the outfits replace files that are inside the game's paks: the game reads those loose files only with REFramework's
    # Loose File Loader on (without it only Eve's face - a new file - shows). Turn it on in re2_fw_config.txt; the file as
    # it was is kept once in work\game-backup\. Uninstall leaves it on (other mods may need it).
    $cfg = Join-Path $MhwDir "re2_fw_config.txt"
    $line = "LooseFileLoader_Enabled=true"
    $lines = @()
    if (Test-Path -LiteralPath $cfg) {
        $lines = @(Get-Content -LiteralPath $cfg)
        if ($lines | Where-Object { $_ -match '^\s*LooseFileLoader_Enabled\s*=\s*true\s*$' }) { Say "REFramework Loose File Loader: already on"; return }
        $bk = Join-Path $WorkDir "game-backup\re2_fw_config.txt.orig"
        if (-not (Test-Path -LiteralPath $bk)) { New-Item -ItemType Directory -Force (Split-Path $bk) | Out-Null; Copy-Item -LiteralPath $cfg $bk }
    }
    $found = $false
    $lines = @($lines | ForEach-Object { if ($_ -match '^\s*LooseFileLoader_Enabled\s*=') { $found = $true; $line } else { $_ } })
    if (-not $found) { $lines += $line }
    [IO.File]::WriteAllLines($cfg, [string[]]$lines, (New-Object System.Text.UTF8Encoding $false))
    Say "REFramework Loose File Loader: turned on ($cfg)"
}

function Get-OutfitMenu {
    $queue = Get-Content (Join-Path $Root "data\night_queue.json") -Raw -Encoding UTF8 | ConvertFrom-Json
    $menu = @(@{ row = "27"; name = "Ocean Maid / 오션 메이드"; armor = "default look: innerwear beta type 2 / 기본 외형: 이너웨어 β 타입 2"; dlc = "" },
              @{ row = "63"; name = "Wave Diver Bikini / 웨이브 다이버 비키니"; armor = "default look: innerwear beta type 1 / 기본 외형: 이너웨어 β 타입 1"; dlc = "" })
    foreach ($q in $queue) {
        $dlc = ""
        if ($q.code[1] -match "Nier") { $dlc = "NieR DLC" } elseif ($q.code[1] -match "Nikke") { $dlc = "NIKKE DLC" }
        $armor = ($q.armor -replace '\s*\(.*$', '')
        if ("$($q.row)" -eq "149") { $armor += " (body + waist / 몸통 + 허리)" }   # this outfit's body sits in the waist part
        $menu += @{ row = "$($q.row)"; name = "$($q.eve)"; armor = $armor; dlc = $dlc }
    }
    foreach ($m in $menu) { $m.text = "$($m.name)  <-  armor / 갑옷: $($m.armor)" + $(if ($m.dlc) { "  [$($m.dlc)]" } else { "" }) }
    return $menu
}

# StellarEve.exe (install.bat) runs this script with -NoGui and shows its output as the progress window's log
if ([Console]::IsOutputRedirected) { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 }

# ---------------- paths ----------------
if (-not $SbPaks) { $sb = Find-SteamGame "StellarBlade" "SB\Content\Paks\pakchunk0-WindowsNoEditor.pak"; if ($sb) { $SbPaks = Join-Path $sb "SB\Content\Paks" } }
if (-not $MhwDir) { $MhwDir = Find-SteamGame "MonsterHunterWilds" "MonsterHunterWilds.exe" }
if (-not $WorkDir) { $WorkDir = Join-Path $Root "work" }
$hint = "(Steam > Library > right-click the game > Manage > Browse local files shows its folder)"
# uninstall needs only Monster Hunter Wilds (Stellar Blade may already be gone)
if (-not $Uninstall -and (-not $SbPaks -or -not (Test-Path -LiteralPath $SbPaks))) { throw "Stellar Blade not found. Run again with -SbPaks '<...>\StellarBlade\SB\Content\Paks' $hint" }
if (-not $MhwDir -or -not (Test-Path -LiteralPath (Join-Path $MhwDir "MonsterHunterWilds.exe"))) { throw "Monster Hunter Wilds not found. Run again with -MhwDir '<...>\MonsterHunterWilds' $hint" }
if (-not $Uninstall -and -not (Test-Path -LiteralPath (Join-Path $MhwDir "dinput8.dll"))) {
    Write-Host "REFramework is not installed (no dinput8.dll in $MhwDir). The outfits will not work in game without it - see README step 2." -ForegroundColor Yellow
}
$cfg = [ordered]@{
    sb_paks = $SbPaks; mhw_dir = $MhwDir; work_dir = $WorkDir
    blender = (Join-Path $Tools "blender\blender.exe"); blender_user_scripts = (Join-Path $Tools "blender\user-scripts")
    dotnet = (Join-Path $Tools "dotnet\dotnet.exe"); ree_editor_dir = (Join-Path $Tools "ree-content-editor"); previews = $false
}
$cfg | ConvertTo-Json | Set-Content (Join-Path $Root "config.json") -Encoding UTF8
Say "Stellar Blade: $SbPaks"
Say "Monster Hunter Wilds: $MhwDir"

if ($Uninstall) {
    if (Get-Process MonsterHunterWilds -ErrorAction SilentlyContinue) { throw "Monster Hunter Wilds is running. Close the game and run again." }
    & $PyExe (Join-Path $Root "scripts\install_game.py") uninstall
    $code = $LASTEXITCODE
    # the desktop / Start menu shortcuts StellarEve.exe made (only those pointing into this folder)
    $sh = New-Object -ComObject WScript.Shell
    $menuDir = Join-Path ([Environment]::GetFolderPath("Programs")) "Stellar Eve"
    $links = @(Join-Path ([Environment]::GetFolderPath("Desktop")) "Stellar Eve.lnk") + @(Get-ChildItem $menuDir -Filter *.lnk -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
    foreach ($l in $links) { if ((Test-Path $l) -and $sh.CreateShortcut($l).TargetPath -like "$Root\*") { Remove-Item $l; Say "removed shortcut $l" } }
    if ((Test-Path $menuDir) -and -not (Get-ChildItem $menuDir)) { Remove-Item $menuDir }
    exit $code
}

# ---------------- which outfits (text mode) ----------------
if (-not $Rows -and -not $All) {
    $menu = Get-OutfitMenu
    Write-Host ""
    Write-Host "Choose the outfits to build and install / 설치할 의상을 고르세요" -ForegroundColor Cyan
    for ($i = 0; $i -lt $menu.Count; $i++) { Write-Host ("  {0,2}) {1}" -f ($i + 1), $menu[$i].text) }
    Write-Host "Eve's face is always included. In game, wear the listed armor (as layered appearance) to see the outfit."
    Write-Host "Eve 얼굴은 항상 포함됩니다. 게임에서는 표시된 갑옷을 외형(덧입기)으로 입으면 그 의상이 나옵니다."
    while (-not $Rows) {
        $a = Read-Host "Numbers separated by commas (e.g. 3,5), or all / 번호를 쉼표로 (예: 3,5), 전체는 all"
        if ($a -match '^\s*(all|a|전체)?\s*$') { break }
        $pick = @()
        foreach ($t in ($a -split '[,\s]+' | Where-Object { $_ })) {
            $n = 0
            if ([int]::TryParse($t, [ref]$n) -and $n -ge 1 -and $n -le $menu.Count) { $pick += $menu[$n - 1].row }
            else { $pick = @(); Write-Host "  '$t' is not on the list / 목록에 없는 번호입니다" -ForegroundColor Yellow; break }
        }
        if ($pick.Count) { $Rows = ($pick | Select-Object -Unique) -join ',' }
    }
    if ($Rows) { Say "outfits: $Rows" } else { Say "outfits: all" }
}

# ---------------- tools ----------------
if (-not $SkipTools) {
    if (-not $Yes) {
        Write-Host ""
        Write-Host "The installer will download these tools from their official pages (see deps.json):"
        Write-Host "  Blender 5.2.2, RE Mesh Editor, RE Chain Editor, .NET 10 SDK,"
        Write-Host "  REE Content Editor, the MHW file list (REasy), the Stellar Blade usmap."
        $a = Read-Host "Continue? (y/n)"; if ($a -ne "y") { exit 1 }
    }
    if (-not (Test-Path (Join-Path $Tools "blender\blender.exe"))) {
        $z = Get-File "blender.zip" $Deps.blender.url $Deps.blender.sha256
        Expand-Into $z (Join-Path $Tools "blender") -StripTop
    }
    $addons = Join-Path $Tools "blender\user-scripts\addons"
    if (-not (Test-Path (Join-Path $addons "RE_Mesh_Editor"))) {
        $z = Get-File "re_mesh_editor.zip" $Deps.re_mesh_editor.url $Deps.re_mesh_editor.sha256
        Expand-Into $z (Join-Path $addons "RE_Mesh_Editor") -StripTop
        Copy-Item (Join-Path $Root "patches\RE_Mesh_Editor\*") (Join-Path $addons "RE_Mesh_Editor") -Recurse -Force
    }
    if (-not (Test-Path (Join-Path $addons "RE_Chain_Editor"))) {
        $z = Get-File "re_chain_editor.zip" $Deps.re_chain_editor.url $Deps.re_chain_editor.sha256
        Expand-Into $z (Join-Path $addons "RE_Chain_Editor") -StripTop
        Copy-Item (Join-Path $Root "patches\RE_Chain_Editor\*") (Join-Path $addons "RE_Chain_Editor") -Recurse -Force
    }
    if (-not (Test-Path (Join-Path $Tools "dotnet\dotnet.exe"))) {
        $z = Get-File "dotnet_sdk.zip" $Deps.dotnet_sdk.url $Deps.dotnet_sdk.sha512 "SHA512"
        Expand-Into $z (Join-Path $Tools "dotnet")
    }
    $ree = Join-Path $Tools "ree-content-editor"
    if (-not (Test-Path (Join-Path $ree "REE-Lib.dll"))) {
        $z = Get-File "ree_content_editor.zip" $Deps.ree_content_editor.url $Deps.ree_content_editor.sha256
        Expand-Into $z $ree
    }
    if (-not (Test-Path (Join-Path $ree "MHWS_STM-upstream.list"))) {
        $f = Get-File "MHWS_STM.list" $Deps.mhw_file_list.url $Deps.mhw_file_list.sha256
        Copy-Item $f (Join-Path $ree "MHWS_STM-upstream.list")
    }
    # our two .NET tools, built from source
    $dn = Join-Path $Tools "dotnet\dotnet.exe"
    & $dn build (Join-Path $Tools "sb-extract\sb-extract.csproj") -c Release -o (Join-Path $Tools "sb-extract\bin")
    if ($LASTEXITCODE) { throw "sb-extract build failed" }
    & $dn build (Join-Path $Tools "motion-convert\motion-convert.csproj") -c Release -o (Join-Path $Tools "motion-convert\bin") "-p:ReeEditorDir=$ree\"
    if ($LASTEXITCODE) { throw "motion-convert build failed" }
    $us = Join-Path $Tools "sb-extract\bin\4.26.2-0+++UE4+Release-4.26-SB-v1.4.1.usmap"
    if (-not (Test-Path $us)) { $f = Get-File "sb.usmap" $Deps.sb_usmap.url $Deps.sb_usmap.sha256; Copy-Item $f $us }
}

# ---------------- build + install ----------------
$env:PYTHONIOENCODING = "utf-8"
if (-not $NoInstall -and (Get-Process MonsterHunterWilds -ErrorAction SilentlyContinue)) { throw "Monster Hunter Wilds is running. Close the game and run again." }
$buildArgs = @()
if ($Rows) { $buildArgs = @("--rows", ($Rows -replace '\s', '')) }
if ($Jobs -gt 1) { $buildArgs += @("--jobs", "$Jobs") }
& $PyExe (Join-Path $Root "scripts\build_all.py") @buildArgs
if ($LASTEXITCODE) { throw "build failed (logs in $WorkDir)" }
if ($NoInstall) { Say "built (not installed): $WorkDir"; exit 0 }
& $PyExe (Join-Path $Root "scripts\install_game.py") install
if ($LASTEXITCODE) { throw "install failed" }
Enable-LooseFileLoader
Say "done. Start the game. To remove: Stellar Eve > Uninstall, or uninstall.bat"

