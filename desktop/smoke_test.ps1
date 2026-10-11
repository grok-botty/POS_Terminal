# Smoke-test a built CashMachine exe.
# Starts the windowed binary in headless mode and requires HTTP 200 from
# /pos/shift/ before the timeout. Used by .github/workflows/windows-exe.yml.
param(
    [string]$Exe = "dist\CashMachine.exe",
    [int]$TimeoutSec = 180
)

$ErrorActionPreference = "Stop"
if (Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue) {
    $PSNativeCommandUseErrorActionPreference = $false
}

function Write-LogFile([string]$Path) {
    if (Test-Path $Path) {
        Write-Host "----- $Path -----"
        Get-Content -Path $Path -Tail 200
    }
}

if (-not $env:CASHMACHINE_DB_PATH) {
    $smokeRoot = Join-Path $env:TEMP "cashmachine-smoke"
    $env:CASHMACHINE_DB_PATH = Join-Path $smokeRoot "cashmachine.sqlite3"
}
$env:CASHMACHINE_HEADLESS = "1"
$env:CASHMACHINE_DEBUG = "0"

$dataDir = Split-Path -Parent $env:CASHMACHINE_DB_PATH
New-Item -ItemType Directory -Force -Path $dataDir | Out-Null
$urlFile = Join-Path $dataDir "cashmachine.url"
$appLog = Join-Path $dataDir "cashmachine.log"
$bootLog = Join-Path $dataDir "cashmachine-boot.log"

$exePath = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Exe)
if (-not (Test-Path $exePath)) {
    Write-Error "Exe not found: $exePath"
}

try {
    Add-MpPreference -ExclusionPath $exePath, $dataDir, $env:TEMP -ErrorAction Stop
    Write-Host "Defender exclusion added for the exe and data dir."
} catch {
    Write-Host "Defender exclusion skipped: $($_.Exception.Message)"
}

Get-Process -Name "CashMachine" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

Write-Host "Starting $exePath"
Write-Host "DB: $env:CASHMACHINE_DB_PATH"

$proc = $null
$passed = $false
$code = 0
$shiftUrl = $null
$deadline = (Get-Date).AddSeconds($TimeoutSec)

try {
    $proc = Start-Process -FilePath $exePath -PassThru -WindowStyle Hidden
    while ((Get-Date) -lt $deadline) {
        if ($proc.HasExited) {
            Write-Host "Process exited early with code $($proc.ExitCode)"
            break
        }
        if (-not $shiftUrl -and (Test-Path $urlFile)) {
            $base = (Get-Content -Path $urlFile -Raw).Trim()
            if ($base) {
                $shiftUrl = ($base.TrimEnd("/")) + "/pos/shift/"
                Write-Host "Probing $shiftUrl"
            }
        }
        if ($shiftUrl) {
            try {
                $resp = Invoke-WebRequest -Uri $shiftUrl -UseBasicParsing -TimeoutSec 5 -MaximumRedirection 0
                $code = [int]$resp.StatusCode
            } catch {
                $response = $_.Exception.Response
                if ($response -and $response.StatusCode) {
                    $code = [int]$response.StatusCode
                } else {
                    $code = 0
                }
            }
            if ($code -eq 200) {
                Write-Host "Smoke test passed: $shiftUrl -> 200"
                $passed = $true
                break
            }
            Write-Host "Still waiting, HTTP $code"
        } else {
            Write-Host "Waiting for $urlFile"
        }
        Start-Sleep -Seconds 2
    }
} finally {
    if ($proc -and -not $proc.HasExited) {
        & taskkill.exe /PID $proc.Id /T /F | Out-Host
    }
}

if ($passed) {
    exit 0
}

Write-Host "Smoke test failed. Last HTTP status: $code"
Write-LogFile $bootLog
Write-LogFile $appLog
exit 1
