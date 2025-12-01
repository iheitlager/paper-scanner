# Copyright 2025 Ilja Heitlager
# SPDX-License-Identifier: Apache-2.0
.ONESHELL:
SHELL := /bin/bash
VENV := .venv
PYTHON_VERSION := 3.14

.PHONY: help install install-dev test lint format type-check clean

version: ## Show project version
	@uv run python -c "import paper_scanner; print(f'paper-scanner version: {paper_scanner.__version__}')"

check: ## Verify required tooling is available
	@echo "Checking for required tools..."
	@command -v uv >/dev/null 2>&1 || { echo >&2 "✗ 'uv' is required but not installed. Please install it from https://github.com/astral-sh/uv"; exit 1; }
	@uv run ruff --version > /dev/null 2>&1 || { echo >&2 "✗ ruff is not installed"; exit 1; }
	@uv run mypy --version > /dev/null 2>&1 || { echo >&2 "✗ mypy is not installed"; exit 1; }
	@echo "✓ All required tools are installed"

env: ## Create and populate the development virtual environment
	@echo "✓ Setting up development environment with Python $(PYTHON_VERSION)..."
	uv venv $(VENV) --python $(PYTHON_VERSION) --clear > /dev/null
	@echo "✓ Virtual environment created at $(VENV)/"
	@uv sync > /dev/null
	@uv sync  --all-groups  > /dev/null
	@if [ ! -f uv.lock ]; then \
		echo "No uv.lock found, generating lock file..."; \
		uv lock; \
	fi
	env.sh
	@uv run python -c "import paper_scanner; print(f'paper-scanner version: {paper_scanner.__version__}')"
	@echo "To activate: source $(VENV)/bin/activate"

sync: ## Sync dependencies into the virtual environment
	@echo "Syncing dependencies into virtual environment..."
	uv sync > /dev/null
	uv sync --all-groups > /dev/null
	@echo "✓ Dependencies synced"

lock: ## Lock dependencies into uv.lock
	@echo "Locking dependencies..."
	uv lock

test: ## Run tests with coverage
	@echo "Running tests..."
	uv run pytest --cov=src/paper_scanner tests/

lint: ## Lint code with ruff
	@echo "Linting with ruff..."
	uv run ruff check src/ tests/

format: ## Format code with ruff
	@echo "Formatting with ruff..."
	uv run ruff check --fix src/ tests/
	uv run ruff format src/ tests/

type-check: ## Run type checks with mypy
	@echo "Type checking with mypy..."
	uv run mypy src/

clean: ## Clean up artifacts and caches
	@echo "Cleaning up..."
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name htmlcov -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete
	@find . -type f -name ".coverage" -delete
	@echo "✓ Cleaned"

.DEFAULT_GOAL := help

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' Makefile | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-16s\033[0m %s\n", $$1, $$2}'

