"""Support form schema."""

import re

from pydantic import BaseModel, EmailStr, Field, field_validator


class SupportIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    subject: str = Field(min_length=3, max_length=240)
    message: str = Field(min_length=10, max_length=4000)

    @field_validator("name", "subject")
    @classmethod
    def _collapse(cls, v: str) -> str:
        return re.sub(r"\s+", " ", v).strip()
