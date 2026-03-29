"""
Test stubs for GET /api/calendar/status endpoint.

Test scenarios (to be implemented by test_writer):
- status: no connection record -> Dataset with single row status=not_connected returned
- status: connected record -> Dataset with status field, no access_token or
  refresh_token in response body
- all endpoints: verify no token values appear in any response body
"""
