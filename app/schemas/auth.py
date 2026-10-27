"""Auth and profile input schemas."""

import re

from pydantic import BaseModel, EmailStr, Field, field_validator

PASSWORD_MIN = 8


class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=PASSWORD_MIN, max_length=128)
    password_confirm: str = Field(min_length=PASSWORD_MIN, max_length=128)

    @field_validator("name")
    @classmethod
    def _clean_name(cls, v: str) -> str:
        v = re.sub(r"\s+", " ", v).strip()
        if len(v) < 2:
            raise ValueError("Имя слишком короткое")
        return v

    @field_validator("password")
    @classmethod
    def _strong_enough(cls, v: str) -> str:
        if v.strip() != v:
            raise ValueError("Пароль не должен начинаться или заканчиваться пробелом")
        if not re.search(r"[A-Za-zА-Яа-я]", v) or not re.search(r"\d", v):
            raise ValueError("Пароль должен содержать буквы и цифры")
        return v

    def validate_match(self) -> bool:
        return self.password == self.password_confirm


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    next: str = Field(default="/", max_length=512)


class ProfileUpdateIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    locale: str = Field(default="ru", max_length=5)


class PasswordChangeIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=PASSWORD_MIN, max_length=128)
    new_password_confirm: str = Field(min_length=PASSWORD_MIN, max_length=128)
