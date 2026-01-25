# TradingAgents-CN 后端启动脚本 (Windows PowerShell)
# 启动FastAPI后端服务，使前端可以访问API接口

param(
    [switch]$NoClean = $false,
    [switch]$ForceClean = $false,
    [switch]$Help = $false
)

function Print-Help {
    Write-Host "TradingAgents-CN 后端启动脚本" -ForegroundColor Cyan
    Write-Host "================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "用法: .\start_backend.ps1 [选项]" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "选项:" -ForegroundColor Yellow
    Write-Host "  -Help              显示帮助信息"
    Write-Host "  -NoClean           跳过缓存清理"
    Write-Host "  -ForceClean        强制清理所有缓存"
    Write-Host ""
    Write-Host "示例:" -ForegroundColor Yellow
    Write-Host "  .\start_backend.ps1              # 正常启动"
    Write-Host "  .\start_backend.ps1 -NoClean     # 跳过缓存清理启动"
    Write-Host ""
}

if ($Help) {
    Print-Help
    exit 0
}

# 获取脚本所在目录
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║     TradingAgents-CN 后端启动脚本                                  ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# 检查Python环境
Write-Host "🔍 检查Python环境..." -ForegroundColor Yellow
$python = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ 未找到Python环境" -ForegroundColor Red
    Write-Host "请确保Python已安装并添加到PATH中" -ForegroundColor Red
    exit 1
}
Write-Host "✅ Python环境检查通过: $python" -ForegroundColor Green

# 检查虚拟环境
Write-Host ""
Write-Host "🔍 检查虚拟环境..." -ForegroundColor Yellow
if (Test-Path ".venv/Scripts/Activate.ps1") {
    Write-Host "✅ 虚拟环境已存在，激活中..." -ForegroundColor Green
    & ".venv/Scripts/Activate.ps1"
    Write-Host "✅ 虚拟环境已激活" -ForegroundColor Green
} else {
    Write-Host "⚠️  虚拟环境不存在" -ForegroundColor Yellow
    Write-Host "请先运行: python -m venv .venv" -ForegroundColor Yellow
    exit 1
}

# 检查依赖
Write-Host ""
Write-Host "🔍 检查依赖包..." -ForegroundColor Yellow
$fastapi = python -c "import fastapi; print('OK')" 2>&1
$uvicorn = python -c "import uvicorn; print('OK')" 2>&1
$motor = python -c "import motor; print('OK')" 2>&1
$redis = python -c "import redis; print('OK')" 2>&1

$missing = @()
if ($fastapi -ne "OK") { $missing += "fastapi" }
if ($uvicorn -ne "OK") { $missing += "uvicorn" }
if ($motor -ne "OK") { $missing += "motor" }
if ($redis -ne "OK") { $missing += "redis" }

if ($missing.Count -gt 0) {
    Write-Host "❌ 缺少以下依赖包: $($missing -join ', ')" -ForegroundColor Red
    Write-Host "请运行: pip install -r requirements.txt" -ForegroundColor Yellow
    exit 1
}
Write-Host "✅ 依赖包检查通过" -ForegroundColor Green

# 检查.env文件
Write-Host ""
Write-Host "🔍 检查配置文件..." -ForegroundColor Yellow
if (Test-Path ".env") {
    Write-Host "✅ 已找到.env配置文件" -ForegroundColor Green
} else {
    Write-Host "⚠️  .env文件不存在" -ForegroundColor Yellow
    Write-Host "   正在从.env.example创建.env文件..." -ForegroundColor Yellow
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Host "✅ .env文件已创建，请编辑并填入真实配置" -ForegroundColor Green
    } else {
        Write-Host "❌ .env.example文件不存在" -ForegroundColor Red
        exit 1
    }
}

# 检查MongoDB和Redis服务
Write-Host ""
Write-Host "🔍 检查MongoDB和Redis服务..." -ForegroundColor Yellow

# 检查MongoDB
try {
    $mongoTest = & mongosh --eval "db.adminCommand('ping')" --quiet 2>&1
    if ($?) {
        Write-Host "✅ MongoDB 服务运行正常" -ForegroundColor Green
    } else {
        Write-Host "⚠️  MongoDB 连接失败，请确保MongoDB服务已启动" -ForegroundColor Yellow
        Write-Host "   启动MongoDB: mongod" -ForegroundColor Yellow
    }
} catch {
    Write-Host "⚠️  MongoDB 检查出错，请确保已安装并启动" -ForegroundColor Yellow
    Write-Host "   启动MongoDB: mongod" -ForegroundColor Yellow
}

# 检查Redis
try {
    $redisTest = & redis-cli ping 2>&1
    if ($redisTest -eq "PONG") {
        Write-Host "✅ Redis 服务运行正常" -ForegroundColor Green
    } else {
        Write-Host "⚠️  Redis 连接失败，请确保Redis服务已启动" -ForegroundColor Yellow
        Write-Host "   启动Redis: redis-server" -ForegroundColor Yellow
    }
} catch {
    Write-Host "⚠️  Redis 检查出错，请确保已安装并启动" -ForegroundColor Yellow
    Write-Host "   启动Redis: redis-server" -ForegroundColor Yellow
}

# 清理缓存（可选）
if (-not $NoClean -and -not $ForceClean) {
    Write-Host ""
    Write-Host "🧹 清理项目缓存..." -ForegroundColor Yellow
    Get-ChildItem -Path . -Include "__pycache__" -Recurse -Directory | Remove-Item -Recurse -Force
    Write-Host "✅ 缓存清理完成" -ForegroundColor Green
}

# 启动FastAPI应用
Write-Host ""
Write-Host "🚀 启动FastAPI后端服务..." -ForegroundColor Cyan
Write-Host ""
Write-Host "📝 服务信息:" -ForegroundColor Cyan
Write-Host "   API 地址: http://localhost:8000" -ForegroundColor Cyan
Write-Host "   API 文档: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "   WebSocket: ws://localhost:8000" -ForegroundColor Cyan
Write-Host ""
Write-Host "⏹️  按 Ctrl+C 停止服务" -ForegroundColor Yellow
Write-Host ""

# 启动服务
$env:PYTHONUNBUFFERED = "1"
python -m uvicorn app.main:app `
    --host 0.0.0.0 `
    --port 8000 `
    --reload `
    --log-level info
