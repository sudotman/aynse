.PHONY: help install dev test test-fast lint docs docs-serve clean build publish bump-patch bump-minor bump-major version

# Default target
help:
	@echo "Available commands:"
	@echo ""
	@echo "Development:"
	@echo "  install      Install package in development mode"
	@echo "  dev          Install with dev dependencies"
	@echo "  test         Run all tests"
	@echo "  test-fast    Run tests excluding slow/network tests"
	@echo "  lint         Run linters (mypy)"
	@echo "  clean        Remove build artifacts"
	@echo ""
	@echo "Documentation:"
	@echo "  docs         Build documentation"
	@echo "  docs-serve   Serve documentation locally"
	@echo ""
	@echo "Release:"
	@echo "  version      Show current version"
	@echo "  bump-patch   Bump patch version (1.0.0 -> 1.0.1)"
	@echo "  bump-minor   Bump minor version (1.0.0 -> 1.1.0)"
	@echo "  bump-major   Bump major version (1.0.0 -> 2.0.0)"
	@echo "  build        Build distribution packages"
	@echo "  publish      Publish to PyPI (requires TWINE credentials)"

# Development
install:
	pip install -e .

dev:
	pip install -e .
	pip install -r requirements.dev.txt

test:
	pytest tests/ -v

test-fast:
	pytest tests/ -v --ignore=tests/test_nse.py --ignore=tests/test_nse_live.py --ignore=tests/test_bhav.py --ignore=tests/test_rbi.py

lint:
	mypy aynse --ignore-missing-imports

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf site/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Documentation
docs:
	mkdocs build --strict

docs-serve:
	mkdocs serve

# Release
version:
	@python scripts/bump_version.py --current

bump-patch:
	python scripts/bump_version.py patch

bump-minor:
	python scripts/bump_version.py minor

bump-major:
	python scripts/bump_version.py major

build: clean
	python -m build

publish: build
	twine check dist/*
	twine upload dist/*

