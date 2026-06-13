# pixbridge justfile

default:
    @just --list

[doc("Install dependencies")]
build:
    uv sync

[doc("Run tests")]
test:
    uv run pytest tests/

[doc("Run live provider tests (hits real APIs; needs API keys set)")]
test-live:
    uv run pytest tests/ -m live -v

[doc("Run tests with coverage reporting")]
coverage:
    uv run pytest --cov=src/pixbridge --cov-report=term --cov-report=html tests/

[doc("Lint with ruff")]
lint:
    uv run ruff check src/ tests/

[doc("Auto-fix lint issues and format")]
fix:
    uv run ruff check --fix src/ tests/
    uv run ruff format src/ tests/

[doc("Type-check with mypy")]
typecheck:
    uv run mypy src/pixbridge

[doc("Run all checks: lint, typecheck, test")]
check: lint typecheck test

[group("pixbridge")]
[doc("Run the pixbridge command with the provided arguments")]
pixbridge *ARGS:
     @uv run pixbridge {{ARGS}}
