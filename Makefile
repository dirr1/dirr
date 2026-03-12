.PHONY: help install install-dev run scan stats clean lint format test

help:
	@echo "Polymarket Insider Tracker - Available Commands:"
	@echo ""
	@echo "  make install      - Install production dependencies"
	@echo "  make install-dev  - Install dev dependencies"
	@echo "  make run          - Run continuous monitoring"
	@echo "  make scan         - Run single scan"
	@echo "  make stats        - View statistics"
	@echo "  make lint         - Check code with ruff"
	@echo "  make format       - Format code with ruff"
	@echo "  make clean        - Remove cache and build files"
	@echo "  make test         - Run tests (when available)"

install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements-dev.txt

run:
	python run.py

scan:
	python run.py --mode scan

stats:
	python run.py --mode stats

lint:
	ruff check src/

format:
	ruff format src/
	ruff check --fix src/

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	rm -rf build/ dist/

test:
	pytest tests/ -v

