$ErrorActionPreference = "Stop"

$RemoteUser = "root"
$RemoteHost = "145.223.93.162"
$RemoteProjectPath = "/var/www/site_inscricao"
$RemoteService = "site_inscricao"
$Branch = "main"

Set-Location (Resolve-Path "$PSScriptRoot\..")

Write-Host ""
Write-Host "Publicacao do site de inscricao" -ForegroundColor Cyan
Write-Host "Repositorio local: $(Get-Location)"
Write-Host "Servidor: $RemoteUser@$RemoteHost"
Write-Host "Projeto no servidor: $RemoteProjectPath"
Write-Host ""

$message = Read-Host "Mensagem do commit"
if ([string]::IsNullOrWhiteSpace($message)) {
    $message = "Atualizacao do site"
}

Write-Host ""
Write-Host "Verificando alteracoes locais..." -ForegroundColor Cyan
$changes = git status --porcelain

if ($changes) {
    git add -A
    git commit -m $message
} else {
    Write-Host "Nenhuma alteracao local para commitar."
}

Write-Host ""
Write-Host "Enviando para o GitHub..." -ForegroundColor Cyan
git push origin $Branch

$remoteCommand = @"
set -e
cd "$RemoteProjectPath"
git pull --ff-only origin "$Branch"
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
. .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate --noinput
python manage.py collectstatic --noinput
systemctl restart "$RemoteService"
systemctl status "$RemoteService" --no-pager
"@

$remoteCommand = $remoteCommand -replace "`r", ""

Write-Host ""
Write-Host "Atualizando a VPS..." -ForegroundColor Cyan
Write-Host "Se pedir senha, digite a senha root da VPS."
$remoteCommand | ssh "$RemoteUser@$RemoteHost" "bash -s"

Write-Host ""
Write-Host "Testando site em producao..." -ForegroundColor Cyan
try {
    $response = Invoke-WebRequest -Uri "https://xn--inscriaoandrews-jmb.com.br" -UseBasicParsing -Method Head -TimeoutSec 20
    Write-Host "Status HTTP: $($response.StatusCode)" -ForegroundColor Green
} catch {
    Write-Host "Nao consegui testar via HTTPS automaticamente: $($_.Exception.Message)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Publicacao finalizada." -ForegroundColor Green
