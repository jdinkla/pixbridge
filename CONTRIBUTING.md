# Contributing to pixbridge

Thanks for your interest in contributing. This project is a small, unified
multi-provider image generation library; contributions that keep the provider
surface consistent are especially welcome.

## Development setup

```bash
uv sync          # install dependencies into .venv
just test        # run the offline test suite
just check       # lint + type-check + test (run this before opening a PR)
```

If you don't use [`just`](https://github.com/casey/just), the underlying
commands are:

```bash
uv run ruff check src/ tests/
uv run mypy src/pixbridge
uv run pytest tests/
```

## Provider API keys

Generation calls need provider credentials. Copy the example env file and fill
in your own keys (the real `.envrc` is gitignored):

```bash
cp .envrc.example .envrc   # then edit with your keys
```

Live provider tests are opt-in and hit real APIs (and cost money):

```bash
just test-live
```

## Pull requests

- Keep the change focused; one logical change per PR.
- Add or update tests for any behaviour change. The suite runs offline with
  mocked SDKs — new code should too unless it is explicitly a `live` test.
- Run `just check` locally; CI runs the same on Python 3.11, 3.12, and 3.13.
- Update `CHANGELOG.md` under an `Unreleased` heading.
- When adding a provider or capability, keep the `ProviderCapabilities` surface
  uniform (see the capability table in the README) so callers don't have to
  branch on provider name.

## Reporting bugs

Open an issue with a minimal reproduction: the provider, model, prompt/size,
and the full error. Please redact API keys.

## License

By contributing, you agree that your contributions will be licensed under the
[Apache License 2.0](LICENSE), the same license that covers this project.
