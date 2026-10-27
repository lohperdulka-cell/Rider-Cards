"""Chat input schema."""

from pydantic import BaseModel, Field, field_validator


class MessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)

    @field_validator("text")
    @classmethod
    def _clean(cls, v: str) -> str:
        v = v.replace("\x00", "").strip()
        if not v:
            raise ValueError("Пустое сообщение")
        return v
