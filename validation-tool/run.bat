@echo off
echo 🚀 Codebase Validator
echo ====================

:: Check if Docker is running
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Error: Docker is not running. Please start Docker first.
    exit /b 1
)

echo 🐳 Docker is running!
echo 🔒 Starting isolated Docker-in-Docker validation environment...
echo.
echo 📋 This will:
echo    Build a secure validation environment
echo    Start the web interface on http://localhost:8080
echo    Use Docker-in-Docker for complete Linux simulation
echo    Isolate all validation operations from host system
echo.

docker compose up --build 