# platform_errorhandling

Reusable platform package providing standardized logging and global error handling for FastAPI services.

This package ensures that unexpected backend failures are:

- logged consistently
- safe for users
- traceable via a request ID

It is intended to be shared across multiple applications in the system.

---

# Purpose

Applications should not implement their own global error handling patterns.

This package provides a shared platform capability that standardizes:

- request ID attachment
- exception logging
- safe API error responses
- consistent debugging behavior across services

The goal is **traceability without exposing internal details**.

---

# What This Package Provides

### Request ID Middleware

Each incoming request receives a unique `request_id`.

This ID:

- is attached to the request context
- appears in error responses
- appears in backend logs

This allows developers to correlate frontend-visible failures with backend logs.

---

### Global Exception Handler

Unhandled exceptions are caught and logged with a full traceback.

The response returned to the client is **safe and minimal**.

---

### API Error Responses

Requests to `/api/*` receive JSON error responses.

Example:

```json
{
  "error": "internal_error",
  "request_id": "a3d3c3d4-5b1b-42b7-aed0-89f71aefb53e",
  "message": "Unexpected error. Search logs for this request_id."
}

Fields:

Field	Meaning
error	stable machine-readable error key
request_id	backend trace identifier
message	safe message for users

No stack traces or internal information are exposed.

HTML Fallback

Non-API routes receive a minimal HTML error page containing the request ID.

This is intended only as a basic fallback for browser requests.

Logging Setup

The package provides a shared logging configuration:

rotating file logs

console logs

timestamped entries

full traceback for unhandled exceptions

Logs include enough context to debug production failures without exposing sensitive data.

Installation / Usage

Typical usage in a FastAPI application:

from pathlib import Path
from fastapi import FastAPI

from platform_errorhandling import setup_logging
from platform_errorhandling import install_exception_handlers

setup_logging("atlas", Path("./logs"))

app = FastAPI()

install_exception_handlers(app)

After installation:

all requests receive a request_id

all uncaught exceptions are logged

safe error responses are returned automatically

Application Responsibilities

Applications using this package should:

initialize logging during startup

install the shared exception handler

avoid implementing competing global error handling

surface request_id to users when an API call fails

Example frontend debug pattern:

API request failed
Request ID: 7e5d1c2a

Developers can then search backend logs for that ID.

Security Principles

Error responses must never expose:

stack traces

SQL queries

file paths

environment variables

tokens

passwords

internal configuration

Full diagnostic information belongs only in server logs.

What This Package Does NOT Do

This package does not handle:

frontend runtime errors

domain-specific exceptions

validation logic

authentication or authorization

alerting or monitoring systems

external services such as Sentry

Those concerns belong in other components.

Recommended Package Structure
platform_errorhandling/
├── __init__.py
├── logging_setup.py
└── fastapi_handlers.py

Responsibilities:

File	Responsibility
logging_setup.py	configure logging
fastapi_handlers.py	middleware and exception handlers