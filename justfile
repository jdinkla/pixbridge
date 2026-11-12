# pixbridge justfile

# Models the live tests run against: the newest cheap/fast model per provider,
# since these are API integration tests. Configuration, not secrets: kept here
# rather than in .envrc. Override per run via the environment, e.g.
# `PIXBRIDGE_LIVE_OPENAI_MODEL=gpt-image-2.6-sunburst just test-live`.
export PIXBRIDGE_LIVE_GEMINI_MODEL := env("PIXBRIDGE_LIVE_GEMINI_MODEL", "gemini-3.1-flash-lite-image")
export PIXBRIDGE_LIVE_OPENAI_MODEL := env("PIXBRIDGE_LIVE_OPENAI_MODEL", "gpt-image-2.6-flare")
export PIXBRIDGE_LIVE_XAI_MODEL := env("PIXBRIDGE_LIVE_XAI_MODEL", "grok-imagine-image-2.0")

default:
    @just --list

[doc("Install dependencies")]
build:
    uv sync

[doc("Run tests")]
test:
    uv run pytest tests/

[doc("Run live provider tests (hits real APIs; needs API keys set; models are set at the top of this justfile; images land in output/live/; extra args go to pytest, e.g. `just test-live -k gemini`)")]
test-live *ARGS:
    uv run pytest tests/ -m live -v -rs {{ARGS}}

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
