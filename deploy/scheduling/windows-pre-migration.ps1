# Manual prerequisite, not an installed task or a DDL runner. Nonzero must stop migration.
param(
    [Parameter(Mandatory=$true)][string]$Node,
    [Parameter(Mandatory=$true)][string]$Repository,
    [Parameter(Mandatory=$true)][string]$Config
)
$ErrorActionPreference = 'Stop'
foreach ($path in @($Node, $Repository, $Config)) {
    if (-not [System.IO.Path]::IsPathRooted($path)) { throw 'Absolute paths required' }
}
& $Node (Join-Path $Repository 'scripts/platform.mjs') operate backup --config $Config --reason pre-migration
exit $LASTEXITCODE
