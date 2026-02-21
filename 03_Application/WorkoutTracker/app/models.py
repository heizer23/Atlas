from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import date
import uuid

class WorkoutLogCreate(BaseModel):
    workout_date: date
    split: str = Field(..., min_length=1)
    exercise: str = Field(..., min_length=1)
    weight_kg: Optional[float] = Field(None, ge=0)
    pause_sec: Optional[int] = Field(None, ge=0)
    set1_reps: Optional[int] = Field(None, ge=0)
    set2_reps: Optional[int] = Field(None, ge=0)
    set3_reps: Optional[int] = Field(None, ge=0)
    set4_reps: Optional[int] = Field(None, ge=0)
    set5_reps: Optional[int] = Field(None, ge=0)
    comment: Optional[str] = None
    workout_id: Optional[uuid.UUID] = None  # Passed from form or generated

    @field_validator('set1_reps', 'set2_reps', 'set3_reps', 'set4_reps', 'set5_reps')
    @classmethod
    def validate_reps(cls, v):
        return v
