# Separate demo environment: SQLite + simulated payments; original .env is untouched.
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $projectRoot 'backend'
$frontendDir = Join-Path $projectRoot 'frontend'
$pythonExe = Join-Path $backendDir '.venv\Scripts\python.exe'
$viteScript = Join-Path $frontendDir 'node_modules\vite\bin\vite.js'
$nodeExe = (Get-Command node).Source

foreach ($port in @(8001, 5174)) {
    if (Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue) {
        throw "Port $port is already in use. Existing services were left running."
    }
}
if (!(Test-Path -LiteralPath $pythonExe) -or !(Test-Path -LiteralPath $viteScript)) {
    throw 'Install backend .venv and frontend node_modules first.'
}

$env:PYTHONIOENCODING = 'utf-8'
$env:DATABASE_URL = 'sqlite:///' + ((Join-Path $backendDir 'demo-data\pawcare.sqlite3') -replace '\\', '/')
$env:JWT_SECRET_KEY = [guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N')
$env:PAYMENT_PROVIDER = 'mock'
$env:PAYMENT_MOCK_BASE_URL = 'http://localhost:5174'
$env:PUBLIC_BASE_URL = 'http://127.0.0.1:8001'
$env:UPLOAD_DIR = Join-Path $backendDir 'demo-data\uploads'
$env:CORS_ORIGINS = 'http://localhost:5174,http://127.0.0.1:5174'
$env:SCHEDULER_ENABLED = 'false'
$env:RAG_ENABLED = 'false'
$env:REDIS_URL = ''
$env:SMTP_HOST = ''
$env:SMTP_USER = ''
$env:SMTP_PASSWORD = ''
$env:LLM_API_KEY = ''
$env:PAWCARE_API_TARGET = 'http://127.0.0.1:8001'
& $pythonExe -B (Join-Path $backendDir 'scripts\prepare_demo.py')
if ($LASTEXITCODE -ne 0) { throw 'Demo preparation failed.' }

$logsDir = Join-Path $projectRoot 'demo-logs'
New-Item -ItemType Directory -Path $logsDir -Force | Out-Null
$backendProcess = Start-Process -FilePath $pythonExe -ArgumentList @('-B', ('"' + (Join-Path $backendDir 'scripts\run_demo_server.py') + '"')) -WorkingDirectory $backendDir -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logsDir 'backend-out.log') -RedirectStandardError (Join-Path $logsDir 'backend-err.log')
try {
    $frontendProcess = Start-Process -FilePath $nodeExe -ArgumentList @(('"' + $viteScript + '"'), '--host', '127.0.0.1', '--port', '5174', '--strictPort') -WorkingDirectory $frontendDir -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logsDir 'frontend-out.log') -RedirectStandardError (Join-Path $logsDir 'frontend-err.log')
} catch {
    Stop-Process -Id $backendProcess.Id
    throw
}
@{backend_pid=$backendProcess.Id; frontend_pid=$frontendProcess.Id; url='http://localhost:5174'} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $logsDir 'processes.json') -Encoding utf8
Write-Output 'Demo: http://localhost:5174 (simulated payments, separate data)'
Write-Output "Backend PID $($backendProcess.Id); frontend PID $($frontendProcess.Id)"
