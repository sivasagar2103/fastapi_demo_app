
from enum import Enum
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

class Role(str, Enum):
    platform_admin = "platform_admin"
    tenant_admin = "tenant_admin"
    organization_admin = "organization_admin"
    viewer = "viewer"

class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

class PasswordInput(Input):
    @field_validator("password", check_fields=False)
    @classmethod
    def validate_password_bytes(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must not exceed 72 UTF-8 bytes")
        return value

class TenantCreate(Input):
    name: str = Field(min_length=1, max_length=120)

class OrganizationCreate(TenantCreate):
    tenant_id: str

class UserCreate(PasswordInput):
    username: str = Field(min_length=3, max_length=100, pattern=r"^[a-z0-9_.@-]+$")
    password: Annotated[str, StringConstraints(strip_whitespace=False, min_length=12, max_length=128)]
    role: Role = Role.viewer
    tenant_id: str | None = None
    organization_id: str | None = None

class EmployeeCreate(Input):
    organization_id: str
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    job_title: str = Field(default="", max_length=120)

class GroupCreate(Input):
    organization_id: str
    name: str = Field(min_length=1, max_length=120)

class Rename(Input):
    name: str = Field(min_length=1, max_length=120)

class EmployeeUpdate(Rename):
    email: str = Field(min_length=3, max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    job_title: str = Field(default="", max_length=120)

class UserUpdate(Input):
    active: bool

class Record(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    created_at: str

class TenantOut(Record):
    name: str

class OrganizationOut(TenantOut):
    tenant_id: str

class UserOut(Record):
    username: str
    role: Role
    tenant_id: str | None
    organization_id: str | None
    active: bool

class EmployeeOut(Record):
    tenant_id: str
    organization_id: str
    name: str
    email: str
    job_title: str

class GroupOut(Record):
    tenant_id: str
    organization_id: str
    name: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserRegistration(PasswordInput):
    username: str = Field(min_length=3, max_length=100, pattern=r"^[a-z0-9_.@-]+$")
    role: Literal["tenant_admin", "organization_admin", "viewer"] = "tenant_admin"
    # Preserve password whitespace; do not silently normalize credentials.
    password: Annotated[str, StringConstraints(strip_whitespace=False, min_length=12, max_length=128)]
    tenant_name: str | None = Field(default=None, min_length=1, max_length=120)

class UserLogin(Input):
    username: str = Field(min_length=3, max_length=100)
    password: Annotated[str, StringConstraints(strip_whitespace=False, min_length=1, max_length=128)]

class UserRegistrationResponse(Token):
    user: UserOut


class PermissionSummary(BaseModel):
    role: Role
    tenant_id: str | None
    organization_id: str | None
    scope: str
    resources: dict[str, list[str]]
    restrictions: list[str]



class TenantChatMessage(Input):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)

class TenantChatRequest(Input):
    question: str = Field(min_length=1, max_length=2000)
    history: list[TenantChatMessage] = Field(default_factory=list, max_length=10)


class ExchangeRateJobCreate(Input):
    base_currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    organization_id: str | None = None

class ExchangeRateJobOut(Record):
    tenant_id: str
    organization_id: str | None
    created_by: str
    base_currency: str
    status: Literal["queued", "running", "succeeded", "failed"]
    attempts: int
    published_at: float | None
    started_at: str | None
    finished_at: str | None
    error: str | None
    result: dict | None
