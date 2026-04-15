param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $MessageParts
)

$ErrorActionPreference = "Stop"

function Invoke-Git {
    git @args
    if ($LASTEXITCODE -ne 0) {
        throw "git $($args -join ' ') failed with exit code $LASTEXITCODE"
    }
}

$repoRoot = git rev-parse --show-toplevel 2>$null
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($repoRoot)) {
    throw "git ci must be run inside a Git repository"
}

Set-Location $repoRoot

$message = ($MessageParts -join " ").Trim()
if ([string]::IsNullOrWhiteSpace($message)) {
    $message = "chore: update workspace $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
}

Invoke-Git add -A

git diff --cached --quiet
if ($LASTEXITCODE -eq 0) {
    Write-Host "Nothing to commit."
    exit 0
}

Invoke-Git commit -m $message
