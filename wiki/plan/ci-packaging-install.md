# CI Packaging Install Plan

## Goal

Make the GitHub CI dependency install step deterministic for the repository's flat layout.

## Problem

`python -m pip install -e ".[dev]"` fails because setuptools auto-discovery sees multiple
top-level directories and refuses to infer which should be packaged.

## Decisions

- Explicitly include only the application packages: `backend` and `bot`.
- Keep `wiki`, `tests`, `scripts`, and `alembic` out of Python package discovery.
- Copy package directories before the Docker editable install so the image build follows the same
  packaging contract as CI.

## Acceptance Criteria

- `python -m pip install -e ".[dev]"` succeeds from a clean checkout.
- `ruff check .` and `pytest -q` still pass.
- Docker image build can install the project package after CI reaches the build job.
