# Full desktop check. No ShipDesk window. Prints GREEN only if every test passes.
$ErrorActionPreference = 'Stop'
$python = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
if (-not (Test-Path -LiteralPath $python)) { throw "Python was not found at $python" }
Set-Location -LiteralPath 'D:\ShipDesk'
Write-Host "Code on this PC: $(git log -1 --oneline)"
& $python -m unittest -v
if ($LASTEXITCODE -ne 0) { throw 'The ShipDesk unit tests failed.' }
& $python .\check_project.py --folder 'D:\VERIFYLY\Verifyly' --bundle 'com.verifyly.app'
if ($LASTEXITCODE -ne 0) { throw 'The Verifyly folder check failed.' }
Write-Host 'GREEN · desktop checks passed'
exit 0
