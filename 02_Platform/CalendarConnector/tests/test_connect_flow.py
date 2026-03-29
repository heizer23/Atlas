"""
Test stubs for OAuth connect start and callback flows.

Test scenarios (to be implemented by test_writer):
- connect_start: verify redirect URL contains correct scope (calendar.readonly),
  correct redirect_uri, and a state parameter; verify nonce row created in DB
- connect_callback: valid state and code -> connection and token rows persisted,
  nonce deleted, 200 returned
- connect_callback: missing or mismatched state -> OAUTH_STATE_MISMATCH error returned,
  no token exchange attempted
- connect_callback: expired nonce -> OAUTH_STATE_MISMATCH error returned
- connect_callback: Google token endpoint returns error -> api_error returned,
  no partial state persisted
"""
