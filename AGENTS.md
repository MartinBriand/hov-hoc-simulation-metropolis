# Instructions

## Running Python

This project manages its Python environment with [uv](https://docs.astral.sh/uv/).

- Always run Python code through the project environment: `uv run python` (or
  `uv run <script>`), never a bare `python` / `python3` command.
- Use `uvx <tool>` when running development tools that are not project
  dependencies (formatters, linters, scrapers, etc.).
- Scripts in `scripts/` already have the `uv run` prefix.
- Do not use `from __future__ import annotations` — the project targets
  Python 3.14, so use the modern annotation syntax directly.
