"""Wire records for the native endpoints and the web mutation bodies. Extra keys are forbidden on request models."""

from datetime import datetime
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from backend.config import MAX_SAMPLES_PER_BATCH


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StreamCounts(_Strict):
    location: int = Field(0, ge=0)
    heart_rate: int = Field(0, ge=0)


DeviceName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]


class PairRequest(_Strict):
    code: str = Field(min_length=1, max_length=64)
    device_name: DeviceName


class PairResponse(BaseModel):
    device_id: str
    device_token: str
    device_name: str


class PreparedRunOut(BaseModel):
    id: str
    short_id: str
    run_type: str
    title: Optional[str] = None
    planned_for: Optional[datetime] = None
    expires_at: datetime
    route_id: Optional[str] = None
    ghost_run_id: Optional[str] = None


class PreparedRunList(BaseModel):
    prepared_runs: list[PreparedRunOut]


class PreparedRunCreate(_Strict):
    title: Optional[str] = Field(None, max_length=120)
    planned_for: Optional[datetime] = None
    route_id: Optional[str] = None
    # none | latest | fastest | <run uuid>; resolved to a concrete run when the run is prepared. Needs route_id.
    ghost: str = "none"


class BeginRequest(_Strict):
    run_type: Literal["continuous"] = "continuous"
    started_at: datetime


class BeginResponse(BaseModel):
    run_id: str
    status: str
    high_seq: StreamCounts
    contiguous_seq: int


class SampleIn(_Strict):
    stream: Literal["location", "heart_rate"]
    seq: int = Field(ge=1)
    payload: dict

    @field_validator("payload")
    @classmethod
    def _payload_has_timestamp(cls, v: dict) -> dict:
        parse_sample_ts(v)  # raises ValueError -> 422
        return v


def parse_sample_ts(payload: dict) -> datetime:
    """payload.timestamp (ISO-8601 UTC) -> aware datetime. ValueError when missing/unparsable/naive."""
    raw = payload.get("timestamp")
    if not isinstance(raw, str):
        raise ValueError("payload.timestamp must be an ISO-8601 string")
    ts = datetime.fromisoformat(raw)  # accepts the trailing 'Z' on Python >= 3.11
    if ts.tzinfo is None:
        raise ValueError("payload.timestamp must carry a UTC offset")
    return ts


class SamplesBatch(_Strict):
    samples: list[SampleIn] = Field(min_length=1, max_length=MAX_SAMPLES_PER_BATCH)


class SamplesResponse(BaseModel):
    stored: int
    duplicates: int
    high_seq: StreamCounts
    contiguous_seq: int


class PauseIn(_Strict):
    started_at: datetime
    ended_at: datetime
    started_elapsed_s: float = Field(ge=0)
    ended_elapsed_s: float

    @model_validator(mode="after")
    def _ordered(self) -> "PauseIn":
        if self.ended_at < self.started_at or self.ended_elapsed_s < self.started_elapsed_s:
            raise ValueError("pause must end after it started")
        return self


class FinishRequest(_Strict):
    finished_at: datetime
    elapsed_s: float = Field(ge=0)
    moving_s: float = Field(ge=0)
    distance_m: float = Field(ge=0)
    last_seq: int = Field(ge=0)
    expected_counts: StreamCounts
    pauses: list[PauseIn] = Field(default_factory=list, max_length=1000)
    dropped: int = Field(0, ge=0)


class SeqRange(BaseModel):
    start: int
    end: int


class CountMismatch(BaseModel):
    stream: str
    expected: int
    stored: int


class FinishResponse(BaseModel):
    result: Literal["complete", "incomplete"]
    run_id: str
    verified_counts: StreamCounts
    missing_seq_ranges: list[SeqRange]
    count_mismatch: list[CountMismatch]
    high_seq: StreamCounts
    contiguous_seq: int


class RunPatch(_Strict):
    """PATCH body (U1): use model_fields_set to tell an omitted comment from an explicit null."""
    comment: Optional[str] = Field(None, max_length=2000)
    category: Optional[str] = Field(None, max_length=60)
    route_id: Optional[str] = None  # null = unlink; omitted = unchanged


class RouteCreate(_Strict):
    run_id: str
    name: str = Field(min_length=1, max_length=120)
    description: Optional[str] = Field(None, max_length=2000)


class RoutePatch(_Strict):
    """name: omitted = unchanged, null rejected (a route needs a name); description: omitted/null/string as for comments."""
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    description: Optional[str] = Field(None, max_length=2000)
