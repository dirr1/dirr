#!/bin/bash
# Quick install script for Polymarket Insider Tracker

echo "🚀 Installing Polymarket Insider Tracker..."
echo ""

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not found"
    exit 1
fi

# Check Python version is 3.10+
python_version=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
required_version="3.10"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then 
    echo "❌ Python 3.10+ is required. Found: $python_version"
    exit 1
fi

# Create venv if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate venv
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

# Create .env if it doesn't exist
if [ ! -f ".env" ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "⚠️  Please edit .env file with your settings!"
fi

echo ""
echo "✅ Installation complete!"
echo ""
echo "📝 Next steps:"
echo "  1. Edit .env file with your Slack webhook (optional)"
echo "  2. source venv/bin/activate"
echo "  3. python run.py"
echo ""
echo "💡 Other commands:"
echo "  python run.py --mode scan   # Single scan"
echo "  python run.py --mode stats  # View statistics"
echo "  python run.py --debug       # Debug mode"
echo ""
echo "📚 See README.md for full documentation"
