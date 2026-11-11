"""Every tunable constant of RunningTracker, declared once.

Metric constants (ACCURACY_MAX_M ... SERIES_BUCKET_S) have the same values in the Kotlin RunMetrics
(01_System/AtlasPhone); parity is enforced by tests/fixtures/metrics_golden.json.
"""

# Pairing (invariants S3, S4)
PAIRING_CODE_LENGTH = 8
PAIRING_CODE_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"  # 31 chars, no 0 O 1 I L
PAIRING_CODE_TTL_SECONDS = 300
PAIRING_MAX_FAILURES = 5
PAIRING_FAILURE_WINDOW_SECONDS = 300

# QR/text payload: "ATLASRUN1|<base_url>|<code>". The literal is repeated in src/pairingPayload.ts and Kotlin
# PairingPayload (three-place literal; each parser has a test).
PAIRING_QR_PREFIX = "ATLASRUN1"

# Prepared runs
PREPARED_RUN_TTL_HOURS = 48
SHORT_ID_LENGTH = 6  # same alphabet as pairing codes

# Native API limits
MAX_SAMPLES_PER_BATCH = 2000
MAX_BODY_BYTES = 2_000_000
DEVICE_LAST_USED_THROTTLE_SECONDS = 60

# Algorithm A1 (10_architecture.json invariants)
ALGO_VERSION = 1
ACCURACY_MAX_M = 30.0
MIN_STEP_M = 1.0
MAX_SPEED_MPS = 12.0
SMOOTHING_WINDOW_S = 10
SPLIT_DISTANCE_M = 1000.0
PARTIAL_SPLIT_MIN_M = 10.0
SERIES_BUCKET_S = 5

# Routes (geometry_version 1)
ROUTE_GEOMETRY_VERSION = 1
ROUTE_SIMPLIFY_TOLERANCE_M = 4.0   # Douglas-Peucker; about GPS noise
ROUTE_LOOP_MAX_GAP_M = 100.0       # start/end closer than this = loop
ROUTE_MIN_POINTS = 10

# Ghost profile / route progress (PROGRESS_ALGO_VERSION 2: idle start trimmed)
PROGRESS_ALGO_VERSION = 2
PROGRESS_OFF_COURSE_M = 50.0        # fix farther than this from the path is not matched (comparison qualified)
PROGRESS_BACK_TOLERANCE_M = 25.0    # GPS noise allowance behind the last progress
PROGRESS_FORWARD_SLACK_M = 40.0     # plus MAX_SPEED_MPS * seconds since last matched fix
PROGRESS_START_WINDOW_M = 250.0     # first match must be within this distance of the route start
PROGRESS_MIN_COVERAGE = 0.95        # run must reach this fraction of the reference distance to be a ghost
PROFILE_MIN_SPACING_S = 1.0         # profile point spacing in moving time
PROFILE_HR_MAX_AGE_S = 5.0          # nearest heart-rate reading must be this close in time, else null
IDLE_START_MIN_S = 10.0             # standing still at least this long at the start counts as idle and is trimmed
IDLE_START_MOVE_M = 5.0             # progress gained below this over the window still counts as standing still
IDLE_START_SEARCH_S = 15.0          # the standing-still window must begin within this many seconds of the start

# Web lists
DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100
