.PHONY: setup test lint run run-george report clean check

# Setup
setup:
	python -m venv .venv
	.venv/Scripts/pip install -r requirements-dev.txt

# Testing
test:
	python -m pytest tests/ -v --tb=short

test-cov:
	python -m pytest tests/ -v --tb=short --cov=engine --cov-report=term-missing

# Linting
lint:
	python -m ruff check engine/ main.py
	python -m ruff format --check engine/ main.py
	python -m mypy engine/ --ignore-missing-imports

format:
	python -m ruff check --fix engine/ main.py
	python -m ruff format engine/ main.py

# Run
run:
	python main.py --profile config/sample_input.yaml

run-george:
	python main.py --profile config/george_input.yaml

run-verbose:
	python main.py --profile config/sample_input.yaml --verbose

report:
	python main.py --profile config/sample_input.yaml
	@echo "Report: outputs/report.md"

# Quality gate (run before committing)
check: lint test
	@echo "All checks passed."

# Cleanup
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache htmlcov .mypy_cache .ruff_cache
