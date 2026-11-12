# Links D:\VERIFYLY\Verifyly and prints the check. No ShipDesk window.
$ErrorActionPreference = 'Stop'
$python = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
if (-not (Test-Path -LiteralPath $python)) { throw "Python was not found at $python" }
Set-Location -LiteralPath 'D:\ShipDesk'
Write-Host "Code on this PC: $(git log -1 --oneline)"
& $python -m unittest -q
if ($LASTEXITCODE -ne 0) { throw 'The ShipDesk unit tests failed.' }
& $python .\check_project.py --folder 'D:\VERIFYLY\Verifyly' --bundle 'com.verifyly.app'
exit $LASTEXITCODE
