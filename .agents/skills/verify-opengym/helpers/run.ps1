$ErrorActionPreference = 'Stop'
$root = Split-Path (Split-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) -Parent) -Parent
if ((Resolve-Path .).Path -ne $root) { throw "Run from repository root: $root" }
$runId = [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss-fff')
$session = "opengym-verify-$runId"
$log = ".playwright-cli/verify-opengym-$runId.log"
$proof = $null
New-Item -ItemType Directory -Force .playwright-cli | Out-Null
try {
    $opened = & playwright-cli "-s=$session" open http://localhost:8080 --browser=msedge 2>&1
    $opened | Set-Content -LiteralPath $log -Encoding utf8
    if ($LASTEXITCODE -ne 0) { throw "Browser launch failed; inspect $log" }
    $output = & playwright-cli "-s=$session" run-code --filename=.agents/skills/verify-opengym/helpers/guest-smoke.js 2>&1
    $output | Add-Content -LiteralPath $log -Encoding utf8
    $json = $output | Where-Object { "$_".StartsWith('{"completed":') } | Select-Object -Last 1
    if (!$json) { throw "No structured proof returned; inspect $log" }
    $proof = $json | ConvertFrom-Json
    if (!$proof.completed) { throw "UI verification failed: $($proof.failure). Evidence: $log" }
    if (@($proof.results).Count -ne 17) { throw 'Incomplete case list' }
    $backupPath = "$($proof.prefix)-backup.json"
    $backup = Get-Content -LiteralPath $backupPath -Raw | ConvertFrom-Json
    if (@($backup.routines).Count -ne 1 -or $backup.routines[0].name -ne 'E2E CLI Routine') { throw 'Export: routine mismatch' }
    if (@($backup.workouts).Count -ne 1 -or $backup.workouts[0].name -ne 'E2E CLI Routine') { throw 'Export: workout mismatch' }
    $sets = @($backup.workouts[0].entries[0].sets)
    if ($sets.Count -ne 3 -or @($sets | Where-Object { $_.done -ne $true -or $_.r -ne 10 }).Count -ne 0) { throw 'Export: completed sets mismatch' }
    if (@($backup.bodyweight).Count -ne 1 -or $backup.bodyweight[0].w -ne 72.5) { throw 'Export: bodyweight mismatch' }
    if (@($backup.measurements).Count -ne 1 -or $backup.measurements[0].waist -ne 85 -or $null -ne $backup.measurements[0].neck) { throw 'Export: measurements mismatch' }
    if ($null -ne $backup.active) { throw 'Export: workout still active after completion' }
    foreach ($case in $proof.results) {
        if (!(Test-Path -LiteralPath "$($proof.prefix)-$($case.id).png")) { throw "Missing screenshot: $($case.id)" }
    }
    "Export assertions PASS" | Add-Content -LiteralPath $log
} finally {
    & playwright-cli "-s=$session" close 2>&1 | Add-Content -LiteralPath $log
}
if (!(Test-Path -LiteralPath $log) -or !(Test-Path -LiteralPath "$($proof.prefix)-backup.json")) { throw 'Cleanup removed proof' }
foreach ($case in $proof.results) {
    if (!(Test-Path -LiteralPath "$($proof.prefix)-$($case.id).png")) { throw "Cleanup removed screenshot: $($case.id)" }
}
"PASS: 17 UI checkpoints + export assertions; owned browser closed; evidence retained at $log"

