"""Checkout input schema."""

import re

from pydantic import BaseModel, Field, field_validator


class CheckoutIn(BaseModel):
    contact: str = Field(min_length=5, max_length=255)
    address: str = Field(min_length=10, max_length=1000)
    note: str = Field(default="", max_length=1000)

    @field_validator("contact")
    @classmethod
    def _contact(cls, v: str) -> str:
        v = re.sub(r"\s+", " ", v).strip()
        if not (re.search(r"@", v) or re.search(r"[\d\+][\d\-\s\(\)]{6,}", v)):
            raise ValueError("Укажите email или телефон для связи")
        return v

    @field_validator("address")
    @classmethod
    def _address(cls, v: str) -> str:
        v = re.sub(r"[ \t]+", " ", v).strip()
        if len(v) < 10:
            raise ValueError("Адрес слишком короткий")
        return v
