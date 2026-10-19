from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    species: Literal["dog", "cat", "other"]
    breed: str | None = Field(default=None, max_length=50)
    birthday: date | None = None
    gender: Literal["male", "female", "unknown"] = "unknown"
    neutered: bool = False
    allergies: str | None = None
    notes: str | None = None
    photo_url: str | None = Field(default=None, max_length=255)


class PetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    species: Literal["dog", "cat", "other"] | None = None
    breed: str | None = Field(default=None, max_length=50)
    birthday: date | None = None
    gender: Literal["male", "female", "unknown"] | None = None
    neutered: bool | None = None
    allergies: str | None = None
    notes: str | None = None
    photo_url: str | None = Field(default=None, max_length=255)


class PetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    name: str
    species: str
    breed: str | None = None
    birthday: date | None = None
    gender: str | None = None
    neutered: bool
    allergies: str | None = None
    notes: str | None = None
    photo_url: str | None = None
    status: str
    create_time: datetime | None = None


class WeightCreate(BaseModel):
    record_date: date
    weight_kg: float = Field(gt=0, le=200)
    note: str | None = None


class WeightResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    pet_id: int
    record_date: date
    weight_kg: float
    note: str | None = None
