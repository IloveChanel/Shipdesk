param([string]$ProjectPath = 'D:\ShipDesk')
$ErrorActionPreference = 'Stop'
$python = Get-Command python.exe -CommandType Application -ErrorAction SilentlyContinue |
    Where-Object { $_.Source -notlike '*\WindowsApps\*' } | Select-Object -First 1
if ($python) {
    $pythonPath = $python.Source
} else {
    $pythonPath = Get-Item -Path @(
        "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe"
        "$env:ProgramFiles\Python3*\python.exe"
    ) -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending |
        Select-Object -First 1 -ExpandProperty FullName
}
if (-not $pythonPath) { throw 'Install Python 3 with Tkinter, then run this setup again.' }
& $pythonPath -m pip install 'flet==1.1.2' 'flet-desktop==1.1.2' Pillow
if ($LASTEXITCODE -ne 0) { throw 'ShipDesk desktop dependencies could not be installed.' }

$project = New-Item -ItemType Directory -Path $ProjectPath -Force
if ($project.FullName -ne $PSScriptRoot) {
    foreach ($file in @('app.py', 'app_old_tkinter.py', 'audit.py', 'store.py', 'screenshots.py', 'project_check.py', 'ai_help.py')) {
        Copy-Item -LiteralPath (Join-Path $PSScriptRoot $file) -Destination $project.FullName -Force
    }
}
$launcher = Join-Path (Split-Path -Parent $pythonPath) 'pythonw.exe'
if (-not (Test-Path -LiteralPath $launcher)) { $launcher = $pythonPath }
$shell = New-Object -ComObject WScript.Shell
$desktop = [Environment]::GetFolderPath('DesktopDirectory')
$linkPath = Join-Path $desktop 'ShipDesk.lnk'
$link = $shell.CreateShortcut($linkPath)
$link.TargetPath = $launcher
$link.Arguments = '"' + (Join-Path $project.FullName 'app.py') + '"'
$link.WorkingDirectory = $project.FullName
$link.Save()
Invoke-Item -LiteralPath $linkPath
