# Development convenience targets. Everything runs inside a project-local
# .venv — the system/stock Python is never modified.

PYTHON ?= python3
VENV := .venv
BIN := $(VENV)/bin

.PHONY: setup test lint run serve clean

$(BIN)/python:
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install --quiet --upgrade pip

setup: $(BIN)/python  ## Create .venv and install ragcli with dev + local extras
	$(BIN)/pip install -e ".[dev,local]"
	@echo ""
	@echo "Done. Activate with:  source $(VENV)/bin/activate"
	@echo "Or run directly:      $(BIN)/rag --help"

test: ## Run the test suite
	$(BIN)/pytest -q

lint: ## Lint and auto-fix
	$(BIN)/ruff check . --fix

run: ## Show the CLI help
	$(BIN)/rag

serve: ## Start the API server + web UI
	$(BIN)/rag serve

clean: ## Remove the venv and build artifacts
	rm -rf $(VENV) dist build *.egg-info
