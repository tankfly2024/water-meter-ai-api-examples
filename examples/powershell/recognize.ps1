$ErrorActionPreference = "Stop"

$RootDir = Resolve-Path (Join-Path $PSScriptRoot "..\..")
function Import-DotEnv($Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return
    }
    foreach ($Line in Get-Content -LiteralPath $Path) {
        $Trimmed = $Line.Trim()
        if (-not $Trimmed -or $Trimmed.StartsWith("#") -or -not $Trimmed.Contains("=")) {
            continue
        }
        $Parts = $Trimmed.Split("=", 2)
        $Name = $Parts[0].Trim()
        $Value = $Parts[1].Trim().Trim('"').Trim("'")
        if (-not [Environment]::GetEnvironmentVariable($Name, "Process")) {
            [Environment]::SetEnvironmentVariable($Name, $Value, "Process")
        }
    }
}

Import-DotEnv (Join-Path $RootDir ".env")

$ApiBase = if ($env:WATERMETER_API_BASE) { $env:WATERMETER_API_BASE.TrimEnd("/") } else { "https://watermeterai.com" }
$ApiKey = $env:WATERMETER_API_KEY
$ImagePath = if ($env:IMAGE_PATH) { $env:IMAGE_PATH } else { Join-Path $RootDir "sample-images\example.jpg" }
if (-not [System.IO.Path]::IsPathRooted($ImagePath)) {
    $ImagePath = Join-Path $RootDir ($ImagePath -replace '^[.\\/]+', '')
}
$PollIntervalSeconds = if ($env:POLL_INTERVAL_SECONDS) { [int]$env:POLL_INTERVAL_SECONDS } else { 2 }
$PollTimeoutSeconds = if ($env:POLL_TIMEOUT_SECONDS) { [int]$env:POLL_TIMEOUT_SECONDS } else { 120 }

if (-not $ApiKey) {
    throw "Set WATERMETER_API_KEY in .env or the environment."
}

if (-not (Test-Path -LiteralPath $ImagePath -PathType Leaf)) {
    throw "Image not found: $ImagePath"
}

function Show-Json($Title, $Payload) {
    "`n== $Title =="
    $Payload | ConvertTo-Json -Depth 20
}

function Invoke-OpenApiGet($Path) {
    Invoke-RestMethod -Method Get -Uri "$ApiBase$Path" -Headers @{ Authorization = "Bearer $ApiKey" }
}

Show-Json "ai status" (Invoke-OpenApiGet "/api/open/ai-status")
Show-Json "quota" (Invoke-OpenApiGet "/api/open/quota")

$Created = Invoke-RestMethod -Method Post -Uri "$ApiBase/api/open/tasks" `
    -Headers @{ Authorization = "Bearer $ApiKey" } `
    -Form @{ file = Get-Item -LiteralPath $ImagePath }

Show-Json "create task" $Created

if (-not $Created.task_id) {
    throw "No task_id returned."
}

$Deadline = (Get-Date).AddSeconds($PollTimeoutSeconds)
while ((Get-Date) -lt $Deadline) {
    $Payload = Invoke-OpenApiGet "/api/open/tasks/$([uri]::EscapeDataString($Created.task_id))"
    Show-Json "task status" $Payload
    if ($Payload.status -in @("done", "failed")) {
        "`nFinal reading: $(if ($Payload.final_reading) { $Payload.final_reading } else { '-' })"
        exit 0
    }
    Start-Sleep -Seconds $PollIntervalSeconds
}

throw "Timed out waiting for task $($Created.task_id)."
