#!/bin/bash
# Initial project setup for contributors

set -e

echo "🔧 Setting up Polymarket Insider Tracker project..."
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3.10+ is required"
    exit 1
fi

# Create venv
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate and install
echo "📥 Installing dependencies..."
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q
pip install -r requirements-dev.txt -q

# Create .env
if [ ! -f ".env" ]; then
    echo "📝 Creating .env from template..."
    cp .env.example .env
fi

# Run linting
echo "🔍 Running code quality checks..."
ruff check src/
ruff format --check src/

echo ""
echo "✅ Setup complete!"
echo ""
echo "📝 Remember to:"
echo "  1. Edit .env with your settings"
echo "  2. Add your Slack webhook (optional)"
echo ""
echo "🚀 Run the tracker:"
echo "  python run.py"
echo ""
echo "💻 Development commands:"
echo "  make lint     # Check code"
echo "  make format   # Format code"
echo "  make run      # Start tracker"

