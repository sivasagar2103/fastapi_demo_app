
from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from rest_api_server.models.base import Base, Record

class User(Record, Base):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(100), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(30))
    tenant_id: Mapped[str | None] = mapped_column(ForeignKey(
        "tenants.id", ondelete="RESTRICT"), index=True)
    organization_id: Mapped[str | None] = mapped_column(String(36), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
