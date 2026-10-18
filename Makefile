.PHONY: install fmt lint typecheck test check

# Resolve uv even when ~/.local/bin (its default install dir) is not on PATH,
# e.g. in non-login shells, hooks, or editor-spawned processes. Override with `make UV=...`.
UV ?= $(shell command -v uv 2>/dev/null || echo $(HOME)/.local/bin/uv)

install:
	$(UV) sync

fmt:
	$(UV) run ruff format .
	$(UV) run ruff check --fix .

lint:
	$(UV) run ruff format --check .
	$(UV) run ruff check .

typecheck:
	$(UV) run mypy

test:
	$(UV) run pytest -m "not integration"

# Default local quality gate. It does not replace acceptance or integration checks.
check: lint typecheck test
