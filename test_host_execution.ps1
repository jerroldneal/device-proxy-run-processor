$scriptContent = 'if (Test-Path E:\) { Get-ChildItem E:\ } else { Write-Host "E: drive not found" }'
$scriptPath = 'C:\.run\scripts\list_e_drive.ps1'
New-Item -ItemType File -Force -Path $scriptPath -Value $scriptContent | Out-Null

$manifest = @{
    id = "test-list-e-drive"
    goal = "List contents of E: drive"
    script_ref = "scripts/list_e_drive.ps1"
    language = "powershell"
    max_retries = 0
} | ConvertTo-Json

$manifestPath = 'C:\.run\todo\test_list_e.json'
Set-Content -Path $manifestPath -Value $manifest

Write-Host "Test triggered. Script: $scriptPath, Manifest: $manifestPath"
