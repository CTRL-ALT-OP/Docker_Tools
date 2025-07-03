#!/bin/bash

echo "🚀 Codebase Validator"
echo "===================="

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running. Please start Docker first."
    exit 1
fi

echo "🐳 Docker is running!"
echo "🔒 Starting isolated Docker-in-Docker validation environment..."
echo ""
echo "📋 This will:"
echo "   Build a secure validation environment"
echo "   Start the web interface on http://localhost:8080"
echo "   Use Docker-in-Docker for complete Linux simulation"
echo "   Isolate all validation operations from host system"
echo ""

docker compose up --build 