# CLAUDE.md

## Purpose

Reusable platform package for FastAPI error handling and logging.

## Classification

This package is Platform, not Application.
It provides a shared technical capability and must contain no domain logic.

## Responsibilities

- attach a per-request `request_id`
- log unhandled exceptions with traceback
- return safe JSON errors for `/api/*`
- return simple HTML fallback for non-API routes
- provide shared logging setup
- log request duration for every HTTP request
- provide a timed block context manager for operation-level timing
- provide `api_error()` for consistent error response envelopes

## Rules

- keep implementation small, explicit, and reusable
- use Python stdlib logging unless a clear reason exists otherwise
- never leak traceback, secrets, SQL, tokens, or internal paths in responses
- keep the public API small and stable
- do not add app-specific exception behavior here
- do not add frontend runtime error capture here
- `install_request_timing` should be called after `install_exception_handlers` so `request_id` is available on `request.state`
## Public API

- `setup_logging(app_name, log_dir)`
- `install_exception_handlers(app)`
- `install_request_timing(app)`
- `timed_block(logger, block_name, request_id="n/a")`
- `api_error(code, message, detail=None, status=400)`