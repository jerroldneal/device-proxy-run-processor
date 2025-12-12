$ErrorActionPreference = "Stop"

# 1. Check Logs
Write-Host "Fetching logs from trading-engine..."
docker logs http-sidecar-trading-engine-1 --tail 50

# 2. Test Endpoint
Write-Host "`nTesting /pinescript/details endpoint..."
$code = "//@version=5`nstrategy('Test')`nrsiVal = ta.rsi(close, 14)`nif (rsiVal > 70)`n  strategy.entry('Short', strategy.short)"
$encodedCode = [System.Web.HttpUtility]::UrlEncode($code)
$url = "http://localhost:3000/pinescript/details?code=$encodedCode"

try {
    $response = Invoke-RestMethod -Uri $url -Method Get
    Write-Host "Response received:"
    $response | ConvertTo-Json -Depth 5
} catch {
    Write-Host "Error calling endpoint: $($_.Exception.Message)"
    if ($_.Exception.Response) {
        $stream = $_.Exception.Response.GetResponseStream()
        $reader = New-Object System.IO.StreamReader($stream)
        $body = $reader.ReadToEnd()
        Write-Host "Response Body: $body"
    }
}

# 3. Check AI Service
Write-Host "`nChecking AI Service (Ollama)..."
try {
    $ollama = Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -Method Get
    Write-Host "Ollama is reachable. Models:"
    $ollama.models | ForEach-Object { Write-Host "- $($_.name)" }
} catch {
    Write-Host "Ollama is NOT reachable: $($_.Exception.Message)"
}
