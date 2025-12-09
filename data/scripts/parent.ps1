$todoPath = "run-processor/data/todo/child-manifest.json"
$donePath = "run-processor/data/done/child-manifest.json"

Write-Host "Parent: Spawning child..."
$manifest = @{
    id = "task-child"
    goal = "I am the child"
    script_ref = "scripts/child.ps1"
    language = "powershell"
    max_retries = 1
    attempt_count = 0
    status = "QUEUED"
    history = @()
} | ConvertTo-Json

$manifest | Out-File -FilePath $todoPath -Encoding utf8

Write-Host "Parent: Waiting for child..."
while (-not (Test-Path $donePath)) {
    Start-Sleep -Seconds 1
}

Write-Host "Parent: Child finished!"
