.PHONY: help venv-create venv-activate venv-deactivate install install-dev test coverage lint format type-check clean docker-build docker-up docker-down

help:
	@echo "Minions Army - Development Commands"
	@echo "===================================="
	@echo "make venv-create       Create Python virtual environment"
	@echo "make venv-activate     Open an activated PowerShell session"
	@echo "make venv-deactivate   Show how to deactivate virtual environment"
	@echo "make install           Install dependencies"
	@echo "make install-dev       Install dev dependencies"
	@echo "make test              Run tests"
	@echo "make coverage          Run tests with coverage"
	@echo "make lint              Run linting (ruff)"
	@echo "make format            Format code (black)"
	@echo "make type-check        Run type checking (mypy)"
	@echo "make check             Run all code quality checks"
	@echo "make clean             Clean up generated files"
	@echo "make docker-build      Build API and minion Docker images"
	@echo "make docker-up         Start Docker containers"
	@echo "make docker-down       Stop Docker containers"
	@echo "make dev               Start development server with hot reload"

venv-create:
	python -m venv .venv

venv-activate:
	powershell -NoExit -ExecutionPolicy Bypass -Command "& .\.venv\Scripts\Activate.ps1"

venv-deactivate:
	@echo "Run this command in the activated terminal:"
	@echo "deactivate"

install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements-dev.txt

test:
	pytest

coverage:
	pytest --cov=minions_army --cov-report=html --cov-report=term

lint:
	ruff check minions_army tests

format:
	black minions_army tests

type-check:
	mypy minions_army

check: format lint type-check test

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	rm -rf htmlcov
	rm -rf .coverage
	rm -rf .ruff_cache
	rm -rf build
	rm -rf dist

docker-build:
	docker-compose build

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

dev:
	uvicorn minions_army.infrastructure.api.fastapi_app:app --reload --host 0.0.0.0 --port 8000
