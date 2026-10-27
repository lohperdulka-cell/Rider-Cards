.DEFAULT_GOAL := help
PY := .venv/bin/python
PIP := uv pip install --python $(PY)

.PHONY: help venv install dev run migrate migration seed create-admin test e2e lint fmt type audit css css-watch check shell clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

venv: ## Create the virtualenv
	uv venv --python 3.13 .venv

install: ## Install runtime and dev dependencies
	$(PIP) -e ".[dev]"

dev: ## Run the dev server with autoreload on :8000
	$(PY) -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

run: ## Run the server without reload
	$(PY) -m uvicorn app.main:app --host 0.0.0.0 --port 8000

migrate: ## Apply Alembic migrations
	$(PY) -m alembic upgrade head

migration: ## Autogenerate a migration: make migration m="add x"
	$(PY) -m alembic revision --autogenerate -m "$(m)"

seed: ## Load the demo catalogue, news and admin user
	$(PY) -m app.scripts.seed

create-admin: ## Create or reset the admin account from .env
	$(PY) -m app.scripts.create_admin

test: ## Run the pytest suite
	$(PY) -m pytest -q

e2e: ## Run the Playwright end-to-end tests
	$(PY) -m pytest tests/e2e -q

lint: ## Ruff lint
	$(PY) -m ruff check app tests

fmt: ## Ruff autofix and format
	$(PY) -m ruff check --fix app tests && $(PY) -m ruff format app tests

type: ## mypy type check
	$(PY) -m mypy app

audit: ## Dependency vulnerability audit (pip-audit)
	$(PY) -m pip_audit

css: ## Build Tailwind CSS once (minified)
	npx --yes tailwindcss@3.4.17 -c tailwind.config.js -i app/static/css/tailwind.src.css -o app/static/css/app.css --minify

css-watch: ## Rebuild Tailwind CSS on change
	npx --yes tailwindcss@3.4.17 -c tailwind.config.js -i app/static/css/tailwind.src.css -o app/static/css/app.css --watch

check: lint type test ## Everything CI would run

shell: ## Python REPL with the app importable
	$(PY) -c "from app.db.session import session_scope; print('session_scope ready')"

clean: ## Remove caches
	rm -rf .pytest_cache .ruff_cache .mypy_cache
