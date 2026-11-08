from typing import Literal
from pydantic import BaseModel, EmailStr, Field, ConfigDict


class Register(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)


class Login(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class User(BaseModel):
    id: str
    name: str
    email: str
    role: Literal["investigator"] = "investigator"


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 1800
    user: User


class Evidence(BaseModel):
    id: str
    filename: str
    sha256: str
    size_bytes: int
    width: int
    height: int
    media_type: str
    created_at: str
    status: Literal["uploaded"]


class AnalyzeRequest(BaseModel):
    evidence_id: str = Field(min_length=1, max_length=64)


class CaseCreate(BaseModel):
    title: str = Field(min_length=3, max_length=150)
    description: str = Field(default="", max_length=2000)


class CaseAnalysisAdd(BaseModel):
    analysis_id: str = Field(min_length=1, max_length=64)


class CaseStatusUpdate(BaseModel):
    status: Literal["open", "closed"]
