$ErrorActionPreference = "Stop"

# Load Secrets
$secretsPath = "..\..\01_System\secrets.env"
if (Test-Path $secretsPath) {
    Write-Host "Loading secrets from $secretsPath"
    Get-Content $secretsPath | ForEach-Object {
        if ($_ -match "^[^#]*=") {
            $key, $value = $_.Split('=', 2)
            [Environment]::SetEnvironmentVariable($key, $value, "Process")
        }
    }
}
else {
    Write-Error "Secrets file not found at $secretsPath"
}

# Add Platform packages to PYTHONPATH
$platformPath = Resolve-Path "..\..\02_Platform\03_ErrorHandling\packages"
$env:PYTHONPATH = "$platformPath;$env:PYTHONPATH"
Write-Host "PYTHONPATH set to include: $platformPath"

# Run App
Write-Host "Starting WorkoutTracker on http://localhost:8000"
# Use python -m uvicorn to ensure we use the same environment as pip installed to
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
