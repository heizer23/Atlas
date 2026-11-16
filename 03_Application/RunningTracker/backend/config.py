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
ALGO_VERSION = 3  # 3: cadence (Sprint03; no steps => cadence NULL, all else unchanged); 2: run_finished_at clipping + recovery object
ACCURACY_MAX_M = 30.0
MIN_STEP_M = 1.0
MAX_SPEED_MPS = 12.0
SMOOTHING_WINDOW_S = 10
SPLIT_DISTANCE_M = 1000.0
PARTIAL_SPLIT_MIN_M = 10.0
SERIES_BUCKET_S = 5

# Heart-rate validity HR1 and recovery HRR1 (same names/values in Kotlin HrConfig / RecoveryConfig;
# parity enforced by tests/fixtures/recovery_golden.json)
HR_VALID_MIN_BPM = 30
HR_VALID_MAX_BPM = 230
HR_SPIKE_MAX_BPM_PER_S = 40.0
HRR_END_BEFORE_S = 3.0
HRR_END_AFTER_S = 2.0
HRR_POINT_HALF_WINDOW_S = 3.0
HRR_MIN_VALID_SAMPLES = 2
HRR_T1_S = 60.0
HRR_T2_S = 120.0
RECOVERY_CURVE_STEP_S = 5.0
RECOVERY_CURVE_WINDOW_S = 5.0

# Cadence CAD1 (same CAD_* names/values in Kotlin CadenceConfig; parity enforced by tests/fixtures/cadence_golden.json)
CADENCE_ALGO_VERSION = 1
CAD_MIN_SPM = 100.0           # plausible running cadence lower bound; interval upper bound = 60 / CAD_MIN_SPM
CAD_MAX_SPM = 230.0           # interval lower bound = 60 / CAD_MAX_SPM
CAD_WINDOW_N = 8
CAD_MIN_INTERVALS = 4
CAD_NORMAL_TOL = 0.25
CAD_MISSED_TOL = 0.15
CAD_GAP_FACTOR = 2.5
CAD_GAP_S = 2.0
CAD_REANCHOR_IRREGULAR = 6
CAD_SERIES_STEP_S = 5.0       # equals SERIES_BUCKET_S: same x axis as the pace/HR series
CAD_PROFILE_MIN_CONF = 0.3
CAD_PROFILE_MAX_AGE_S = 5.0
CAD_PROGRESS_BUCKET_M = 20.0

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

# Ghost Coach (Sprint04; invariants CO1, EGR1, KEY1, PAY1, PROF1, PLAN1, OUT1 in Sprint04_GhostCoach/10_architecture.json)
COACH_CONSENT_VERSION = 1  # bump when COACH_PAYLOAD_VERSION, COACH_ALLOWED_HOSTS or the EGR1 data categories change
COACH_PAYLOAD_VERSION = 1
COACH_PLAN_SCHEMA_VERSION = 1
COACH_PROMPT_VERSION_DEFAULT = "v1"  # file backend/prompts/coach_prompt_<version>.md; env override must match ^v[0-9]+$
COACH_API_URL_DEFAULT = "https://api.anthropic.com/v1/messages"
COACH_ALLOWED_HOSTS = ("api.anthropic.com",)  # changing it is a code change plus a COACH_CONSENT_VERSION bump
COACH_MAX_TOKENS = 1500
COACH_HTTP_TIMEOUT_S = 60.0
COACH_MAX_CALLS_PER_DAY = 10  # attempts in the last 24 h (server clock)
COACH_HISTORY_RUNS = 10
COACH_MIN_RUN_S = 300.0  # moving time below this is RUN_NOT_ANALYSABLE
COACH_SERIES_STEP_S = 60  # payload series bucket
COACH_MAX_PAYLOAD_BYTES = 60000
COACH_MEASURED_WINDOW_RUNS = 10
COACH_PACE_MATCH_TOL = 0.10
COACH_HR_PACE_MIN_RUNS = 3
COACH_MIN_RUNS_INFERRED = 3
COACH_MEASURED_KEYS = ("natural_cadence_spm", "avg_step_length_m", "hr_at_median_pace_bpm", "runs_per_week",
                       "km_per_week", "pr_fastest_1k_s", "pr_longest_run_m")
COACH_INFERRED_KEYS = ("aerobic_endurance", "fatigue_drift", "development_trend")
COACH_PLAN_TYPES = ("easy_continuous", "hr_controlled", "recovery", "endurance", "interval")
COACH_SEGMENT_KINDS = ("warmup", "steady", "work", "recovery", "cooldown")
COACH_TRIGGERS = ("hr_high", "hr_low", "pace_fast", "pace_slow", "cadence_low", "cadence_high",
                  "segment_change", "keep_rhythm", "sensor_lost")
COACH_HR_BOUNDS = (60, 200)  # bpm
COACH_PACE_BOUNDS_S_PER_KM = (180, 900)
COACH_MIN_RANGE_HR = 6  # bpm
COACH_MIN_RANGE_PACE = 10  # s/km
COACH_MIN_RANGE_CAD = 4  # spm; cadence bounds reuse CAD_MIN_SPM / CAD_MAX_SPM
COACH_MAX_SEGMENTS = 40
COACH_MIN_SEGMENT_S = 20
COACH_MIN_PLAN_S = 300
COACH_MAX_PLAN_S = 10800
COACH_INTERVAL_LOOKBACK_PLANS = 2
COACH_OUTCOME_COMPLETED_FRACTION = 0.9
COACH_PLAN_LIST_DEFAULT = 20
COACH_PLAN_LIST_MAX = 50
