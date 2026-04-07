# Contributing

## Local setup

1. Create a virtual environment with Python 3.11 or newer.
2. Install the project in editable mode:

```bash
pip install -e .[dev]
```

3. Copy `.env.example` to `.env` and adjust values if needed.

## Development workflow

1. Run the test suite before submitting changes:

```bash
pytest
```

2. Keep changes focused and documented.
3. If you change configuration or setup steps, update `README.md`.

## Pull requests

- Explain the motivation for the change.
- Include test coverage when behavior changes.
- Avoid committing `.venv`, local caches, or machine-specific files.
